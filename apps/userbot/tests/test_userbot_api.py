"""Mini App API: consent -> login (code + 2FA) -> groups -> settings -> template -> pause -> logout.
No network: the Telethon client is a fake. Codes, passwords and sessions must never be stored or logged in plain text."""
import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta
from urllib.parse import urlencode

import httpx
import pytest
from sqlalchemy import select, text
from telethon import errors as tg
from tulporgo_api.main import create_app
from tulporgo_core.db import utcnow
from tulporgo_core.enums import Plan, UserbotStatus
from tulporgo_core.models import UserbotAccount
from tulporgo_userbot import crypto, runtime
from tulporgo_userbot.client import GroupInfo
from userbot_fixtures import *  # noqa: F403 - pytest fixtures
from userbot_helpers import SESSION_PLAIN, make_account, make_driver

TOKEN = "123456:TEST"


def init_data(tg_id: int) -> str:
    fields = {"auth_date": str(int(time.time())), "query_id": "AAE",
              "user": json.dumps({"id": tg_id, "first_name": "Haydovchi"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


class Api:
    def __init__(self, client: httpx.AsyncClient, tg_id: int) -> None:
        self.c, self.tg_id = client, tg_id

    async def __call__(self, method: str, path: str, body: dict | None = None, auth: bool = True):
        headers = {"Authorization": f"tma {init_data(self.tg_id)}"} if auth else {}
        return await self.c.request(method, f"/api/userbot{path}", json=body, headers=headers)


@pytest.fixture
async def make_api(maker, bus):
    clients = []

    async def build(settings, tg_id):
        app = create_app(settings, maker=maker, bus=bus)
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        return Api(c, tg_id)
    yield build
    for c in clients:
        await c.aclose()


@pytest.fixture
async def api(s, settings, make_api, factory):
    d = await make_driver(s, settings)
    return await make_api(settings, d.user.tg_id)


async def account_row(maker, driver_id=None):
    async with maker() as s2:
        return (await s2.execute(select(UserbotAccount))).scalars().first()


async def all_db_text(maker) -> str:
    """Every textual column of every userbot table, to prove nothing sensitive was stored."""
    async with maker() as s2:
        rows = []
        for table in ("userbot_accounts", "userbot_groups", "userbot_posts"):
            rows += (await s2.execute(text(f"SELECT * FROM {table}"))).all()
        return repr(rows)


# ------------------------------------------------------------------ auth / driver

async def test_requires_mini_app_auth(api):
    assert (await api("GET", "/status", auth=False)).status_code == 401


async def test_non_driver_is_refused(s, settings, make_api, factory):
    from tulporgo_core.services import users
    await users.get_or_create_user(s, 424242, username=None, first_name="Yo'lovchi")
    await s.commit()
    r = await (await make_api(settings, 424242))("GET", "/status")
    assert r.status_code == 403 and r.json()["error"] == "not_driver"


# ------------------------------------------------------------------ consent (decision 8)

async def test_login_needs_consent_first(api, factory):
    r = await api("POST", "/login/start", {"phone": "+998901234567"})
    assert r.status_code == 403 and r.json()["error"] == "consent_required"
    assert factory.code_requests == [] and factory.clients == []            # Telegram was never contacted


async def test_consent_then_login_start(api, maker, factory):
    r = await api("POST", "/consent")
    assert r.status_code == 200 and r.json()["consent"] is True
    assert (await account_row(maker)).consent_at is not None
    r = await api("POST", "/login/start", {"phone": "+998 90 123 45 67"})
    assert r.status_code == 200 and r.json() == {"status": "code_sent"}
    assert factory.code_requests == ["+998901234567"]


async def test_code_without_consent_or_pending_login_is_refused(api, factory):
    assert (await api("POST", "/login/code", {"code": "12345"})).json()["error"] == "consent_required"
    await api("POST", "/consent")
    r = await api("POST", "/login/code", {"code": "12345"})
    assert r.status_code == 404 and r.json()["error"] == "no_pending_login"


async def test_bad_phone_is_rejected_before_telegram(api, factory):
    await api("POST", "/consent")
    for bad in ("abc", "123", "+99890", ""):
        r = await api("POST", "/login/start", {"phone": bad})
        assert r.status_code == 422 and r.json()["error"] == "bad_phone"
    assert factory.code_requests == []


async def test_basic_plan_cannot_start_login(s, paid_settings, make_api, factory):
    d = await make_driver(s, paid_settings, plan=Plan.BASIC)
    a = await make_api(paid_settings, d.user.tg_id)
    await a("POST", "/consent")
    r = await a("POST", "/login/start", {"phone": "+998901234567"})
    assert r.status_code == 403 and r.json()["error"] == "plan_required" and factory.code_requests == []


async def test_login_not_configured_gives_503(s, settings, make_api, monkeypatch):
    monkeypatch.delenv("TULPORGO_TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TULPORGO_TELEGRAM_API_HASH", raising=False)
    runtime.set_factory(None)
    d = await make_driver(s, settings)
    a = await make_api(settings, d.user.tg_id)
    await a("POST", "/consent")
    r = await a("POST", "/login/start", {"phone": "+998901234567"})
    assert r.status_code == 503 and r.json()["error"] == "telegram_api_missing"


# ------------------------------------------------------------------ login: code path

async def test_login_with_code_stores_only_an_encrypted_session(api, maker, factory, settings):
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    r = await api("POST", "/login/code", {"code": "12345"})
    assert r.status_code == 200 and r.json()["status"] == UserbotStatus.CONNECTED and r.json()["connected"] is True
    assert SESSION_PLAIN not in r.text and "12345" not in r.text            # not echoed to the browser either
    acc = await account_row(maker)
    assert acc.status == UserbotStatus.CONNECTED and acc.tg_user_id == factory.me_id
    assert SESSION_PLAIN not in acc.session_encrypted
    assert crypto.decrypt_session(settings, acc.session_encrypted) == SESSION_PLAIN
    dump = await all_db_text(maker)
    assert SESSION_PLAIN not in dump and "12345" not in dump
    assert factory.clients[0].disconnected                                  # the login client is closed afterwards


async def test_wrong_code_then_correct(api, maker, factory):
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    r = await api("POST", "/login/code", {"code": "99999"})
    assert r.status_code == 422 and r.json()["error"] == "bad_code"
    assert (await account_row(maker)).session_encrypted is None            # nothing stored on failure
    assert (await api("POST", "/login/code", {"code": "12345"})).status_code == 200


async def test_too_many_wrong_codes_cancel_the_login(api, factory):
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    codes = []
    for _ in range(5):
        codes.append((await api("POST", "/login/code", {"code": "00000"})).status_code)
    assert codes == [422, 422, 422, 422, 429]
    r = await api("POST", "/login/code", {"code": "12345"})                # even the right code is refused now
    assert r.status_code == 404 and r.json()["error"] == "no_pending_login"


@pytest.mark.parametrize("bad", ["12", "abcdef", "", "1" * 30])
async def test_malformed_code_is_rejected_without_echo(api, factory, bad):
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    r = await api("POST", "/login/code", {"code": bad})
    assert r.status_code == 422 and (bad == "" or bad not in r.text)


async def test_expired_code_drops_the_pending_login(api, factory):
    from telethon.errors import PhoneCodeExpiredError
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    factory.code_error = PhoneCodeExpiredError(request=None)
    r = await api("POST", "/login/code", {"code": "55555"})
    assert r.status_code == 422 and r.json()["error"] == "code_expired"
    assert (await api("POST", "/login/code", {"code": "12345"})).status_code == 404


async def test_pending_login_expires_after_ten_minutes(api, factory):
    await api("POST", "/consent")
    clock = [1000.0]
    runtime.logins()._clock = lambda: clock[0]
    await api("POST", "/login/start", {"phone": "+998901234567"})
    clock[0] += 601
    r = await api("POST", "/login/code", {"code": "12345"})
    assert r.status_code == 404 and r.json()["error"] == "no_pending_login"


async def test_new_code_requests_are_rate_limited(api, factory):
    await api("POST", "/consent")
    clock = [1000.0]
    runtime.logins()._clock = lambda: clock[0]
    assert (await api("POST", "/login/start", {"phone": "+998901234567"})).status_code == 200
    r = await api("POST", "/login/start", {"phone": "+998901234567"})
    assert r.status_code == 429 and r.json()["error"] == "login_cooldown" and len(factory.code_requests) == 1
    clock[0] += 61
    assert (await api("POST", "/login/start", {"phone": "+998901234567"})).status_code == 200


async def test_flood_wait_on_send_code_is_not_retried(api, factory):
    await api("POST", "/consent")
    factory.send_code_error = tg.FloodWaitError(request=None, capture=300)
    r = await api("POST", "/login/start", {"phone": "+998901234567"})
    assert r.status_code == 429 and r.json()["error"] == "flood_wait"
    assert factory.code_requests == [] and factory.clients[0].disconnected


async def test_cancel_login_closes_the_client(api, factory):
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    assert (await api("POST", "/login/cancel")).status_code == 200
    assert factory.clients[0].disconnected
    assert (await api("POST", "/login/code", {"code": "12345"})).status_code == 404


# ------------------------------------------------------------------ login: 2FA path

async def test_two_factor_login_never_stores_or_logs_the_password(api, maker, factory, settings, caplog):
    factory.needs_password = True
    caplog.set_level(logging.DEBUG)
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    r = await api("POST", "/login/code", {"code": "12345"})
    assert r.json() == {"status": "password_required"}
    assert (await account_row(maker)).session_encrypted is None            # not connected until 2FA passes
    bad = await api("POST", "/login/password", {"password": "wrong-pass"})
    assert bad.status_code == 422 and bad.json()["error"] == "bad_password"
    ok = await api("POST", "/login/password", {"password": factory.good_password})
    assert ok.status_code == 200 and ok.json()["connected"] is True
    acc = await account_row(maker)
    assert crypto.decrypt_session(settings, acc.session_encrypted) == SESSION_PLAIN
    dump = await all_db_text(maker)
    for secret in (factory.good_password, "wrong-pass", "12345", SESSION_PLAIN):
        assert secret not in dump and secret not in caplog.text and secret not in ok.text and secret not in bad.text


async def test_password_before_it_is_requested_is_refused(api, factory):
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    r = await api("POST", "/login/password", {"password": factory.good_password})
    assert r.status_code == 403 and r.json()["error"] == "password_not_requested"


async def test_too_many_wrong_passwords_cancel_the_login(api, factory):
    factory.needs_password = True
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    await api("POST", "/login/code", {"code": "12345"})
    statuses = [(await api("POST", "/login/password", {"password": "nope"})).status_code for _ in range(5)]
    assert statuses == [422, 422, 422, 422, 429]


async def test_password_validation_error_does_not_echo_the_value(api, factory):
    await api("POST", "/consent")
    r = await api("POST", "/login/password", {"pw": "topsecret-value"})       # wrong field name -> FastAPI 422
    assert r.status_code == 422 and "topsecret-value" not in r.text


# ------------------------------------------------------------------ groups

async def connected_api(api, maker):
    await api("POST", "/consent")
    await api("POST", "/login/start", {"phone": "+998901234567"})
    assert (await api("POST", "/login/code", {"code": "12345"})).status_code == 200


async def test_sync_lists_groups_off_then_driver_selects(api, maker, factory):
    await connected_api(api, maker)
    r = await api("POST", "/groups/sync")
    groups = r.json()["groups"]
    assert [g["chat_id"] for g in groups] == [-1001, -1002, -1003] and not any(g["enabled"] for g in groups)
    r = await api("PUT", "/groups", {"chat_ids": [-1001, -1003]})
    assert [g["enabled"] for g in r.json()["groups"]] == [True, False, True]
    r = await api("PATCH", f"/groups/{groups[1]['id']}", {"enabled": True})
    assert r.status_code == 200
    r = await api("PUT", "/groups", {"chat_ids": [-9999]})                 # not one of the driver's groups
    assert r.status_code == 404 and r.json()["error"] == "group_not_found"


async def test_sync_requires_a_connected_account(api, factory):
    await api("POST", "/consent")
    r = await api("POST", "/groups/sync")
    assert r.status_code == 404 or r.json()["error"] == "not_connected"


async def test_sync_removes_groups_the_driver_left(api, maker, factory):
    await connected_api(api, maker)
    await api("POST", "/groups/sync")
    factory.groups = [GroupInfo(-1001, "Samarqand taksi (yangi nom)")]
    r = await api("POST", "/groups/sync")
    assert [(g["chat_id"], g["title"]) for g in r.json()["groups"]] == [(-1001, "Samarqand taksi (yangi nom)")]


async def test_pro_plan_limit_is_15_groups(s, paid_settings, make_api, factory, maker):
    d = await make_driver(s, paid_settings, plan=Plan.PRO)
    a = await make_api(paid_settings, d.user.tg_id)
    factory.groups = [GroupInfo(-2000 - i, f"G{i}") for i in range(20)]
    await connected_api(a, maker)
    await a("POST", "/groups/sync")
    ok = await a("PUT", "/groups", {"chat_ids": [-2000 - i for i in range(15)]})
    assert ok.status_code == 200
    over = await a("PUT", "/groups", {"chat_ids": [-2000 - i for i in range(16)]})
    assert over.status_code == 403 and over.json()["error"] == "group_limit"
    gid = next(g["id"] for g in ok.json()["groups"] if not g["enabled"])
    one_more = await a("PATCH", f"/groups/{gid}", {"enabled": True})       # the 16th, one at a time
    assert one_more.status_code == 403 and one_more.json()["error"] == "group_limit"


async def test_business_has_unlimited_groups_and_free_period_counts_as_business(api, maker, factory):
    factory.groups = [GroupInfo(-3000 - i, f"G{i}") for i in range(30)]
    await connected_api(api, maker)                                        # `api` runs in the free period
    await api("POST", "/groups/sync")
    r = await api("PUT", "/groups", {"chat_ids": [-3000 - i for i in range(30)]})
    assert r.status_code == 200 and sum(g["enabled"] for g in r.json()["groups"]) == 30


async def test_basic_plan_cannot_enable_any_group(s, paid_settings, make_api, factory, maker):
    d = await make_driver(s, paid_settings, plan=Plan.PRO)
    a = await make_api(paid_settings, d.user.tg_id)
    await connected_api(a, maker)
    await a("POST", "/groups/sync")
    async with maker() as s2:
        drv = await s2.get(type(d), d.id)
        drv.plan = Plan.BASIC                                              # downgraded afterwards
        await s2.commit()
    r = await a("PUT", "/groups", {"chat_ids": [-1001]})
    assert r.status_code == 403 and r.json()["error"] == "plan_required"


async def test_sync_flood_wait_is_recorded_and_not_retried(api, maker, factory):
    await connected_api(api, maker)
    factory.list_error = tg.FloodWaitError(request=None, capture=90)
    r = await api("POST", "/groups/sync")
    assert r.status_code == 429 and r.json()["error"] == "flood_wait"
    acc = await account_row(maker)
    assert acc.status == UserbotStatus.FLOOD_WAIT and acc.flood_until > utcnow()
    factory.list_error = None
    again = await api("POST", "/groups/sync")                              # still within the wait: Telegram not contacted
    assert again.status_code == 429
    assert len([c for c in factory.clients if c.session == SESSION_PLAIN]) == 1


async def test_sync_with_revoked_session_stops_the_account(api, maker, factory, bus):
    await connected_api(api, maker)
    factory.list_error = tg.AuthKeyUnregisteredError(request=None)
    r = await api("POST", "/groups/sync")
    assert r.status_code == 403 and r.json()["error"] == "session_revoked"
    acc = await account_row(maker)
    assert acc.status == UserbotStatus.STOPPED and acc.session_encrypted is None
    assert bus.published and bus.published[-1].account_id == acc.id


# ------------------------------------------------------------------ settings (decision 48)

async def test_interval_below_safe_default_needs_acknowledgement(api, maker, factory):
    await connected_api(api, maker)
    r = await api("PUT", "/settings", {"interval_minutes": 20})
    assert r.status_code == 403 and r.json()["error"] == "risk_ack_required"
    acc = await account_row(maker)
    assert acc.min_interval_minutes == 45 and acc.risk_acknowledged is False   # unchanged
    r = await api("PUT", "/settings", {"interval_minutes": 20, "acknowledge_risk": True})
    assert r.status_code == 200 and r.json()["interval_minutes"] == 20 and r.json()["risk_acknowledged"] is True


async def test_interval_floor_and_normal_changes(api, maker, factory):
    await connected_api(api, maker)
    r = await api("PUT", "/settings", {"interval_minutes": 2, "acknowledge_risk": True})
    assert r.status_code == 422 and r.json()["error"] == "interval_too_low"
    r = await api("PUT", "/settings", {"interval_minutes": 90, "daily_max_posts": 10})
    assert r.status_code == 200 and r.json()["interval_minutes"] == 90 and r.json()["daily_max_posts"] == 10
    assert (await api("PUT", "/settings", {"daily_max_posts": 0})).status_code == 422
    r = await api("PUT", "/settings", {"clear_daily_cap": True})
    assert r.json()["daily_max_posts"] is None


async def test_lowering_jitter_also_needs_acknowledgement(api, maker, factory):
    await connected_api(api, maker)
    assert (await api("PUT", "/settings", {"jitter_minutes": 1})).status_code == 403
    assert (await api("PUT", "/settings", {"jitter_minutes": 1, "acknowledge_risk": True})).status_code == 200


# ------------------------------------------------------------------ template

async def test_template_roundtrip_and_preview(api, maker, factory):
    await connected_api(api, maker)
    assert (await api("GET", "/template")).json() == {"template": None, "preview": None}
    r = await api("PUT", "/template", {"from": "Samarqand", "to": "Toshkent", "time": "08:00", "seats": 3, "price": 120000})
    assert r.status_code == 200 and "@tulporgobot" in r.json()["preview"]
    g = (await api("GET", "/template")).json()
    assert g["template"] == {"from": "Samarqand", "to": "Toshkent", "time": "08:00", "seats": 3, "price": 120000}


@pytest.mark.parametrize("field,value", [("from", "https://spam.example"), ("to", "@kanal"), ("time", "t.me/x"),
                                         ("seats", 12)])
async def test_template_rejects_links_and_bad_values(api, maker, factory, field, value):
    await connected_api(api, maker)
    body = {"from": "A", "to": "B", "time": "08:00", "seats": 3, field: value}
    r = await api("PUT", "/template", body)
    assert r.status_code == 422 and r.json()["error"] == "bad_template"
    assert (await api("GET", "/template")).json()["template"] is None


# ------------------------------------------------------------------ pause / resume / logout

async def test_pause_and_resume(api, maker, factory):
    await connected_api(api, maker)
    assert (await api("POST", "/pause")).json()["status"] == UserbotStatus.PAUSED
    assert (await api("POST", "/resume")).json()["status"] == UserbotStatus.CONNECTED


async def test_resume_cannot_cut_a_flood_wait_short(api, maker, factory):
    await connected_api(api, maker)
    async with maker() as s2:
        acc = (await s2.execute(select(UserbotAccount))).scalars().first()
        acc.status, acc.flood_until = UserbotStatus.FLOOD_WAIT, utcnow() + timedelta(hours=1)
        await s2.commit()
    r = await api("POST", "/resume")
    assert r.status_code == 403 and r.json()["error"] == "flood_wait_active"
    # pause + resume does not shorten it either
    await api("POST", "/pause")
    assert (await api("POST", "/resume")).json()["status"] == UserbotStatus.FLOOD_WAIT


async def test_stopped_account_cannot_be_resumed(api, maker, factory):
    await connected_api(api, maker)
    async with maker() as s2:
        acc = (await s2.execute(select(UserbotAccount))).scalars().first()
        acc.status = UserbotStatus.STOPPED
        await s2.commit()
    r = await api("POST", "/resume")
    assert r.status_code == 403 and r.json()["error"] == "needs_login"


async def test_logout_deletes_the_session_everywhere(api, maker, factory):
    await connected_api(api, maker)
    await api("POST", "/groups/sync")
    await api("PUT", "/groups", {"chat_ids": [-1001]})
    r = await api("POST", "/logout")
    assert r.status_code == 200 and r.json()["connected"] is False and r.json()["groups"] == []
    assert factory.logged_out_sessions == [SESSION_PLAIN]                  # ended on Telegram's side
    acc = await account_row(maker)
    assert acc.session_encrypted is None and acc.tg_user_id is None and acc.status == UserbotStatus.NEEDS_LOGIN
    assert acc.consent_at is None                                          # the risk screen is shown again
    assert SESSION_PLAIN not in await all_db_text(maker)
    # after logout no login is possible without a fresh consent (negative)
    r = await api("POST", "/login/start", {"phone": "+998901234567"})
    assert r.status_code == 403 and r.json()["error"] == "consent_required"


async def test_logout_deletes_locally_even_if_telegram_call_fails(api, maker, factory):
    await connected_api(api, maker)
    factory.logout_error = ConnectionError("network down")
    r = await api("POST", "/logout")
    assert r.status_code == 200
    assert (await account_row(maker)).session_encrypted is None


async def test_logout_works_without_telegram_credentials(s, settings, make_api, maker, monkeypatch):
    monkeypatch.delenv("TULPORGO_TELEGRAM_API_ID", raising=False)
    runtime.set_factory(None)
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=2)
    a = await make_api(settings, d.user.tg_id)
    r = await a("POST", "/logout")
    assert r.status_code == 200
    acc = await account_row(maker)
    assert acc.session_encrypted is None and r.json()["groups"] == []


async def test_status_never_exposes_the_session(api, maker, factory):
    await connected_api(api, maker)
    body = (await api("GET", "/status")).text
    assert "session_encrypted" not in body
    assert SESSION_PLAIN not in body
    assert "gAAAA" not in body                                              # no Fernet token either
