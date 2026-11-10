"""Scheduler: posting limits and the stop rules of decisions 8 and 48. Every rule has a negative test."""
import logging
from datetime import timedelta

import pytest
from sqlalchemy import select
from telethon import errors as tg
from tulporgo_core.db import utcnow
from tulporgo_core.enums import Plan, PostStatus, UserbotStatus
from tulporgo_core.events import UserbotStopped
from tulporgo_core.models import UserbotAccount, UserbotPost
from tulporgo_userbot import crypto, service
from tulporgo_userbot.scheduler import Scheduler
from userbot_fixtures import *  # noqa: F403 - pytest fixtures
from userbot_helpers import SESSION_PLAIN, make_account, make_driver


class ZeroRng:
    def uniform(self, a, b):
        return a


class MaxRng:
    def uniform(self, a, b):
        return b


def sched(maker, settings, bus, factory, notifier, rng=None):
    return Scheduler(maker, settings, bus, factory, notifier, rng=rng or ZeroRng())


async def reload(maker, account_id):
    async with maker() as s:
        return (await s.execute(select(UserbotAccount).where(UserbotAccount.id == account_id))).scalar_one()


async def posts(maker, status=None):
    async with maker() as s:
        rows = (await s.execute(select(UserbotPost))).scalars().all()
        return [p for p in rows if status is None or p.status == status]


T0 = utcnow()


# ------------------------------------------------------------------ happy path

async def test_posts_one_group_per_tick_with_template_text(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=2)
    sc = sched(maker, settings, bus, factory, notifier)
    assert await sc.tick(T0) == 1                          # ONE post per account per tick
    assert len(factory.sent) == 1
    assert await sc.tick(T0) == 1
    assert {c for c, _ in factory.sent} == {-1001, -1002}
    text = factory.sent[0][1]
    assert "Samarqand" in text and "Toshkent" in text and "08:00" in text and "@tulporgobot" in text
    assert "http" not in text and "t.me" not in text       # never spam links
    assert len(await posts(maker, PostStatus.SENT)) == 2


async def test_session_is_decrypted_only_for_the_client(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    assert SESSION_PLAIN not in acc.session_encrypted      # stored only as a Fernet token
    await sched(maker, settings, bus, factory, notifier).tick(T0)
    assert factory.clients[0].session == SESSION_PLAIN and factory.clients[0].connected


# ------------------------------------------------------------------ consent / plan / template (negatives)

async def test_no_post_before_consent(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, consent=False)
    assert await sched(maker, settings, bus, factory, notifier).tick(T0) == 0
    assert factory.send_calls == 0 and factory.clients == []


async def test_no_post_without_template(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, with_template=False)
    assert await sched(maker, settings, bus, factory, notifier).tick(T0) == 0
    assert factory.send_calls == 0


async def test_corrupt_template_does_not_crash_or_post(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d)
    acc.post_template = "{not json"
    await s.commit()
    assert await sched(maker, settings, bus, factory, notifier).tick(T0) == 0


@pytest.mark.parametrize("status", [UserbotStatus.NEEDS_LOGIN, UserbotStatus.PAUSED, UserbotStatus.STOPPED])
async def test_only_connected_accounts_post(s, maker, settings, bus, factory, notifier, status):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, status=status)
    assert await sched(maker, settings, bus, factory, notifier).tick(T0) == 0
    assert factory.send_calls == 0


async def test_account_without_session_never_posts(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d)
    acc.session_encrypted = None
    await s.commit()
    assert await sched(maker, settings, bus, factory, notifier).tick(T0) == 0


@pytest.mark.parametrize("plan,subscribed", [(None, True), (Plan.BASIC, True), (Plan.PRO, False)])
async def test_plan_without_autopost_never_posts(s, maker, paid_settings, bus, factory, notifier, plan, subscribed):
    # trial (no plan yet) = Basic; Basic has no auto-post; an expired Pro subscription has no plan at all
    d = await make_driver(s, paid_settings, plan=plan, subscribed=subscribed)
    await make_account(s, paid_settings, d, groups=3)
    assert await sched(maker, paid_settings, bus, factory, notifier).tick(T0) == 0
    assert factory.send_calls == 0


async def test_pro_posts_at_most_15_groups(s, maker, paid_settings, bus, factory, notifier):
    d = await make_driver(s, paid_settings, plan=Plan.PRO)
    await make_account(s, paid_settings, d, groups=20)
    sc = sched(maker, paid_settings, bus, factory, notifier)
    for _ in range(30):
        await sc.tick(T0)
    assert len({c for c, _ in factory.sent}) == 15 and len(factory.sent) == 15


async def test_business_and_free_period_have_no_group_limit(s, maker, settings, paid_settings, bus, factory, notifier):
    d = await make_driver(s, paid_settings, plan=Plan.BUSINESS)
    await make_account(s, paid_settings, d, groups=20)
    sc = sched(maker, paid_settings, bus, factory, notifier)
    for _ in range(25):
        await sc.tick(T0)
    assert len({c for c, _ in factory.sent}) == 20
    # free period: a driver with NO paid plan is treated as Business (decision 44)
    d2 = await make_driver(s, settings)
    await make_account(s, settings, d2, groups=17)
    factory.sent.clear()
    sc2 = sched(maker, settings, bus, factory, notifier)
    for _ in range(25):
        await sc2.tick(T0)
    assert len({c for c, _ in factory.sent}) == 17


async def test_disabled_groups_are_skipped(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=3, enabled=False)
    assert await sched(maker, settings, bus, factory, notifier).tick(T0) == 0


# ------------------------------------------------------------------ interval / jitter (decision 48)

async def test_interval_default_45_minutes(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1)
    sc = sched(maker, settings, bus, factory, notifier)
    assert await sc.tick(T0) == 1
    assert await sc.tick(T0 + timedelta(minutes=44, seconds=59)) == 0       # too early: negative
    assert await sc.tick(T0 + timedelta(minutes=45)) == 1


async def test_jitter_delays_the_next_post(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1)
    sc = sched(maker, settings, bus, factory, notifier, rng=MaxRng())       # jitter = full 15 minutes
    assert await sc.tick(T0) == 0                                            # first seen: waits its jitter
    first = T0 + timedelta(minutes=15)
    assert await sc.tick(first) == 1
    assert await sc.tick(first + timedelta(minutes=45)) == 0                 # interval over, jitter not yet
    assert await sc.tick(first + timedelta(minutes=60)) == 1


async def test_first_post_waits_for_its_jitter(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1)
    sc = sched(maker, settings, bus, factory, notifier, rng=MaxRng())
    assert await sc.tick(T0) == 0
    assert await sc.tick(T0 + timedelta(minutes=14)) == 0
    assert await sc.tick(T0 + timedelta(minutes=15)) == 1


async def test_interval_below_minimum_without_acknowledgement_is_ignored(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1, interval=10, risk=False)    # 10 stored, but no risk acknowledgement
    sc = sched(maker, settings, bus, factory, notifier)
    assert await sc.tick(T0) == 1
    assert await sc.tick(T0 + timedelta(minutes=10)) == 0                    # still held back to 45
    assert await sc.tick(T0 + timedelta(minutes=45)) == 1


async def test_interval_below_minimum_with_acknowledgement_is_honoured(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1, interval=10, risk=True)
    sc = sched(maker, settings, bus, factory, notifier)
    assert await sc.tick(T0) == 1
    assert await sc.tick(T0 + timedelta(minutes=9)) == 0
    assert await sc.tick(T0 + timedelta(minutes=10)) == 1


async def test_interval_never_below_absolute_floor(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1, interval=0, risk=True)
    sc = sched(maker, settings, bus, factory, notifier)
    assert await sc.tick(T0) == 1
    assert await sc.tick(T0 + timedelta(minutes=1)) == 0
    assert await sc.tick(T0 + timedelta(minutes=5)) == 1


async def test_daily_cap(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=3)
    acc.daily_max_posts = 2
    await s.commit()
    sc = sched(maker, settings, bus, factory, notifier)
    now = utcnow()
    for _ in range(6):
        await sc.tick(now)
    assert len(factory.sent) == 2                                            # the cap stops the third group


# ------------------------------------------------------------------ FloodWait (decision 8)

async def test_flood_wait_sets_state_notifies_and_never_retries(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=2)
    factory.send_error = tg.FloodWaitError(request=None, capture=120)
    sc = sched(maker, settings, bus, factory, notifier)
    assert await sc.tick(T0) == 0
    a = await reload(maker, acc.id)
    assert a.status == UserbotStatus.FLOOD_WAIT and a.flood_until == T0 + timedelta(seconds=120)
    assert factory.send_calls == 1                                           # exactly one attempt, no retry loop
    assert len(notifier.messages) == 1
    failed = await posts(maker, PostStatus.FAILED)
    assert len(failed) == 1 and failed[0].error == "flood_wait:120"
    assert bus.published == []                                               # flood wait is temporary: no stop event


async def test_nothing_is_sent_during_flood_wait_then_it_resumes(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    factory.send_error = tg.FloodWaitError(request=None, capture=600)
    sc = sched(maker, settings, bus, factory, notifier)
    await sc.tick(T0)
    factory.send_error = None                                                # Telegram would accept now - still wait
    for minutes in (0, 1, 5, 9):
        assert await sc.tick(T0 + timedelta(minutes=minutes)) == 0
    assert factory.send_calls == 1 and factory.sent == []
    assert await sc.tick(T0 + timedelta(seconds=601)) == 1                   # wait over: back to connected
    assert (await reload(maker, acc.id)).status == UserbotStatus.CONNECTED


async def test_flood_wait_on_one_group_blocks_the_whole_account(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=3)
    factory.send_errors = {-1001: tg.FloodWaitError(request=None, capture=60)}
    sc = sched(maker, settings, bus, factory, notifier)
    for _ in range(4):
        await sc.tick(T0)
    assert factory.send_calls == 1 and factory.sent == []


async def test_premium_flood_wait_is_treated_like_flood_wait(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    factory.send_error = tg.FloodPremiumWaitError(request=None, capture=30)
    await sched(maker, settings, bus, factory, notifier).tick(T0)
    assert (await reload(maker, acc.id)).status == UserbotStatus.FLOOD_WAIT


# ------------------------------------------------------------------ PeerFlood / bans / dead session

async def test_peer_flood_stops_the_account_for_good(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=2)
    factory.send_error = tg.PeerFloodError(request=None)
    sc = sched(maker, settings, bus, factory, notifier)
    await sc.tick(T0)
    a = await reload(maker, acc.id)
    assert a.status == UserbotStatus.STOPPED and a.stop_reason == "peer_flood"
    assert bus.published == [UserbotStopped(acc.id, "peer_flood")]
    assert "PEER_FLOOD" in notifier.messages[0][1]
    # a stopped account never posts again — even when Telegram would accept and a lot of time passes
    factory.send_error = None
    for days in (0, 1, 7, 30):
        assert await sc.tick(T0 + timedelta(days=days)) == 0
    assert factory.send_calls == 1 and factory.sent == []
    # and the driver cannot just flip it back on
    async with maker() as s2:
        a2 = await s2.get(UserbotAccount, acc.id)
        with pytest.raises(Exception) as ei:
            await service.resume(s2, a2)
        assert ei.value.code == "needs_login"


@pytest.mark.parametrize("error", [tg.AuthKeyUnregisteredError(request=None), tg.UserDeactivatedError(request=None),
                                   tg.UserDeactivatedBanError(request=None), tg.SessionRevokedError(request=None)])
async def test_dead_session_stops_account_and_drops_session(s, maker, settings, bus, factory, notifier, error):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    factory.send_error = error
    await sched(maker, settings, bus, factory, notifier).tick(T0)
    a = await reload(maker, acc.id)
    assert a.status == UserbotStatus.STOPPED and a.session_encrypted is None
    assert isinstance(bus.published[0], UserbotStopped) and len(notifier.messages) == 1


async def test_unauthorized_client_stops_account(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    factory.authorized = False
    await sched(maker, settings, bus, factory, notifier).tick(T0)
    a = await reload(maker, acc.id)
    assert a.status == UserbotStatus.STOPPED and factory.send_calls == 0


@pytest.mark.parametrize("error", [tg.ChatWriteForbiddenError(request=None), tg.UserBannedInChannelError(request=None)])
async def test_group_ban_stops_only_that_group(s, maker, settings, bus, factory, notifier, error):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=2)
    factory.send_errors = {-1001: error}
    sc = sched(maker, settings, bus, factory, notifier)
    await sc.tick(T0)                                                        # group 1 fails -> disabled
    await sc.tick(T0)                                                        # group 2 posts
    for _ in range(3):
        await sc.tick(T0 + timedelta(hours=3))
    a = await reload(maker, acc.id)
    assert a.status == UserbotStatus.CONNECTED                               # the account itself keeps working
    async with maker() as s2:
        groups = (await s2.execute(select(UserbotAccount).where(UserbotAccount.id == acc.id))).scalar_one()
        await s2.refresh(groups, ["groups"])
        by = {g.chat_id: g.enabled for g in groups.groups}
    assert by == {-1001: False, -1002: True}
    assert all(c == -1002 for c, _ in factory.sent)                          # never tried the banned group again
    assert factory.send_calls == 1 + len(factory.sent)
    assert any(isinstance(e, UserbotStopped) and e.reason.startswith("group:-1001:") for e in bus.published)
    assert "Guruh 1" in notifier.messages[0][1]


async def test_unknown_error_is_not_retried_in_a_loop(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1)
    factory.send_error = RuntimeError("boom")
    sc = sched(maker, settings, bus, factory, notifier)
    for _ in range(5):
        await sc.tick(T0)
    assert factory.send_calls == 1                                           # backed off for the full interval
    assert await sc.tick(T0 + timedelta(minutes=46)) == 0
    assert factory.send_calls == 2
    assert all(p.status == PostStatus.FAILED for p in await posts(maker))


async def test_slow_mode_backs_off_that_group_only(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    factory.send_error = tg.SlowModeWaitError(request=None, capture=300)
    sc = sched(maker, settings, bus, factory, notifier)
    await sc.tick(T0)
    factory.send_error = None
    assert await sc.tick(T0 + timedelta(seconds=299)) == 0
    assert await sc.tick(T0 + timedelta(seconds=300)) == 1
    assert (await reload(maker, acc.id)).status == UserbotStatus.CONNECTED


async def test_wrong_encryption_key_stops_account_without_leaking(s, maker, settings, bus, factory, notifier, caplog):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    other = settings.model_copy(update={"userbot_encryption_key": crypto.generate_key()})
    with caplog.at_level(logging.DEBUG):
        await sched(maker, other, bus, factory, notifier).tick(T0)
    assert (await reload(maker, acc.id)).status == UserbotStatus.STOPPED
    assert factory.send_calls == 0 and SESSION_PLAIN not in caplog.text


# ------------------------------------------------------------------ pause / disconnect / logging

async def test_paused_account_disconnects_its_client_and_stays_silent(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d, groups=1)
    sc = sched(maker, settings, bus, factory, notifier)
    await sc.tick(T0)
    client = factory.clients[0]
    async with maker() as s2:
        await service.pause(s2, await s2.get(UserbotAccount, acc.id))
        await s2.commit()
    assert await sc.tick(T0 + timedelta(hours=2)) == 0
    assert client.disconnected and len(factory.sent) == 1


async def test_notifications_follow_the_driver_language(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings, lang="ru")
    await make_account(s, settings, d, groups=1)
    factory.send_error = tg.PeerFloodError(request=None)
    await sched(maker, settings, bus, factory, notifier).tick(T0)
    assert "Telegram ограничил" in notifier.messages[0][1]


async def test_secrets_never_reach_logs(s, maker, settings, bus, factory, notifier, caplog):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1)
    factory.send_error = tg.PeerFloodError(request=None)
    with caplog.at_level(logging.DEBUG):
        await sched(maker, settings, bus, factory, notifier).tick(T0)
    assert SESSION_PLAIN not in caplog.text and settings.userbot_encryption_key not in caplog.text


async def test_close_disconnects_all_clients(s, maker, settings, bus, factory, notifier):
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=1)
    sc = sched(maker, settings, bus, factory, notifier)
    await sc.tick(T0)
    await sc.close()
    assert factory.clients[0].disconnected
