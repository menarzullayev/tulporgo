"""/malumotlarim (privacy policy §8): export as a file, delete only after a confirmation, never during a trip."""
import json

from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import tx
from sqlalchemy import select
from tulporgo_core.enums import UserbotStatus
from tulporgo_core.models import Driver, RideRequest, Trip, User, UserbotAccount
from tulporgo_core.services import rides

SESSION = "gAAAAAB-encrypted-session"


async def user_by(env, tg):
    return await env.db(lambda s: s.scalar(select(User).where(User.tg_id == tg)))


async def test_menu_and_export_file(env):
    await env.user(1)
    await env.say(1, "/malumotlarim")
    assert env.last_text(1).startswith("Ma'lumotlarim")
    assert env.buttons(1) == ["pv:x", "pv:d"]
    await env.press(1, "pv:x")
    docs = env.methods("SendDocument")
    assert docs, "no file was sent"
    data = json.loads(docs[-1].document.data.decode("utf-8"))
    assert data["profile"]["telegram_id"] == 1


async def test_delete_needs_the_second_button(env):
    await env.user(1)
    await env.press(1, "pv:d")
    assert env.buttons(1) == ["pv:dy", "pv:no"]
    await env.press(1, "pv:no")                                   # negative: "keep" deletes nothing
    assert (await user_by(env, 1)) is not None
    assert env.last_text(1) == tx("bot.privacy.kept")


async def test_delete_anonymises(env):
    await env.user(1, username="ali")
    await env.press(1, "pv:dy")
    assert env.last_text(1) == tx("bot.privacy.deleted")
    assert (await user_by(env, 1)) is None                        # tg_id no longer links to the person


async def test_delete_refused_during_a_trip_and_userbot_untouched(env, monkeypatch):
    await env.user(1)
    driver_id = await env.driver(2)

    async def setup(s):
        p = await s.scalar(select(User).where(User.tg_id == 1))
        d = await s.get(Driver, driver_id)
        s.add(UserbotAccount(driver_id=d.id, session_encrypted=SESSION, status=UserbotStatus.CONNECTED))
        r = await rides.create_request(s, p, env.settings, from_text="Qo'shrabot", to_text="Samarqand")
        o = await rides.send_offer(s, d, r, env.settings, price=30000)
        await rides.accept_offer(s, p, o)
    await env.db(setup)

    import tulporgo_userbot.service as ub_service
    called = []

    async def spy(*a, **kw):
        called.append(a)
    monkeypatch.setattr(ub_service, "disconnect_account", spy)

    await env.press(2, "pv:dy")
    assert tx("bot.err.active_trip") in env.alerts()
    assert called == []                                           # negative: refused → the userbot keeps working
    acc = await env.db(lambda s: s.scalar(select(UserbotAccount)))
    assert acc.session_encrypted == SESSION
    assert await env.db(lambda s: s.scalar(select(Trip.status))) == "confirmed"


async def test_driver_delete_logs_the_userbot_out_first(env, monkeypatch):
    driver_id = await env.driver(2)
    await env.db(lambda s: _add_account(s, driver_id))
    import tulporgo_userbot.service as ub_service
    called = []
    real = ub_service.disconnect_account

    async def spy(s, account, settings, factory):
        called.append(account.id)
        await real(s, account, settings, None)                   # no network in tests
    monkeypatch.setattr(ub_service, "disconnect_account", spy)

    await env.press(2, "pv:dy")
    assert called, "the Telegram session was not logged out"
    assert await env.db(lambda s: s.scalar(select(UserbotAccount))) is None
    assert env.last_text(2) == tx("bot.privacy.deleted")
    assert await env.db(lambda s: s.scalar(select(RideRequest))) is None


async def _add_account(s, driver_id):
    s.add(UserbotAccount(driver_id=driver_id, session_encrypted=SESSION, status=UserbotStatus.CONNECTED))
    await s.flush()


async def test_deep_link_from_the_mini_app_opens_the_menu(env):
    await env.user(1)
    await env.say(1, "/start malumotlarim")
    assert env.last_text(1).startswith("Ma'lumotlarim")
    assert env.buttons(1) == ["pv:x", "pv:d"]


async def test_other_deep_links_do_not_open_it(env):
    # negative: a plain /start greets as before
    await env.user(1)
    await env.say(1, "/start")
    assert "pv:x" not in env.buttons(1)
