# ruff: noqa: F401, F811  (fixtures are imported explicitly, see pay_fixtures.py)
"""Click SHOP API fixtures: sign_string is computed independently here with hashlib (not via the module under test)."""
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from pay_fixtures import bus, cfg, engine, free_cfg, maker, s
from pay_helpers import CLICK_SECRET, make_driver
from tulporgo_core.enums import PaymentStatus
from tulporgo_payments import service
from tulporgo_payments.providers import click


def md5(*parts) -> str:
    return hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()


def prepare_req(p, *, trans="555", amount=None, secret=CLICK_SECRET, **kw):
    amount = str(p.amount) + ".00" if amount is None else amount
    r = {"click_trans_id": trans, "service_id": "1001", "click_paydoc_id": "777", "merchant_trans_id": str(p.id),
         "amount": amount, "action": "0", "error": "0", "error_note": "Success", "sign_time": "2026-11-10 12:00:00"}
    r.update(kw)
    r["sign_string"] = md5(r["click_trans_id"], r["service_id"], secret, r["merchant_trans_id"], r["amount"],
                           r["action"], r["sign_time"])
    return r


def complete_req(p, prep_id=None, *, trans="555", amount=None, secret=CLICK_SECRET, **kw):
    amount = str(p.amount) + ".00" if amount is None else amount
    r = {"click_trans_id": trans, "service_id": "1001", "click_paydoc_id": "777", "merchant_trans_id": str(p.id),
         "merchant_prepare_id": str(prep_id if prep_id is not None else p.id), "amount": amount, "action": "1",
         "error": "0", "error_note": "Success", "sign_time": "2026-11-10 12:00:05"}
    r.update(kw)
    r["sign_string"] = md5(r["click_trans_id"], r["service_id"], secret, r["merchant_trans_id"],
                           r["merchant_prepare_id"], r["amount"], r["action"], r["sign_time"])
    return r


async def setup(s, cfg):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    return d, c.payment


def test_pay_url_builder(cfg):
    class P:
        id, amount = 42, 59_000
    q = parse_qs(urlparse(click.build_pay_url(cfg, P())).query)
    assert q["service_id"] == ["1001"] and q["merchant_id"] == ["2002"]
    assert q["amount"] == ["59000.00"] and q["transaction_param"] == ["42"]
    assert "secret" not in click.build_pay_url(cfg, P()).lower()


async def test_prepare_then_complete_pays_and_extends(s, cfg, bus):
    d, p = await setup(s, cfg)
    r = await click.handle(s, cfg, prepare_req(p), bus)
    assert r["error"] == 0 and r["merchant_prepare_id"] == p.id and r["click_trans_id"] == "555"
    assert p.status == PaymentStatus.PENDING
    r = await click.handle(s, cfg, complete_req(p), bus)
    assert r["error"] == 0 and r["merchant_confirm_id"] == p.id
    assert p.status == PaymentStatus.PAID and p.external_id == "555" and d.plan == "pro"
    assert d.subscription_until is not None and len(bus.published) == 1


async def test_bad_signature_rejected_on_both_steps(s, cfg):
    d, p = await setup(s, cfg)
    r = await click.handle(s, cfg, prepare_req(p, secret="wrong-secret"))
    assert r["error"] == -1
    await click.handle(s, cfg, prepare_req(p))
    r = await click.handle(s, cfg, complete_req(p, secret="wrong-secret"))
    assert r["error"] == -1 and p.status == PaymentStatus.PENDING


async def test_tampered_field_breaks_signature(s, cfg):
    d, p = await setup(s, cfg)
    req = prepare_req(p)
    req["amount"] = "1.00"                                   # attacker lowers the amount, keeps the old sign
    assert (await click.handle(s, cfg, req))["error"] == -1


async def test_missing_signature_or_secret_unconfigured(s, cfg):
    d, p = await setup(s, cfg)
    req = prepare_req(p)
    del req["sign_string"]
    assert (await click.handle(s, cfg, req))["error"] == -8
    from pay_helpers import make_settings
    bare = make_settings(click_secret_key="")
    assert (await click.handle(s, bare, prepare_req(p, secret="")))["error"] == -1   # empty secret never validates


async def test_wrong_amount_rejected(s, cfg):
    d, p = await setup(s, cfg)
    assert (await click.handle(s, cfg, prepare_req(p, amount="1000.00")))["error"] == -2
    assert (await click.handle(s, cfg, prepare_req(p, amount="59000.50")))["error"] == -2
    await click.handle(s, cfg, prepare_req(p))
    r = await click.handle(s, cfg, complete_req(p, amount="58999.00"))
    assert r["error"] == -2 and p.status == PaymentStatus.PENDING


async def test_unknown_or_foreign_payment(s, cfg):
    d, p = await setup(s, cfg)
    ghost = type("G", (), {"id": 99999, "amount": 59_000})()
    assert (await click.handle(s, cfg, prepare_req(ghost)))["error"] == -5
    non_numeric = prepare_req(p, merchant_trans_id="abc")
    assert (await click.handle(s, cfg, non_numeric))["error"] == -5
    c2 = await service.start_checkout(s, d.user, cfg, "payme", "pro", 1)   # a Payme order cannot be paid via Click
    assert (await click.handle(s, cfg, prepare_req(c2.payment)))["error"] == -5


async def test_complete_without_prepare_or_wrong_prepare_id(s, cfg):
    d, p = await setup(s, cfg)
    assert (await click.handle(s, cfg, complete_req(p)))["error"] == -6
    await click.handle(s, cfg, prepare_req(p))
    assert (await click.handle(s, cfg, complete_req(p, prep_id=999)))["error"] == -6
    assert (await click.handle(s, cfg, complete_req(p, trans="other-trans")))["error"] == -6
    assert p.status == PaymentStatus.PENDING


async def test_replayed_complete_is_idempotent(s, cfg, bus):
    d, p = await setup(s, cfg)
    await click.handle(s, cfg, prepare_req(p), bus)
    await click.handle(s, cfg, complete_req(p), bus)
    until = d.subscription_until
    r = await click.handle(s, cfg, complete_req(p), bus)
    assert r["error"] == -4 and d.subscription_until == until and len(bus.published) == 1
    assert (await click.handle(s, cfg, prepare_req(p), bus))["error"] == -4      # prepare after paid


async def test_click_reported_error_cancels_payment(s, cfg):
    d, p = await setup(s, cfg)
    await click.handle(s, cfg, prepare_req(p))
    r = await click.handle(s, cfg, complete_req(p, error="-5017", error_note="insufficient funds"))
    assert r["error"] == -9 and p.status == PaymentStatus.CANCELLED and d.plan != "pro"
    assert (await click.handle(s, cfg, complete_req(p)))["error"] == -9           # cannot be completed afterwards
    assert (await click.handle(s, cfg, prepare_req(p)))["error"] == -9


async def test_wrong_service_unknown_action_and_missing_fields(s, cfg):
    d, p = await setup(s, cfg)
    assert (await click.handle(s, cfg, prepare_req(p, service_id="9999")))["error"] == -8
    assert (await click.handle(s, cfg, prepare_req(p, action="7")))["error"] == -3
    req = prepare_req(p)
    del req["merchant_trans_id"]
    assert (await click.handle(s, cfg, req))["error"] == -8
    assert (await click.handle(s, cfg, {}))["error"] == -8
    assert (await click.handle(s, cfg, prepare_req(p, amount="abc")))["error"] == -8


async def test_provider_verify_and_start(s, cfg):
    d, p = await setup(s, cfg)
    gw = click.ClickProvider(cfg)
    assert await gw.verify(prepare_req(p)) and await gw.verify(complete_req(p))
    assert not await gw.verify(prepare_req(p, secret="bad"))
    assert not await gw.verify({})
    assert (await gw.start(p))["type"] == "url"


@pytest.mark.parametrize("value", ["59000", "59000.00", "59000.0"])
async def test_amount_formats_equal(s, cfg, value):
    d, p = await setup(s, cfg)
    assert (await click.handle(s, cfg, prepare_req(p, amount=value)))["error"] == 0
