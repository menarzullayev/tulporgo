"""End-to-end (GOAL.md Phase 2 gate): passenger ↔ driver ↔ payment across the real bot dispatcher, the real HTTP API
and the payment callbacks — one database, one event bus, a fake Telegram session. No network, no real token.

Passenger orders in the Mini App (API) → the bot tells the driver → the driver offers in the bot → the passenger
accepts in the Mini App → both get the trip card → complete + rate → public share page. Then a driver pays with Click
(prepare + complete callbacks) → the bot tells the driver, the subscription is extended exactly once.
"""
import hashlib
import hmac
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "bot" / "tests"))       # the bot's fake-Telegram harness

from bot_harness import Env, no_waiting, offer_by_ui, tx  # noqa: E402,F401  (no_waiting is an autouse fixture)
from sqlalchemy import select  # noqa: E402
from tulporgo_api.main import create_app  # noqa: E402
from tulporgo_bot.main import start_optional_jobs  # noqa: E402
from tulporgo_core.enums import PaymentStatus, TripStatus  # noqa: E402
from tulporgo_core.models import Driver, Payment, RideRequest, Trip  # noqa: E402

TOKEN = "1:TEST"                                    # the bot harness token; never a real one
PASSENGER, DRIVER = 101, 202
CLICK_SECRET = "click-test-secret"


def init_data(user_id: int, first_name: str = "Ali") -> str:
    user = {"id": user_id, "first_name": first_name, "language_code": "uz"}
    fields = {"auth_date": str(int(time.time())), "query_id": "AAE-e2e", "user": json.dumps(user)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


def auth(user_id: int) -> dict:
    return {"Authorization": f"tma {init_data(user_id)}"}


async def started(tmp_path, **settings):
    env = await Env(tmp_path, **settings).start()
    await env.seed_places()
    app = create_app(env.settings, env.maker, env.bus)               # same DB and the same bus as the bot
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://e2e")
    return env, http


async def test_passenger_driver_trip_end_to_end(tmp_path):
    env, http = await started(tmp_path, free_period_until=date.today() + timedelta(days=30))
    try:
        await env.user(PASSENGER, name="Ali")
        await env.driver(DRIVER, name="Karim", plate="30A777BC")

        # 1. passenger orders in the Mini App
        r = await http.post("/api/requests", headers=auth(PASSENGER), json={
            "from_place_id": env.qosh, "to_place_id": env.sam, "seats": 2, "note": "yuk bor"})
        assert r.status_code == 201, r.text
        rid = r.json()["id"]

        # 2. the bot told the driver (RequestCreated published by the API after its commit)
        assert any(f"ofp:{rid}" in b for b in env.buttons(DRIVER)), "driver was not notified"

        # 3. the driver offers through the bot
        offer_id = await offer_by_ui(env, DRIVER, rid, "35000")
        assert offer_id is not None

        # 4. the passenger sees and accepts it in the Mini App
        offers = (await http.get(f"/api/requests/{rid}/offers", headers=auth(PASSENGER))).json()["offers"]
        assert [o["id"] for o in offers] == [offer_id] and offers[0]["price"] == 35000
        acc = await http.post(f"/api/offers/{offer_id}/accept", headers=auth(PASSENGER))
        assert acc.status_code == 200, acc.text
        trip_id = acc.json()["id"]

        # 5. the driver got the trip card with the passenger's contact (only now)
        driver_texts = " ".join(env.texts(DRIVER))
        assert "Ali" in driver_texts

        # negative: a stranger cannot accept or read someone else's request
        assert (await http.get(f"/api/requests/{rid}/offers", headers=auth(999))).status_code in (403, 404)

        # 6. complete + rate in the Mini App; the driver's rating changes
        assert (await http.post(f"/api/trips/{trip_id}/complete", headers=auth(PASSENGER))).status_code == 200
        assert (await http.post(f"/api/trips/{trip_id}/rate", headers=auth(PASSENGER),
                                json={"stars": 5, "comment": "Zo'r"})).status_code == 200
        d = await env.db(lambda s: s.scalar(select(Driver).where(Driver.car_plate == "30A777BC")))
        assert (d.rating_sum, d.rating_count) == (5, 1)

        # 7. the public share page: route and car, no personal contacts
        token = await env.db(lambda s: s.scalar(select(Trip.share_token).where(Trip.id == trip_id)))
        share = await http.get(f"/api/share/{token}")                 # no auth on purpose
        assert share.status_code == 200
        body = share.text
        assert "Samarqand" in body and "903333333" not in body and "+998" not in body
        trip = await env.db(lambda s: s.get(Trip, trip_id))
        assert trip.status == TripStatus.COMPLETED
        req = await env.db(lambda s: s.get(RideRequest, rid))
        assert req.status == "completed"
    finally:
        await http.aclose()
        await env.stop()


def click_params(payment: Payment, action: str, prepare_id: str | None = None, secret: str = CLICK_SECRET) -> dict:
    p = {"click_trans_id": "9001", "service_id": "1001", "click_paydoc_id": "77", "merchant_trans_id": str(payment.id),
         "amount": f"{payment.amount}.00", "action": action, "error": "0", "error_note": "Success",
         "sign_time": "2026-11-10 12:00:00"}
    parts = [p["click_trans_id"], p["service_id"], secret, p["merchant_trans_id"]]
    if prepare_id is not None:
        p["merchant_prepare_id"] = prepare_id
        parts.append(prepare_id)
    parts += [p["amount"], p["action"], p["sign_time"]]
    p["sign_string"] = hashlib.md5("".join(parts).encode()).hexdigest()
    return p


async def test_driver_pays_with_click_end_to_end(tmp_path):
    env, http = await started(tmp_path, free_period_until=None, click_service_id="1001", click_merchant_id="2002",
                              click_secret_key=CLICK_SECRET)
    jobs = start_optional_jobs(env.bot, env.maker, env.settings, env.bus)     # W4 notices on PaymentConfirmed
    try:
        await env.driver(DRIVER, name="Karim")
        before = (await env.db(lambda s: s.scalar(select(Driver)))).subscription_until

        co = await http.post("/api/payments/checkout", headers=auth(DRIVER),
                             json={"plan": "pro", "months": 1, "provider": "click"})
        assert co.status_code == 200, co.text
        data = co.json()
        assert data["amount"] == 59000 and data["start"]["type"] == "url"
        assert data["start"]["url"].startswith("https://")
        payment = await env.db(lambda s: s.get(Payment, data["payment_id"]))

        # negative: a forged signature is refused and changes nothing
        bad = await http.post("/api/payments/click/prepare", data=click_params(payment, "0", secret="wrong"))
        assert bad.json()["error"] == -1

        prep = (await http.post("/api/payments/click/prepare", data=click_params(payment, "0"))).json()
        assert prep["error"] == 0, prep
        comp = (await http.post("/api/payments/click/complete",
                                data=click_params(payment, "1", str(prep["merchant_prepare_id"])))).json()
        assert comp["error"] == 0, comp

        paid = await env.db(lambda s: s.get(Payment, payment.id))
        assert paid.status == PaymentStatus.PAID
        after = (await env.db(lambda s: s.scalar(select(Driver)))).subscription_until
        assert after > before

        # the driver is told in the bot (W4 job subscribed to PaymentConfirmed)
        await _settle()
        assert any("Pro" in m for m in env.texts(DRIVER)), env.texts(DRIVER)

        # negative: Click replays the complete callback → idempotent, no second extension
        again = (await http.post("/api/payments/click/complete",
                                 data=click_params(payment, "1", str(prep["merchant_prepare_id"])))).json()
        assert again["error"] in (0, -4)                                 # "already paid" per the Click spec
        assert (await env.db(lambda s: s.scalar(select(Driver)))).subscription_until == after
    finally:
        for h in jobs:
            h.cancel()
        await http.aclose()
        await env.stop()


async def _settle():
    """W4 sends the paid notice from a task that waits until the payment's commit is visible; wait for those tasks."""
    import asyncio

    import tulporgo_payments.bot as paybot
    pending = list(paybot.PENDING)
    assert pending, "no paid-notice task was started (PaymentConfirmed not delivered to the bot)"
    await asyncio.wait_for(asyncio.gather(*pending), timeout=15)
