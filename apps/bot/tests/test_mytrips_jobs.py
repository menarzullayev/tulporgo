"""/qatnovlarim and the background jobs (expiry, weekly KPI report)."""
from datetime import datetime, timedelta

from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import new_request, offer_by_ui, tx
from sqlalchemy import select, update
from tulporgo_bot import delivery, jobs
from tulporgo_bot.handlers import setup
from tulporgo_core.db import utcnow
from tulporgo_core.models import Offer, RideRequest, Trip

PHONE = "+998901234567"


async def accepted_trip(env):
    await env.user(1, name="Pas", username="pas", phone=PHONE)
    await env.driver(2, name="Drv", username="drv")
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(1, f"oa:{oid}")
    trip = await env.db(lambda s: s.scalar(select(Trip)))
    return rid, oid, trip


# ---------- /qatnovlarim ----------

async def test_empty_lists(env):
    await env.user(1)
    await env.say(1, "/qatnovlarim")
    assert tx("bot.my.empty") in env.last_text(1)


async def test_passenger_sees_and_cancels_open_requests(env):
    await env.user(1)
    rid = await new_request(env, 1)
    await env.say(1, "/qatnovlarim")
    assert tx("bot.my.open_requests") in env.last_text(1) and f"rq:c:{rid}" in env.buttons(1)
    await env.press(1, f"rq:c:{rid}")
    assert (await env.db(lambda s: s.get(RideRequest, rid))).status == "cancelled"
    await env.press(1, f"rq:c:{rid}")                                         # again
    assert env.alerts()[-1] == tx("bot.err.request_not_open")


async def test_nobody_else_can_cancel_my_request(env):
    await env.user(1)
    await env.user(9)
    rid = await new_request(env, 1)
    await env.press(9, f"rq:c:{rid}")
    assert env.alerts()[-1] == tx("bot.err.not_your_request")
    assert (await env.db(lambda s: s.get(RideRequest, rid))).status == "open"
    await env.press(9, "rq:c:abc")                                            # tampered data is ignored silently
    await env.press(9, "rq:c:99999")
    assert env.alerts()[-1] == tx("bot.err.request_not_found")


async def test_trips_listed_for_both_sides_and_card_can_be_reopened(env):
    rid, oid, trip = await accepted_trip(env)
    await env.say(1, "/qatnovlarim")
    assert tx("bot.my.trips") in env.last_text(1) and tx("bot.status.confirmed") in env.last_text(1)
    assert f"mt:{trip.id}" in env.buttons(1)
    n = len(env.sent(1, ("SendRichMessage",)))
    await env.press(1, f"mt:{trip.id}")
    card = env.sent(1, ("SendRichMessage",))[-1]
    assert len(env.sent(1, ("SendRichMessage",))) == n + 1 and "@drv" in repr(card.rich_message.blocks)   # passenger view
    await env.say(2, "/qatnovlarim")
    assert tx("bot.my.drive_trips") in env.last_text(2) and f"mt:{trip.id}" in env.buttons(2)
    await env.press(2, f"mt:{trip.id}")
    assert "@pas" in repr(env.sent(2, ("SendRichMessage",))[-1].rich_message.blocks)                  # driver view


async def test_other_people_cannot_open_my_trip_card(env):
    rid, oid, trip = await accepted_trip(env)
    await env.user(9)
    await env.press(9, f"mt:{trip.id}")
    assert env.alerts()[-1] == tx("bot.err.not_your_trip") and env.sent(9) == []


async def test_driver_sees_open_offers_and_can_withdraw(env):
    await env.user(1)
    await env.driver(2)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.say(2, "/qatnovlarim")
    assert tx("bot.my.offers") in env.last_text(2) and f"ow:{oid}" in env.buttons(2)
    await env.press(2, f"ow:{oid}")
    assert (await env.db(lambda s: s.get(Offer, oid))).status == "withdrawn"
    await env.say(2, "/qatnovlarim")
    assert tx("bot.my.offers") not in env.last_text(2)


async def test_finished_trip_has_no_open_button(env):
    rid, oid, trip = await accepted_trip(env)
    await env.press(1, f"tc:{trip.id}")
    await env.say(1, "/qatnovlarim")
    assert f"mt:{trip.id}" not in env.buttons(1) and tx("bot.status.completed") in env.last_text(1)


# ---------- expiry job ----------

async def test_expire_job_closes_only_overdue_requests_and_tells_passengers(env):
    await env.user(1)
    old, fresh = await new_request(env, 1), await new_request(env, 1)
    await env.db(lambda s: s.execute(update(RideRequest).where(RideRequest.id == old)
                                     .values(expires_at=utcnow() - timedelta(minutes=1))))
    ids = await jobs.expire_once(env.bot, env.maker, env.bus)
    assert ids == [old]
    assert (await env.db(lambda s: s.get(RideRequest, old))).status == "expired"
    assert (await env.db(lambda s: s.get(RideRequest, fresh))).status == "open"
    assert env.said(1, tx("bot.order.expired", route="Qo'shrabot → Samarqand"))
    assert any(type(e).__name__ == "RequestClosed" and e.request_id == old for e in env.bus.published)
    n = len(env.fake.calls)
    assert await jobs.expire_once(env.bot, env.maker, env.bus) == [] and len(env.fake.calls) == n   # idempotent


async def test_expired_request_drivers_cannot_offer_any_more(env):
    await env.user(1)
    await env.driver(2)
    rid = await new_request(env, 1)
    await env.db(lambda s: s.execute(update(RideRequest).where(RideRequest.id == rid)
                                     .values(expires_at=utcnow() - timedelta(minutes=1))))
    await jobs.expire_once(env.bot, env.maker, env.bus)
    await env.press(2, f"ofq:{rid}:40000")
    assert env.alerts()[-1] == tx("bot.err.request_not_open")


# ---------- weekly KPI report ----------

def test_next_weekly_run_is_monday_nine_tashkent():
    mon_0300 = datetime(2026, 11, 9, 3, 0)          # Monday 08:00 in Tashkent → today 09:00 (= 04:00 UTC)
    assert jobs.next_weekly_run(mon_0300) == datetime(2026, 11, 9, 4, 0)
    assert jobs.next_weekly_run(datetime(2026, 11, 9, 4, 0)) == datetime(2026, 11, 16, 4, 0)      # strictly after "now"
    assert jobs.next_weekly_run(datetime(2026, 11, 9, 5, 0)) == datetime(2026, 11, 16, 4, 0)
    assert jobs.next_weekly_run(datetime(2026, 11, 15, 23, 0)) == datetime(2026, 11, 16, 4, 0)    # Sunday night
    assert jobs.next_weekly_run(datetime(2026, 11, 15, 19, 30)) == datetime(2026, 11, 16, 4, 0)   # Mon 00:30 local


def test_next_weekly_run_other_weekday_and_hour():
    assert jobs.next_weekly_run(datetime(2026, 11, 9, 0, 0), weekday=2, hour=18) == datetime(2026, 11, 11, 13, 0)


async def test_weekly_report_goes_to_the_owner_in_the_new_alphabet(tmp_path):
    from bot_harness import Env
    env = await Env(tmp_path, owner_chat_id=4242).start()
    try:
        await env.driver(2)
        assert await jobs.weekly_report(env.bot, env.maker, env.settings) is True
        text = env.last_text(4242)
        assert "haftalik KPI" in text and "maqsad" in text
        assert "Röyxatdan" in text and "Ro'yxatdan" not in text            # new alphabet (decision 29): o' → ö
    finally:
        await env.stop()


async def test_weekly_report_without_an_owner_chat_sends_nothing(env):
    assert env.settings.owner_chat_id is None
    n = len(env.fake.calls)
    assert await jobs.weekly_report(env.bot, env.maker, env.settings) is False
    assert len(env.fake.calls) == n


async def test_setup_starts_and_stops_background_jobs(env):
    runtime = await setup(bot=env.bot, maker=env.maker, settings=env.settings, bus=env.bus, jobs=True)
    try:
        # expire, weekly report, member tags, rejected-documents purge (decision 63)
        assert len(runtime.tasks) == 4 and not any(t.done() for t in runtime.tasks)
    finally:
        await runtime.stop()
    assert all(t.cancelled() or t.done() for t in runtime.tasks)
    assert delivery.LIMITER.rate == 25.0                                      # setup applies the configured rate


async def test_weekly_loop_sends_one_report_when_the_time_has_come(tmp_path, monkeypatch):
    import asyncio

    from bot_harness import Env
    env = await Env(tmp_path, owner_chat_id=4242).start()
    try:
        monkeypatch.setattr(jobs, "next_weekly_run", lambda now, weekday=0, hour=9: now - timedelta(seconds=1))

        async def stop_after_report(_):
            raise asyncio.CancelledError            # the loop's only sleep after sending ends the test
        monkeypatch.setattr(jobs.asyncio, "sleep", stop_after_report)
        try:
            await jobs.weekly_loop(env.bot, env.maker, env.settings, 0, 9)
        except asyncio.CancelledError:
            pass
        assert len(env.sent(4242)) == 1
    finally:
        await env.stop()


async def test_a_failing_job_run_does_not_kill_the_loop(monkeypatch):
    import asyncio
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    async def fake_sleep(_):
        if len(calls) >= 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(jobs.asyncio, "sleep", fake_sleep)
    try:
        await jobs.every(1, flaky, "test")
    except asyncio.CancelledError:
        pass
    assert len(calls) == 2                           # it ran again after the error
