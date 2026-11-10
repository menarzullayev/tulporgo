# ruff: noqa: F401, F811  (fixtures are imported explicitly, see pay_fixtures.py)
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import httpx
import pytest
from pay_fixtures import engine
from pay_helpers import PAYME_KEY, make_driver, make_settings, make_user
from sqlalchemy import select
from tulporgo_api.main import create_app
from tulporgo_core.db import Base, make_engine, make_sessionmaker
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.events import InMemoryBus
from tulporgo_core.models import Payment

TOKEN = "123456:TEST"
AUTH = "Basic " + base64.b64encode(f"Paycom:{PAYME_KEY}".encode()).decode()


def init_data(tg_id: int, token: str = TOKEN) -> str:
    fields = {"auth_date": str(int(time.time())), "query_id": "AAE",
              "user": json.dumps({"id": tg_id, "first_name": "Ali"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


@pytest.fixture
async def env(tmp_path):
    eng = make_engine(f"sqlite+aiosqlite:///{(tmp_path / 'p.db').as_posix()}")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    maker = make_sessionmaker(eng)
    cfg = make_settings()
    bus = InMemoryBus()
    app = create_app(cfg, maker=maker, bus=bus)
    calls = []

    async def fake_tg(method, params):
        calls.append((method, params))
        return "https://t.me/$invoice"
    app.state.tg_call = fake_tg
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        yield type("Env", (), {"client": client, "maker": maker, "cfg": cfg, "bus": bus, "app": app,
                               "tg_calls": calls})
    await eng.dispose()


async def seed_driver(env):
    async with env.maker() as s:
        d = await make_driver(s, env.cfg)
        tg_id = d.user.tg_id
        await s.commit()
    return tg_id


async def payments(env):
    async with env.maker() as s:
        return (await s.execute(select(Payment))).scalars().all()


def tma(tg_id):
    return {"Authorization": f"tma {init_data(tg_id)}"}


async def test_routes_are_mounted(env):
    assert (await env.client.get("/api/health")).json() == {"ok": True}
    paths = set(env.app.openapi()["paths"])
    assert {"/api/payments/checkout", "/api/payments/click/prepare", "/api/payments/click/complete",
            "/api/payments/payme"} <= paths


async def test_checkout_requires_mini_app_auth(env):
    r = await env.client.post("/api/payments/checkout", json={"plan": "pro", "months": 1, "provider": "click"})
    assert r.status_code == 401
    forged = {"Authorization": f"tma {init_data(1, token='999:OTHER')}"}
    r = await env.client.post("/api/payments/checkout", headers=forged,
                              json={"plan": "pro", "months": 1, "provider": "click"})
    assert r.status_code == 401 and await payments(env) == []


async def test_checkout_click_returns_url_and_server_side_amount(env):
    tg = await seed_driver(env)
    r = await env.client.post("/api/payments/checkout", headers=tma(tg), json={"plan": "pro", "months": 3,
                                                                                "provider": "click"})
    body = r.json()
    assert r.status_code == 200 and body["amount"] == 177_000 and body["start"]["type"] == "url"
    assert body["start"]["url"].startswith("https://my.click.uz/services/pay?")


async def test_client_sent_amount_is_ignored(env):
    tg = await seed_driver(env)
    r = await env.client.post("/api/payments/checkout", headers=tma(tg),
                              json={"plan": "basic", "months": 1, "provider": "payme", "amount": 1})
    assert r.status_code == 200 and r.json()["amount"] == 29_000
    assert [p.amount for p in await payments(env)] == [29_000]


async def test_checkout_stars_returns_invoice_link_and_recurring(env):
    tg = await seed_driver(env)
    r = await env.client.post("/api/payments/checkout", headers=tma(tg),
                              json={"plan": "pro", "months": 1, "provider": "stars", "recurring": True})
    body = r.json()
    assert r.status_code == 200 and body["currency"] == "XTR" and body["start"]["invoice_link"] == "https://t.me/$invoice"
    assert env.tg_calls[0][0] == "createInvoiceLink" and env.tg_calls[0][1]["subscription_period"] == 2_592_000


async def test_checkout_p2p_returns_card_instructions(env):
    tg = await seed_driver(env)
    r = await env.client.post("/api/payments/checkout", headers=tma(tg),
                              json={"plan": "pro", "months": 1, "provider": "p2p"})
    assert r.json()["start"]["card"] == env.cfg.p2p_card_number


@pytest.mark.parametrize("body,status,code", [
    ({"plan": "pro", "months": 2, "provider": "click"}, 422, "bad_months"),
    ({"plan": "gold", "months": 1, "provider": "click"}, 422, "bad_plan"),
    ({"plan": "pro", "months": 1, "provider": "bitcoin"}, 422, "provider_unavailable"),
])
async def test_checkout_validation_errors(env, body, status, code):
    tg = await seed_driver(env)
    r = await env.client.post("/api/payments/checkout", headers=tma(tg), json=body)
    assert r.status_code == status and r.json()["error"] == code


async def test_checkout_non_driver_forbidden(env):
    async with env.maker() as s:
        u = await make_user(s)
        tg = u.tg_id
        await s.commit()
    r = await env.client.post("/api/payments/checkout", headers=tma(tg),
                              json={"plan": "pro", "months": 1, "provider": "click"})
    assert r.status_code == 403 and r.json()["error"] == "driver_required"


async def test_checkout_refused_during_free_period(env):
    from datetime import date, timedelta
    env.app.state.settings = make_settings(free_period_until=date.today() + timedelta(days=5))
    tg = await seed_driver(env)
    r = await env.client.post("/api/payments/checkout", headers=tma(tg),
                              json={"plan": "pro", "months": 1, "provider": "click"})
    assert r.status_code == 409 and r.json()["error"] == "free_period" and await payments(env) == []
    r = await env.client.get("/api/payments/providers", headers=tma(tg))
    assert r.json()["free_period"] is True


# ---- Click over HTTP (form-encoded, as Click sends it)

def click_form(p, action, secret="click-test-secret", prep=None, **kw):
    r = {"click_trans_id": "900", "service_id": "1001", "click_paydoc_id": "1", "merchant_trans_id": str(p.id),
         "amount": f"{p.amount}.00", "action": action, "error": "0", "error_note": "Success",
         "sign_time": "2026-11-10 10:00:00"}
    if action == "1":
        r["merchant_prepare_id"] = str(prep or p.id)
    r.update(kw)
    parts = [r["click_trans_id"], r["service_id"], secret, r["merchant_trans_id"]]
    if action == "1":
        parts.append(r["merchant_prepare_id"])
    parts += [r["amount"], r["action"], r["sign_time"]]
    r["sign_string"] = hashlib.md5("".join(parts).encode()).hexdigest()
    return r


async def test_click_http_flow_and_replay(env):
    tg = await seed_driver(env)
    await env.client.post("/api/payments/checkout", headers=tma(tg),
                          json={"plan": "pro", "months": 1, "provider": "click"})
    p = (await payments(env))[0]
    r = await env.client.post("/api/payments/click/prepare", data=click_form(p, "0"))
    assert r.status_code == 200 and r.json()["error"] == 0
    r = await env.client.post("/api/payments/click/complete", data=click_form(p, "1"))
    assert r.json()["error"] == 0 and r.json()["merchant_confirm_id"] == p.id
    again = await env.client.post("/api/payments/click/complete", data=click_form(p, "1"))
    assert again.json()["error"] == -4
    assert (await payments(env))[0].status == PaymentStatus.PAID
    assert len(env.bus.published) == 1


async def test_click_http_rejects_bad_signature_and_wrong_endpoint_action(env):
    tg = await seed_driver(env)
    await env.client.post("/api/payments/checkout", headers=tma(tg),
                          json={"plan": "pro", "months": 1, "provider": "click"})
    p = (await payments(env))[0]
    r = await env.client.post("/api/payments/click/prepare", data=click_form(p, "0", secret="nope"))
    assert r.json()["error"] == -1
    r = await env.client.post("/api/payments/click/prepare", data=click_form(p, "1"))   # Complete sent to Prepare
    assert r.json()["error"] == -3
    r = await env.client.post("/api/payments/click/complete", data=click_form(p, "0"))
    assert r.json()["error"] == -3
    assert (await payments(env))[0].status == PaymentStatus.PENDING


# ---- Payme over HTTP

async def test_payme_http_flow_and_auth(env):
    tg = await seed_driver(env)
    await env.client.post("/api/payments/checkout", headers=tma(tg),
                          json={"plan": "basic", "months": 1, "provider": "payme"})
    p = (await payments(env))[0]
    body = {"jsonrpc": "2.0", "id": 1, "method": "CheckPerformTransaction",
            "params": {"amount": 2_900_000, "account": {"payment_id": str(p.id)}}}
    r = await env.client.post("/api/payments/payme", json=body)                  # no Authorization header
    assert r.status_code == 200 and r.json()["error"]["code"] == -32504
    r = await env.client.post("/api/payments/payme", json=body, headers={"Authorization": AUTH})
    assert r.json()["result"] == {"allow": True}
    create = {**body, "method": "CreateTransaction",
              "params": {**body["params"], "id": "c" * 24, "time": 1_700_000_000_000}}
    assert (await env.client.post("/api/payments/payme", json=create, headers={"Authorization": AUTH})
            ).json()["result"]["state"] == 1
    perform = {"jsonrpc": "2.0", "id": 3, "method": "PerformTransaction", "params": {"id": "c" * 24}}
    assert (await env.client.post("/api/payments/payme", json=perform, headers={"Authorization": AUTH})
            ).json()["result"]["state"] == 2
    assert (await payments(env))[0].status == PaymentStatus.PAID


async def test_payme_http_garbage_body_is_json_rpc_error(env):
    r = await env.client.post("/api/payments/payme", content=b"nope", headers={"Authorization": AUTH})
    assert r.status_code == 200 and r.json()["error"]["code"] == -32700
