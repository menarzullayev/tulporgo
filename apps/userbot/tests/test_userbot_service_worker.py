"""Service rules, integration points and the worker loop."""
import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from tulporgo_core.db import utcnow
from tulporgo_core.enums import UserbotStatus
from tulporgo_core.errors import DomainError
from tulporgo_core.events import PaymentConfirmed, UserbotStopped
from tulporgo_core.models import UserbotAccount, UserbotGroup, UserbotPost
from tulporgo_userbot import service
from tulporgo_userbot.scheduler import Scheduler
from tulporgo_userbot.worker import Worker
from userbot_fixtures import *  # noqa: F403 - pytest fixtures
from userbot_helpers import make_account, make_driver


def acc(**kw) -> UserbotAccount:
    base = dict(driver_id=1, min_interval_minutes=45, jitter_minutes=15, risk_acknowledged=False)
    base.update(kw)
    return UserbotAccount(**base)


# ------------------------------------------------------------------ limits

@pytest.mark.parametrize("stored,ack,expected", [(45, False, 45), (10, False, 45), (90, False, 90), (10, True, 10),
                                                 (2, True, 5), (0, True, 5)])
def test_effective_interval(settings, stored, ack, expected):
    assert service.effective_interval(acc(min_interval_minutes=stored, risk_acknowledged=ack), settings) == expected


def test_effective_jitter_needs_acknowledgement_to_shrink(settings):
    assert service.effective_jitter(acc(jitter_minutes=0), settings) == 15
    assert service.effective_jitter(acc(jitter_minutes=0, risk_acknowledged=True), settings) == 0
    assert service.effective_jitter(acc(jitter_minutes=30), settings) == 30


async def test_update_limits_refusal_changes_nothing(s, settings):
    d = await make_driver(s, settings)
    a = await make_account(s, settings, d)
    with pytest.raises(DomainError) as e:
        await service.update_limits(s, a, settings, interval_minutes=30, daily_max_posts=5)
    assert e.value.code == "risk_ack_required"
    assert (a.min_interval_minutes, a.daily_max_posts, a.risk_acknowledged) == (45, None, False)


async def test_raising_the_interval_needs_no_acknowledgement(s, settings):
    d = await make_driver(s, settings)
    a = await make_account(s, settings, d)
    await service.update_limits(s, a, settings, interval_minutes=120)
    assert a.min_interval_minutes == 120 and a.risk_acknowledged is False


def test_daily_cap_counts_the_tashkent_day():
    now = datetime(2026, 11, 10, 20, 0)                       # 01:00 on 11 Nov in Tashkent (UTC+5)
    assert service.day_start_utc(now) == datetime(2026, 11, 10, 19, 0)
    assert service.day_start_utc(datetime(2026, 11, 10, 3, 0)) == datetime(2026, 11, 9, 19, 0)


async def test_posts_today_counts_only_sent_posts_of_today(s, settings):
    d = await make_driver(s, settings)
    a = await make_account(s, settings, d, groups=1)
    gid = a.groups[0].id
    now = utcnow()
    s.add_all([UserbotPost(group_id=gid, status="sent", created_at=now),
               UserbotPost(group_id=gid, status="failed", created_at=now),
               UserbotPost(group_id=gid, status="sent", created_at=now - timedelta(days=2))])
    await s.commit()
    assert await service.posts_today(s, a, now) == 1


# ------------------------------------------------------------------ consent / groups / status

async def test_consent_is_idempotent_and_uses_safe_defaults(s, settings):
    d = await make_driver(s, settings)
    a1 = await service.accept_consent(s, d, settings)
    await s.commit()
    a2 = await service.accept_consent(s, d, settings)
    assert a1.id == a2.id and (a1.min_interval_minutes, a1.jitter_minutes) == (45, 15) and not a1.risk_acknowledged
    assert a1.status == UserbotStatus.NEEDS_LOGIN and a1.session_encrypted is None


def test_require_consent_rejects_missing_and_empty():
    with pytest.raises(DomainError) as e:
        service.require_consent(None)
    assert e.value.code == "consent_required"
    with pytest.raises(DomainError):
        service.require_consent(acc(consent_at=None))


async def test_finish_login_requires_consent_and_encrypts(s, settings):
    d = await make_driver(s, settings)
    a = await make_account(s, settings, d, consent=False)
    with pytest.raises(DomainError):
        await service.finish_login(s, a, settings, "SESSION", 5)
    a.consent_at = utcnow()
    await service.finish_login(s, a, settings, "SESSION", 5)
    assert a.session_encrypted != "SESSION" and "SESSION" not in a.session_encrypted and a.status == "connected"


async def test_finish_login_clears_an_old_stop(s, settings):
    d = await make_driver(s, settings)
    a = await make_account(s, settings, d, status=UserbotStatus.STOPPED)
    a.stop_reason = "peer_flood"
    await service.finish_login(s, a, settings, "NEW", 9)
    assert a.status == UserbotStatus.CONNECTED and a.stop_reason is None


async def test_sync_keeps_enabled_flags_and_adds_new_groups_off(s, settings):
    from tulporgo_userbot.client import GroupInfo
    d = await make_driver(s, settings)
    a = await make_account(s, settings, d, groups=1, enabled=True)
    await service.sync_groups(s, a, [GroupInfo(-1001, "Renamed"), GroupInfo(-5, "New")])
    by = {g.chat_id: (g.title, g.enabled) for g in a.groups}
    assert by == {-1001: ("Renamed", True), -5: ("New", False)}


async def test_status_view_without_account_and_without_secrets(s, settings):
    d = await make_driver(s, settings)
    v = service.status_view(None, d, settings)
    assert v["consent"] is False and v["connected"] is False and v["groups"] == []
    a = await make_account(s, settings, d)
    text = repr(service.status_view(a, d, settings))
    assert "session" not in text and "gAAAA" not in text


async def test_disconnect_deletes_posts_groups_and_session(s, maker, settings, factory):
    d = await make_driver(s, settings)
    a = await make_account(s, settings, d, groups=2)
    s.add(UserbotPost(group_id=a.groups[0].id, status="sent"))
    await s.commit()
    await service.disconnect_account(s, a, settings, factory)
    await s.commit()
    async with maker() as s2:
        assert (await s2.execute(select(UserbotPost))).first() is None
        assert (await s2.execute(select(UserbotGroup))).first() is None
        row = (await s2.execute(select(UserbotAccount))).scalars().one()
        assert row.session_encrypted is None and row.consent_at is None
    assert factory.clients[0].disconnected and factory.clients[0].logged_out


# ------------------------------------------------------------------ integration points

def test_api_app_mounts_the_userbot_router(maker, bus, settings):
    from tulporgo_api.main import create_app
    paths = set(create_app(settings, maker=maker, bus=bus).openapi()["paths"])
    assert {"/api/userbot/login/start", "/api/userbot/login/code", "/api/userbot/login/password",
            "/api/userbot/logout"} <= paths


def test_bot_and_api_integration_points_resolve():
    """The bot includes `tulporgo_userbot.bot:router` (aiogram Router); the API includes `tulporgo_userbot.api:router`;
    the worker runs as `python -m tulporgo_userbot`."""
    import importlib

    from aiogram import Router
    from fastapi import APIRouter
    from tulporgo_api.main import OPTIONAL_ROUTERS as API_ROUTERS
    from tulporgo_bot.main import OPTIONAL_ROUTERS as BOT_ROUTERS
    assert "tulporgo_userbot.bot:router" in BOT_ROUTERS and "tulporgo_userbot.api:router" in API_ROUTERS
    assert isinstance(importlib.import_module("tulporgo_userbot.bot").router, Router)
    assert isinstance(importlib.import_module("tulporgo_userbot.api").router, APIRouter)
    assert importlib.util.find_spec("tulporgo_userbot.__main__") is not None


# ------------------------------------------------------------------ worker

class CountingScheduler:
    def __init__(self, fail_first: bool = False) -> None:
        self.ticks = 0
        self.forgotten: list[int] = []
        self.closed = False
        self.fail_first = fail_first

    async def tick(self):
        self.ticks += 1
        if self.fail_first and self.ticks == 1:
            raise RuntimeError("tick blew up")
        return 0

    async def forget(self, account_id):
        self.forgotten.append(account_id)

    async def close(self):
        self.closed = True


async def test_worker_loops_survives_errors_and_shuts_down_gracefully(bus):
    sched = CountingScheduler(fail_first=True)
    w = Worker(sched, bus, tick_seconds=0.01)
    task = asyncio.create_task(w.run())
    await asyncio.sleep(0.15)
    w.stop.set()
    await asyncio.wait_for(task, 2)
    assert sched.ticks >= 3 and sched.closed                       # the first failure did not end the loop


async def test_worker_drops_the_client_on_userbot_stopped_and_wakes_on_plan_change(bus):
    sched = CountingScheduler()
    w = Worker(sched, bus, tick_seconds=30)
    task = asyncio.create_task(w.run())
    await asyncio.sleep(0.05)
    assert sched.ticks == 1
    await bus.publish(UserbotStopped(account_id=7, reason="peer_flood"))
    await asyncio.sleep(0.05)
    assert sched.forgotten == [7] and sched.ticks == 2             # woken immediately, not after 30 s
    await bus.publish(PaymentConfirmed(payment_id=1))
    await asyncio.sleep(0.05)
    assert sched.ticks == 3
    w.stop.set()
    await asyncio.wait_for(task, 2)


async def test_worker_stops_promptly_even_with_a_long_tick_interval(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1)
    sched = Scheduler(maker, settings, bus, factory, notifier)
    w = Worker(sched, bus, tick_seconds=3600)
    task = asyncio.create_task(w.run())
    await asyncio.sleep(0.3)
    w.stop.set()
    await asyncio.wait_for(task, 3)
    assert all(c.disconnected for c in factory.clients)            # sessions are closed on shutdown
