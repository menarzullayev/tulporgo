# ruff: noqa: F401, F811  (fixtures are imported explicitly, see pay_fixtures.py)
"""Payme Merchant API fixtures (JSON-RPC bodies shaped like the ones Payme sends)."""
import base64
import json

import pytest
from pay_fixtures import bus, cfg, engine, free_cfg, maker, s
from pay_helpers import PAYME_KEY, make_driver, make_settings
from tulporgo_core.enums import PaymentStatus
from tulporgo_payments import service
from tulporgo_payments.providers import payme

AUTH = "Basic " + base64.b64encode(f"Paycom:{PAYME_KEY}".encode()).decode()
T0 = 1_700_000_000_000
TID = "5305e3bab097f420a62ced0b"


async def rpc(s, cfg, method, params, *, auth=AUTH, now=T0 + 1, bus=None, rid=7):
    body = json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
    return await payme.handle(s, cfg, body, auth, bus, now_ms=now)


async def setup(s, cfg):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "payme", "pro", 1)
    return d, c.payment


def acct(p, amount=None):
    return {"amount": p.amount * 100 if amount is None else amount, "account": {"payment_id": str(p.id)}}


def create(p, **kw):
    return {"id": TID, "time": T0, **acct(p), **kw}


def err(r):
    return r["error"]["code"]


def test_checkout_url_is_base64_of_params_and_test_host(cfg):
    class P:
        id, amount = 42, 59_000
    url = payme.build_checkout_url(cfg, P())
    assert url.startswith("https://test.paycom.uz/")
    decoded = base64.b64decode(url.rsplit("/", 1)[1]).decode()
    assert "m=merchant-test" in decoded and "ac.payment_id=42" in decoded and "a=5900000" in decoded
    live = payme.build_checkout_url(make_settings(payme_test_mode=False), P())
    assert live.startswith("https://checkout.paycom.uz/")


async def test_basic_auth_required_everywhere(s, cfg):
    d, p = await setup(s, cfg)
    bad = "Basic " + base64.b64encode(b"Paycom:wrong").decode()
    wrong_login = "Basic " + base64.b64encode(f"Hacker:{PAYME_KEY}".encode()).decode()
    for header in (None, "", bad, wrong_login, "Bearer abc", "Basic !!!notbase64"):
        r = await rpc(s, cfg, "CheckPerformTransaction", acct(p), auth=header)
        assert err(r) == -32504 and r["id"] == 7
    assert p.status == PaymentStatus.PENDING
    unconfigured = make_settings(payme_key="")
    assert err(await rpc(s, unconfigured, "CheckPerformTransaction", acct(p))) == -32504


async def test_malformed_requests(s, cfg):
    assert err(await payme.handle(s, cfg, "{not json", AUTH)) == -32700
    assert err(await payme.handle(s, cfg, "[1,2]", AUTH)) == -32600
    assert err(await payme.handle(s, cfg, json.dumps({"id": 1, "method": 5}), AUTH)) == -32600
    assert err(await rpc(s, cfg, "Nope", {})) == -32601
    assert err(await payme.handle(s, cfg, json.dumps({"id": 1, "method": "GetStatement", "params": 3}), AUTH)) == -32600


async def test_check_perform_ok_and_failures(s, cfg):
    d, p = await setup(s, cfg)
    assert (await rpc(s, cfg, "CheckPerformTransaction", acct(p)))["result"] == {"allow": True}
    r = await rpc(s, cfg, "CheckPerformTransaction", acct(p, amount=p.amount * 100 - 1))
    assert err(r) == -31001 and r["error"]["data"] == "amount"
    r = await rpc(s, cfg, "CheckPerformTransaction", acct(p, amount=p.amount))       # so'm instead of tiyin
    assert err(r) == -31001
    assert err(await rpc(s, cfg, "CheckPerformTransaction", {"amount": 1, "account": {"payment_id": "999"}})) == -31050
    assert err(await rpc(s, cfg, "CheckPerformTransaction", {"amount": 1, "account": {}})) == -31050
    assert err(await rpc(s, cfg, "CheckPerformTransaction", {"amount": 1, "account": {"payment_id": "x"}})) == -31050
    assert err(await rpc(s, cfg, "CheckPerformTransaction", {"amount": True, "account": {"payment_id": "1"}})) in (
        -31001, -31050)


async def test_click_order_cannot_be_paid_via_payme(s, cfg):
    d, _ = await setup(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    assert err(await rpc(s, cfg, "CheckPerformTransaction", acct(c.payment))) == -31050


async def test_full_lifecycle_create_perform_check(s, cfg, bus):
    d, p = await setup(s, cfg)
    r = (await rpc(s, cfg, "CreateTransaction", create(p), now=T0 + 10))["result"]
    assert r == {"create_time": T0 + 10, "transaction": str(p.id), "state": 1}
    assert p.status == PaymentStatus.PENDING and d.plan != "pro"
    r = (await rpc(s, cfg, "PerformTransaction", {"id": TID}, now=T0 + 20, bus=bus))["result"]
    assert r == {"transaction": str(p.id), "perform_time": T0 + 20, "state": 2}
    assert p.status == PaymentStatus.PAID and d.plan == "pro" and p.external_id == TID
    chk = (await rpc(s, cfg, "CheckTransaction", {"id": TID}))["result"]
    assert chk == {"create_time": T0 + 10, "perform_time": T0 + 20, "cancel_time": 0,
                   "transaction": str(p.id), "state": 2, "reason": None}
    assert len(bus.published) == 1


async def test_create_is_idempotent_and_busy_order_refused(s, cfg):
    d, p = await setup(s, cfg)
    a = (await rpc(s, cfg, "CreateTransaction", create(p), now=T0 + 10))["result"]
    b = (await rpc(s, cfg, "CreateTransaction", create(p), now=T0 + 99))["result"]
    assert a == b                                            # same id: same answer, original create_time
    other = {**create(p), "id": "aaaaaaaaaaaaaaaaaaaaaaaa"}
    assert err(await rpc(s, cfg, "CreateTransaction", other)) == -31099   # order already has an active transaction
    assert err(await rpc(s, cfg, "CheckPerformTransaction", acct(p))) == -31099


async def test_create_with_wrong_amount_or_unknown_order(s, cfg):
    d, p = await setup(s, cfg)
    assert err(await rpc(s, cfg, "CreateTransaction", create(p, amount=100))) == -31001
    ghost = {"id": TID, "time": T0, "amount": 100, "account": {"payment_id": "424242"}}
    assert err(await rpc(s, cfg, "CreateTransaction", ghost)) == -31050
    assert err(await rpc(s, cfg, "CreateTransaction", {"time": T0, **acct(p)})) == -32600
    assert p.external_id is None


async def test_perform_unknown_transaction_and_replay(s, cfg, bus):
    d, p = await setup(s, cfg)
    assert err(await rpc(s, cfg, "PerformTransaction", {"id": "nope"})) == -31003
    await rpc(s, cfg, "CreateTransaction", create(p), now=T0 + 10)
    first = (await rpc(s, cfg, "PerformTransaction", {"id": TID}, now=T0 + 20, bus=bus))["result"]
    until = d.subscription_until
    again = (await rpc(s, cfg, "PerformTransaction", {"id": TID}, now=T0 + 500, bus=bus))["result"]
    assert again == first and d.subscription_until == until and len(bus.published) == 1


async def test_perform_after_timeout_cancels_with_reason_4(s, cfg):
    d, p = await setup(s, cfg)
    await rpc(s, cfg, "CreateTransaction", create(p), now=T0)
    late = T0 + payme.TIMEOUT_MS + 1
    assert err(await rpc(s, cfg, "PerformTransaction", {"id": TID}, now=late)) == -31008
    assert p.status == PaymentStatus.CANCELLED and d.plan != "pro"
    chk = (await rpc(s, cfg, "CheckTransaction", {"id": TID}))["result"]
    assert chk["state"] == -1 and chk["reason"] == 4 and chk["cancel_time"] == late


async def test_cancel_before_perform(s, cfg):
    d, p = await setup(s, cfg)
    await rpc(s, cfg, "CreateTransaction", create(p), now=T0)
    r = (await rpc(s, cfg, "CancelTransaction", {"id": TID, "reason": 3}, now=T0 + 5))["result"]
    assert r == {"transaction": str(p.id), "cancel_time": T0 + 5, "state": -1}
    assert p.status == PaymentStatus.CANCELLED
    assert err(await rpc(s, cfg, "PerformTransaction", {"id": TID})) == -31008     # cannot perform a cancelled one
    again = (await rpc(s, cfg, "CancelTransaction", {"id": TID, "reason": 3}, now=T0 + 99))["result"]
    assert again["cancel_time"] == T0 + 5                    # idempotent
    assert err(await rpc(s, cfg, "CheckPerformTransaction", acct(p))) == -31099   # cancelled order is closed


async def test_cancel_after_perform_refunds_and_takes_days_back(s, cfg):
    d, p = await setup(s, cfg)
    await rpc(s, cfg, "CreateTransaction", create(p), now=T0)
    await rpc(s, cfg, "PerformTransaction", {"id": TID}, now=T0 + 1)
    paid_until = d.subscription_until
    r = (await rpc(s, cfg, "CancelTransaction", {"id": TID, "reason": 5}, now=T0 + 9))["result"]
    assert r["state"] == -2 and p.status == PaymentStatus.REFUNDED
    from datetime import timedelta
    assert d.subscription_until == paid_until - timedelta(days=30)
    until = d.subscription_until
    await rpc(s, cfg, "CancelTransaction", {"id": TID, "reason": 5}, now=T0 + 10)   # replay: no second reversal
    assert d.subscription_until == until
    assert err(await rpc(s, cfg, "CancelTransaction", {"id": "ghost", "reason": 1})) == -31003


async def test_check_transaction_unknown(s, cfg):
    assert err(await rpc(s, cfg, "CheckTransaction", {"id": "ghost"})) == -31003
    assert err(await rpc(s, cfg, "CheckTransaction", {})) == -32600


async def test_get_statement_filters_by_time_window(s, cfg):
    d, p = await setup(s, cfg)
    d2 = await make_driver(s, cfg)
    p2 = (await service.start_checkout(s, d2.user, cfg, "payme", "basic", 1)).payment
    await rpc(s, cfg, "CreateTransaction", create(p), now=T0 + 1)
    await rpc(s, cfg, "CreateTransaction", {"id": "b" * 24, "time": T0 + 5000, **acct(p2)}, now=T0 + 5001)
    r = (await rpc(s, cfg, "GetStatement", {"from": T0 - 1, "to": T0 + 1000}))["result"]["transactions"]
    assert [t["id"] for t in r] == [TID] and r[0]["amount"] == 5_900_000
    assert r[0]["account"] == {"payment_id": str(p.id)} and r[0]["state"] == 1
    both = (await rpc(s, cfg, "GetStatement", {"from": 0, "to": T0 + 10_000}))["result"]["transactions"]
    assert len(both) == 2
    assert (await rpc(s, cfg, "GetStatement", {"from": T0 + 9000, "to": T0 + 9999}))["result"]["transactions"] == []
    assert err(await rpc(s, cfg, "GetStatement", {"from": "a", "to": 1})) == -32600


@pytest.mark.parametrize("method", ["CreateTransaction", "PerformTransaction", "CancelTransaction", "GetStatement"])
async def test_mutating_methods_require_auth(s, cfg, method):
    d, p = await setup(s, cfg)
    assert err(await rpc(s, cfg, method, create(p), auth=None)) == -32504
    assert p.external_id is None and p.status == PaymentStatus.PENDING


async def test_provider_verify_and_start(s, cfg):
    d, p = await setup(s, cfg)
    gw = payme.PaymeProvider(cfg)
    assert await gw.verify({"authorization": AUTH})
    assert not await gw.verify({"authorization": "Basic " + base64.b64encode(b"Paycom:x").decode()})
    assert not await gw.verify({})
    s_ = await gw.start(p)
    assert s_["amount_tiyin"] == 5_900_000 and s_["url"].startswith("https://test.paycom.uz/")
