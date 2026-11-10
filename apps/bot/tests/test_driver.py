"""Driver onboarding (decision 12), documents → "Tasdiqlangan", referral bonus (decision 52), member tags."""
from datetime import timedelta

from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import Env, tx
from sqlalchemy import select
from tulporgo_core.db import utcnow
from tulporgo_core.models import Driver, User


async def driver_of(env, tg):
    return await env.db(lambda s: s.scalar(select(Driver).join(User, User.id == Driver.user_id).where(User.tg_id == tg)))


async def user_of(env, tg):
    return await env.db(lambda s: s.scalar(select(User).where(User.tg_id == tg)))


async def register(env, uid=1, plate="30 A 123 BC", skip_home=False):
    await env.press(uid, "drv:reg")
    await env.contact(uid)
    await env.say(uid, "Cobalt")
    await env.say(uid, "oq")
    await env.say(uid, plate)
    await env.press(uid, "ds:4")
    await env.photo(uid, "car-photo")
    if skip_home:
        await env.press(uid, "ph:skip")
    else:
        await env.press(uid, f"pk:h:{env.qosh}")


async def test_registration_end_to_end(env):
    await env.user(1, name="Karim")
    await register(env)
    d = await driver_of(env, 1)
    assert (d.car_make, d.car_color, d.car_plate, d.seats) == ("Cobalt", "oq", "30A123BC", 4)
    assert (d.car_photo_file_id, d.home_place_id, d.verified, d.status) == ("car-photo", env.qosh, False, "active")
    assert (await user_of(env, 1)).phone == "+998901234567"
    left = d.subscription_until - utcnow()
    assert timedelta(days=6, hours=23) < left <= timedelta(days=7)           # the 7-day trial (decision 10)
    panel = env.last_text(1)
    code = (await user_of(env, 1)).referral_code
    assert f"https://t.me/tulporgobot?start=ref_{code}" in panel and "+7" in panel
    assert tx("bot.drv.until", date=(d.subscription_until + timedelta(hours=5)).strftime("%d.%m.%Y")) in panel
    assert tx("bot.drv.not_verified") in panel and "drv:doc" in env.buttons(1)
    chat = [c for c in env.methods("SetMyCommands") if getattr(c.scope, "chat_id", None) == 1][-1]
    assert [c.command for c in chat.commands][-2:] == ["elon", "obuna"]       # drivers get /elon and /obuna
    assert any(type(e).__name__ == "DriverRegistered" for e in env.bus.published)


async def test_registration_can_skip_the_home_district(env):
    await env.user(1)
    await register(env, skip_home=True)
    assert (await driver_of(env, 1)).home_place_id is None


async def test_phone_step_demands_the_users_own_contact(env):
    await env.user(1)
    await env.press(1, "drv:reg")
    assert env.sent(1)[-1].reply_markup.keyboard[0][0].request_contact is True
    await env.contact(1, owner=999)                                           # somebody else's contact card
    assert tx("bot.reg.contact_not_own") in env.last_text(1)
    assert (await user_of(env, 1)).phone is None
    await env.contact(1, phone="+15551234567")                                # not an Uzbek number
    assert env.last_text(1) == tx("bot.err.bad_phone") and (await user_of(env, 1)).phone is None
    await env.say(1, "+998901234567")                                         # typing a number is not enough
    assert tx("bot.reg.phone_only_button") in env.last_text(1) and (await user_of(env, 1)).phone is None
    await env.contact(1)
    assert (await user_of(env, 1)).phone == "+998901234567" and tx("bot.reg.make") in env.last_text(1)


async def test_known_phone_skips_the_phone_step(env):
    await env.user(1, phone="+998903333333")
    await env.press(1, "drv:reg")
    assert tx("bot.reg.make") in env.last_text(1)


async def test_bad_answers_keep_the_step(env):
    await env.user(1, phone="+998903333333")
    await env.press(1, "drv:reg")
    await env.say(1, "x")                                                     # too short
    assert env.last_text(1) == tx("bot.reg.bad_text")
    await env.say(1, "Cobalt")
    await env.say(1, "oq")
    await env.say(1, "ABC")                                                   # not a plate
    assert env.last_text(1) == tx("bot.err.bad_plate")
    await env.say(1, "30A123BC")
    assert tx("bot.reg.seats") in env.last_text(1)
    await env.say(1, "12")
    assert env.last_text(1) == tx("bot.seats.bad")
    await env.press(1, "ds:99")                                               # tampered
    await env.say(1, "4")
    assert tx("bot.reg.photo") in env.last_text(1)
    await env.say(1, "rasm yo'q")
    assert env.last_text(1) == tx("bot.reg.photo_only")
    assert await driver_of(env, 1) is None                                    # nothing is created before the end


async def test_duplicate_plate_is_refused_at_the_end(env):
    await env.driver(5, plate="30A123BC")
    await env.user(1)
    await register(env)
    assert env.alerts()[-1] == tx("bot.err.plate_taken") and await driver_of(env, 1) is None


async def test_existing_driver_sees_the_panel_not_a_second_registration(env):
    await env.driver(1)
    await env.press(1, "drv:reg")
    assert tx("bot.drv.panel") in env.last_text(1) and tx("bot.reg.make") not in env.last_text(1)


async def test_start_command_cancels_a_half_finished_registration(env):
    await env.user(1, phone="+998903333333")
    await env.press(1, "drv:reg")
    await env.say(1, "Cobalt")
    await env.say(1, "/start")
    await env.say(1, "oq")                                                    # no longer a registration answer
    assert await driver_of(env, 1) is None
    assert env.last_text(1) == tx("bot.order.not_understood")               # it went to the free-text order parser


async def test_blocked_user_cannot_register(env):
    await env.user(1, blocked=True)
    await env.press(1, "drv:reg")
    assert env.sent(1) == []


# ---------- documents → verified ----------

async def test_documents_flow_and_admin_approval_with_referral(tmp_path, monkeypatch):
    monkeypatch.setenv("TULPORGO_DRIVERS_GROUP_ID", "-100777")
    env = await Env(tmp_path, admin_ids=[50]).start()
    await env.seed_places()
    try:
        await env.driver(10, name="Inviter", plate="30A111BC")
        code = (await user_of(env, 10)).referral_code
        await env.user(50, name="Admin", admin=True)
        await env.say(20, f"/start ref_{code}", name="Newbie")                # new person through the link
        await env.press(20, "lang:uz_new")
        await register(env, 20)
        await env.press(20, "drv:doc")
        await env.say(20, "mana hujjat")                                      # text is not a photo
        assert env.last_text(20) == tx("bot.docs.photo_only")
        await env.photo(20, "licence-1")
        await env.photo(20, "techpass-1")
        d = await driver_of(env, 20)
        assert (d.license_file_id, d.techpass_file_id, d.verified) == ("licence-1", "techpass-1", False)
        assert tx("bot.drv.docs_pending") in (await _panel(env, 20))
        assert "ad:docs" in env.buttons(50)                                   # the admin was told

        await env.press(50, "ad:docs")
        photos = env.methods("SendPhoto")
        assert [p.photo for p in photos] == ["licence-1", "techpass-1"]
        assert [x for x in photos[-1].reply_markup.inline_keyboard[0]][0].callback_data == f"ad:dv:{d.id}"

        before = (await driver_of(env, 10)).subscription_until
        await env.press(50, f"ad:dv:{d.id}")
        d, inviter = await driver_of(env, 20), await driver_of(env, 10)
        assert d.verified is True and inviter.ambassador is True
        assert inviter.subscription_until - before == timedelta(days=7)       # +7 days for both (decision 52)
        assert env.said(20, tx("bot.drv.verified_msg")) and env.said(20, tx("bot.ref.granted", days=7))
        assert env.said(10, tx("bot.ref.granted", days=7))
        tags = {(c.user_id, c.tag) for c in env.methods("SetChatMemberTag")}
        assert tags == {(20, tx("bot.tag.verified")), (10, tx("bot.tag.ambassador"))}                  # member tags in the drivers group
        assert {c.chat_id for c in env.methods("SetChatMemberTag")} == {-100777}
        await env.runtime.notifier.tags.sync()
        assert len(env.methods("SetChatMemberTag")) == 2                      # applied once, not on every sync
        await env.press(50, f"ad:dv:{d.id}")                                  # approving twice pays nothing twice
        assert (await driver_of(env, 10)).subscription_until - before == timedelta(days=7)
    finally:
        await env.stop()


async def _panel(env, uid):
    await env.press(uid, "drv:reg")
    return env.last_text(uid)


async def test_no_member_tags_without_a_configured_group(env):
    await env.driver(10, verified=True)
    await env.runtime.notifier.tags.sync()
    assert env.methods("SetChatMemberTag") == []


async def test_member_tag_failure_is_not_fatal(tmp_path, monkeypatch):
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import GetMe, SetChatMemberTag
    monkeypatch.setenv("TULPORGO_DRIVERS_GROUP_ID", "-100777")
    env = await Env(tmp_path).start()
    try:
        await env.driver(10, verified=True)
        env.fake.errors[SetChatMemberTag] = TelegramBadRequest(method=GetMe(), message="Bad Request: user is not a member")
        assert await env.runtime.notifier.tags.sync() == 0                    # skipped, retried at the next sync
        env.fake.errors.clear()
        assert await env.runtime.notifier.tags.sync() == 1
    finally:
        await env.stop()


async def test_documents_need_a_driver_and_verified_drivers_are_told_so(env):
    await env.user(1)
    await env.press(1, "drv:doc")
    assert env.alerts()[-1] == tx("bot.err.not_driver")
    await env.driver(2, verified=True)
    await env.press(2, "drv:doc")
    assert tx("bot.drv.already_verified") in env.last_text(2)
    await env.photo(2, "x")                                                   # no document step is active
    assert (await driver_of(env, 2)).license_file_id == "lic"


async def test_rejected_documents_are_cleared_and_pay_no_bonus(env):
    await env.user(50, name="Admin", admin=True)
    await env.driver(10, plate="30A111BC")
    code = (await user_of(env, 10)).referral_code
    await env.user(20)
    await env.say(20, f"/start ref_{code}")
    await register(env, 20)
    await env.press(20, "drv:doc")
    await env.photo(20, "l")
    await env.photo(20, "t")
    d = await driver_of(env, 20)
    await env.press(50, f"ad:dr:{d.id}")
    d = await driver_of(env, 20)
    assert (d.license_file_id, d.techpass_file_id, d.verified) == (None, None, False)
    assert tx("bot.docs.rejected") in env.last_text(20) and "drv:doc" in env.buttons(20)
    assert (await driver_of(env, 10)).ambassador is False                     # no bonus without verification


async def test_approving_without_documents_is_refused(env):
    await env.user(50, admin=True)
    d = await env.driver(10)
    await env.db(lambda s: _clear_docs(s, d))
    await env.press(50, f"ad:dv:{d}")
    assert env.alerts()[-1] == tx("bot.err.documents_missing")
    assert (await driver_of(env, 10)).verified is False


async def _clear_docs(s, did):
    d = await s.get(Driver, did)
    d.license_file_id = d.techpass_file_id = None
