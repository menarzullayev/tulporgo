"""Admin panel (decision 19): documents, complaints, blacklist, KPI — and who may NOT use it."""
from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import Env, tx
from sqlalchemy import select
from tulporgo_core.models import Complaint, Driver, User


async def user_of(env, tg):
    return await env.db(lambda s: s.scalar(select(User).where(User.tg_id == tg)))


async def complaint(env, author=1, against=2, text="Haydovchi pulni ko'p so'radi"):
    async def make(s):
        a = await s.scalar(select(User).where(User.tg_id == author))
        b = await s.scalar(select(User).where(User.tg_id == against)) if against else None
        c = Complaint(from_user_id=a.id, against_user_id=b.id if b else None, text=text)
        s.add(c)
        await s.flush()
        return c.id
    return await env.db(make)


async def test_panel_for_admins_and_denial_for_everybody_else(env):
    await env.user(50, admin=True)
    await env.user(1)
    await env.say(50, "/admin")
    assert tx("bot.admin.panel") in env.last_text(50)
    assert env.buttons(50) == ["ad:docs", "ad:cp", "ad:bl", "ad:kpi"]
    await env.say(1, "/admin")
    assert env.last_text(1) == tx("bot.err.admin_only")                       # nothing about the panel leaks
    assert not any(d.startswith("ad:") for d in env.buttons(1))


async def test_admin_ids_from_settings_work_without_a_database_flag(tmp_path):
    env = await Env(tmp_path, admin_ids=[77]).start()
    try:
        await env.say(77, "/admin")
        assert tx("bot.admin.panel") in env.last_text(77)
    finally:
        await env.stop()


async def test_every_admin_button_refuses_normal_users(env):
    await env.user(1)
    d = await env.driver(2, docs=True)
    cid = await complaint(env)
    victim = (await user_of(env, 2)).id
    for data in ("ad:menu", "ad:docs", f"ad:dv:{d}", f"ad:dr:{d}", "ad:cp", f"ad:cr:{cid}:1", "ad:bl",
                 f"ad:bu:{victim}", f"ad:ub:{victim}", "ad:kpi"):
        await env.press(1, data)
        assert env.alerts()[-1] == tx("bot.err.admin_only"), data
    assert (await user_of(env, 2)).is_blocked is False
    driver = await env.db(lambda s: s.scalar(select(Driver).where(Driver.id == d)))
    assert driver.verified is False and driver.license_file_id == "lic"
    assert (await env.db(lambda s: s.get(Complaint, cid))).status == "open"


async def test_non_admin_cannot_use_the_block_prompt_state(env):
    await env.user(1)
    await env.user(2)
    await env.say(1, "2")                                                     # a number typed outside the admin flow
    assert (await user_of(env, 2)).is_blocked is False


async def test_complaint_resolution_notifies_the_author(env):
    await env.user(50, admin=True)
    await env.user(1)
    await env.driver(2)
    cid = await complaint(env)
    await env.press(50, "ad:cp")
    assert "pulni" in env.last_text(50) and f"ad:cr:{cid}:1" in env.buttons(50)
    await env.press(50, f"ad:cr:{cid}:1")
    c = await env.db(lambda s: s.get(Complaint, cid))
    assert (c.status, c.resolution) == ("resolved", tx("bot.admin.resolution_ok"))
    assert env.said(1, tx("bot.complaint.resolved", id=cid))
    await env.press(50, f"ad:cr:{cid}:0")                                     # already closed
    assert env.alerts()[-1] == tx("bot.err.complaint_closed")
    assert (await env.db(lambda s: s.get(Complaint, cid))).status == "resolved"


async def test_complaint_can_be_rejected_and_bad_flags_are_ignored(env):
    await env.user(50, admin=True)
    await env.user(1)
    cid = await complaint(env, against=None)
    await env.press(50, f"ad:cr:{cid}:7")
    assert env.alerts()[-1] == tx("bot.err.complaint_not_found")
    await env.press(50, f"ad:cr:{cid}:0")
    assert (await env.db(lambda s: s.get(Complaint, cid))).status == "rejected"
    await env.press(50, "ad:cr:999:1")
    assert env.alerts()[-1] == tx("bot.err.complaint_not_found")


async def test_block_from_a_complaint_and_blocked_user_is_ignored(env):
    await env.user(50, admin=True)
    await env.user(1)
    await env.driver(2)
    await complaint(env)
    await env.press(50, "ad:cp")
    block = env.pick(50, "ad:bu:")
    await env.press(50, block)
    assert (await user_of(env, 2)).is_blocked is True
    n = len(env.fake.calls)
    await env.say(2, "/start")                                                # the blacklist is enforced (decision 13)
    assert len(env.fake.calls) == n


async def test_block_by_id_and_username_then_unblock(env):
    await env.user(50, admin=True)
    await env.user(1, username="Passenger")
    await env.press(50, "ad:bl")
    await env.say(50, "999999")
    assert env.last_text(50) == tx("bot.admin.user_none")                     # state kept: ask again
    await env.say(50, "@passenger")                                           # case-insensitive username
    uid = (await user_of(env, 1)).id
    assert f"ad:bu:{uid}" in env.buttons(50)
    await env.press(50, f"ad:bu:{uid}")
    assert (await user_of(env, 1)).is_blocked is True
    await env.press(50, "ad:bl")
    await env.say(50, "1")                                                    # numeric = Telegram id
    assert f"ad:ub:{uid}" in env.buttons(50)
    await env.press(50, f"ad:ub:{uid}")
    assert (await user_of(env, 1)).is_blocked is False


async def test_admin_cannot_block_themselves(env):
    await env.user(50, admin=True)
    me = (await user_of(env, 50)).id
    await env.press(50, f"ad:bu:{me}")
    assert env.alerts()[-1] == tx("bot.err.cannot_block_self")
    assert (await user_of(env, 50)).is_blocked is False


async def test_kpi_now_shows_the_weekly_report(env):
    await env.user(50, admin=True)
    await env.driver(2)
    await env.press(50, "ad:kpi")
    text = env.last_text(50)
    assert "KPI" in text and "maqsad" in text and "Röyxatdan" in text


async def test_empty_queues_say_so(env):
    await env.user(50, admin=True)
    await env.press(50, "ad:docs")
    assert env.last_text(50) == tx("bot.admin.none")
    await env.press(50, "ad:cp")
    assert env.last_text(50) == tx("bot.admin.none")
