from datetime import datetime, time, timedelta

from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import tx, walk_to_confirm
from sqlalchemy import select
from tulporgo_bot.handlers.common import UZT, local_to_utc, to_local
from tulporgo_core.db import utcnow
from tulporgo_core.models import RideRequest, Trip
from tulporgo_core.services import rides


async def requests(env):
    return await env.db(lambda s: _all(s, RideRequest))


async def _all(s, model):
    return list((await s.execute(select(model).order_by(model.id))).scalars())


async def test_buttons_flow_creates_a_request(env):
    await env.user(1)
    await walk_to_confirm(env)
    card = env.last_text(1)
    assert "Qo'shrabot" in card and "Samarqand" in card and "yuk bor" in card and tx("bot.seats_n", n=2) in card
    assert env.buttons(1) == ["cf:y", "cf:n"]
    await env.press(1, "cf:y")
    [r] = await requests(env)
    assert (r.from_text, r.to_text, r.seats, r.note, r.source) == ("Qo'shrabot", "Samarqand", 2, "yuk bor", "buttons")
    assert (r.from_place_id, r.to_place_id) == (env.qosh, env.sam)
    tomorrow = (to_local(utcnow()) + timedelta(days=1)).date()
    assert r.depart_at == local_to_utc(datetime.combine(tomorrow, time(8, 30), UZT))
    assert any(type(e).__name__ == "RequestCreated" for e in env.bus.published)
    assert any("rq:c:" in d for d in env.buttons(1))        # the passenger can cancel right away


async def test_place_list_is_paginated_and_sorted_by_popularity(env):
    await env.user(1)
    await env.press(1, "ord:new")
    assert env.buttons(1)[:2] == [f"pd:f:{env.sam}", f"pd:f:{env.qosh}"]        # popularity 20 before 10
    await env.press(1, f"pd:f:{env.qosh}")
    first = env.buttons(1)
    assert first[0] == f"pk:f:{env.qosh}"                    # "the whole district" comes first
    assert "pg:f:%d:1" % env.qosh in first and not any(d.startswith(f"pg:f:{env.qosh}:-") for d in first)
    mahallas_p1 = [d for d in first if d.startswith("pk:f:") and d != f"pk:f:{env.qosh}"]
    assert len(mahallas_p1) == 8
    await env.press(1, f"pg:f:{env.qosh}:1")
    second = env.buttons(1)
    assert len([d for d in second if d.startswith("pk:f:") and d != f"pk:f:{env.qosh}"]) == 2
    assert f"pg:f:{env.qosh}:0" in second and not any(d.endswith(":2") for d in second if d.startswith("pg:"))


async def test_district_without_children_is_chosen_directly(env):
    await env.user(1)
    await env.press(1, "ord:new")
    await env.press(1, f"pd:f:{env.pas}")                   # Pastdarg'om has no mahallas
    assert "Qayerga" in env.last_text(1)


async def test_tampered_place_callbacks_do_nothing(env):
    await env.user(1)
    await env.press(1, "ord:new")
    n = len(env.sent(1))
    for bad in ("pk:f:999999", "pk:x:1", "pk:f:abc", "pg:f:abc:1", "pd:f:0", "pk:f"):
        await env.press(1, bad)
    assert len(env.sent(1)) == n and await requests(env) == []


async def test_typing_a_place_searches_and_offers_to_use_the_text(env):
    await env.user(1)
    await env.press(1, "ord:new")
    await env.say(1, "koshrabad")                           # alias, other spelling
    assert f"pk:f:{env.qosh}" in env.buttons(1)
    await env.say(1, "Xyzabc")
    assert "pt:f" in env.buttons(1) and not any(d.startswith("pk:") for d in env.buttons(1))
    await env.press(1, "pt:f")
    assert "Qayerga" in env.last_text(1)
    await env.press(1, f"pk:t:{env.sam}")
    await env.press(1, "tm:now")
    await env.press(1, "st:1")
    await env.press(1, "nt:skip")
    await env.press(1, "cf:y")
    [r] = await requests(env)
    assert (r.from_text, r.from_place_id, r.depart_at) == ("Xyzabc", None, None)    # free text, "hozir"


async def test_same_origin_and_destination_is_refused(env):
    await env.user(1)
    await env.press(1, "ord:new")
    await env.press(1, f"pk:f:{env.sam}")
    await env.press(1, f"pk:t:{env.sam}")
    assert env.alerts() and tx("bot.err.same_place") == env.alerts()[-1]
    assert not any(tx("bot.time.ask") in t for t in env.texts(1))        # the flow did not move on to the time step


async def test_typed_time_and_bad_time(env):
    await env.user(1)
    await env.press(1, "ord:new")
    await env.press(1, f"pk:f:{env.qosh}")
    await env.press(1, f"pk:t:{env.sam}")
    await env.say(1, "yarim soat")
    assert tx("bot.time.bad") in env.last_text(1)           # asked again, nothing stored
    await env.say(1, "07:30")
    assert env.buttons(1) == ["st:1", "st:2", "st:3", "st:4"]
    await env.say(1, "9")
    assert tx("bot.seats.bad") in env.last_text(1)
    await env.say(1, "6")
    await env.press(1, "nt:skip")
    await env.press(1, "cf:y")
    [r] = await requests(env)
    assert r.seats == 6
    local = to_local(r.depart_at)
    assert (local.hour, local.minute) == (7, 30) and r.depart_at > utcnow() - timedelta(minutes=10)


async def test_time_buttons_reject_bad_values(env):
    await env.user(1)
    await env.press(1, "ord:new")
    await env.press(1, f"pk:f:{env.qosh}")
    await env.press(1, f"pk:t:{env.sam}")
    n = len(env.sent(1))
    for bad in ("tm:d:7", "tm:h:1:99", "tm:m:1:8:75", "tm:m:1:8", "tm:h:x:y"):
        await env.press(1, bad)
    assert len(env.sent(1)) == n


async def test_confirm_is_single_use_and_cancel_creates_nothing(env):
    await env.user(1)
    await walk_to_confirm(env, note=None)
    await env.press(1, "cf:y")
    await env.press(1, "cf:y")                               # a second tap on an old button
    assert len(await requests(env)) == 1
    assert tx("bot.stale") == env.alerts()[-1]
    await walk_to_confirm(env, note=None)
    await env.press(1, "cf:n")
    assert len(await requests(env)) == 1


async def test_confirm_button_without_a_flow_is_stale(env):
    await env.user(1)
    await env.press(1, "cf:y")
    assert await requests(env) == [] and tx("bot.stale") == env.alerts()[-1]


async def test_fourth_open_request_is_refused(env):
    await env.user(1)
    for _ in range(3):
        await walk_to_confirm(env, note=None)
        await env.press(1, "cf:y")
    await walk_to_confirm(env, note=None)
    await env.press(1, "cf:y")
    assert len(await requests(env)) == 3
    assert tx("bot.err.too_many_open_requests") == env.alerts()[-1]


async def test_woman_marker_reaches_the_request(env):
    await env.user(1, woman=True)
    await walk_to_confirm(env, note=None)
    assert tx("bot.women_marker") in env.last_text(1)
    await env.press(1, "cf:y")
    assert (await requests(env))[0].women_only is True


async def test_women_marker_toggle_in_help(env):
    await env.user(1)
    await env.say(1, "/yordam")
    assert "wm:t" in env.buttons(1) and "cm:0" in env.buttons(1)
    await env.press(1, "wm:t")
    from tulporgo_core.models import User
    assert (await env.db(lambda s: s.scalar(select(User.is_woman).where(User.tg_id == 1)))) is True
    await env.press(1, "wm:t")
    assert (await env.db(lambda s: s.scalar(select(User.is_woman).where(User.tg_id == 1)))) is False


async def test_price_hint_appears_when_there_is_history(env):
    for i in range(3):                                      # core rule: a hint needs 3 matched trips on the route
        await env.user(100 + i)
        await env.driver(200 + i, plate=f"30A10{i}BC")

    async def seed(s):
        from tulporgo_core.models import Driver, User
        for i in range(3):
            p = await s.scalar(select(User).where(User.tg_id == 100 + i))
            d = (await s.execute(select(Driver).order_by(Driver.id))).scalars().all()[i]
            r = await rides.create_request(s, p, env.settings, from_text="Qo'shrabot", to_text="Samarqand",
                                           from_place_id=env.qosh, to_place_id=env.sam)
            o = await rides.send_offer(s, d, r, env.settings, 40_000)
            await rides.accept_offer(s, p, o)
    await env.db(seed)
    await env.user(1)
    await walk_to_confirm(env, note=None)
    assert "40 000" in env.last_text(1)
    assert len(await env.db(lambda s: _all(s, Trip))) == 3


async def test_hint_is_absent_without_history(env):
    await env.user(1)
    await walk_to_confirm(env, note=None)
    assert "~" not in env.last_text(1)           # never an invented number


# ---------- free text (decision 47b) ----------

async def test_free_text_order_is_parsed_and_confirmed(env):
    await env.user(1)
    await env.say(1, "Qo'shrabot → Samarqand 07:30 2 kishi")
    card = env.last_text(1)
    assert "Qo'shrabot → Samarqand" in card and tx("bot.seats_n", n=2) in card
    assert env.buttons(1) == ["cf:y", "cf:n", "ord:new"]    # confirm, cancel, "change with buttons"
    await env.press(1, "cf:y")
    [r] = await requests(env)
    assert (r.source, r.seats, r.from_place_id, r.to_place_id) == ("text", 2, env.qosh, env.sam)
    assert to_local(r.depart_at).strftime("%H:%M") == "07:30"


async def test_free_text_in_russian_and_cyrillic(env):
    await env.user(1, lang="ru")
    await env.say(1, "Кошрабад - Самарканд завтра 18:00")
    await env.press(1, "cf:y")
    [r] = await requests(env)
    assert (r.from_place_id, r.to_place_id) == (env.qosh, env.sam)


async def test_unreadable_text_falls_back_to_buttons_and_creates_nothing(env):
    await env.user(1)
    await env.say(1, "salom, qalaysiz")
    assert env.buttons(1) == ["ord:new"] and await requests(env) == []


async def test_free_text_change_button_restarts_with_buttons(env):
    await env.user(1)
    await env.say(1, "Qo'shrabot → Samarqand")
    await env.press(1, "ord:new")
    assert env.buttons(1)[0].startswith("pd:f:")


async def test_free_text_in_a_group_is_not_an_order(env):
    await env.user(1)
    await env.say(1, "Qo'shrabot → Samarqand 07:30", chat="supergroup")
    assert env.sent(1) == [] and await requests(env) == []


async def test_unknown_button_gets_a_visible_answer(env):
    await env.user(1)
    await env.press(1, "zzz:unknown")
    assert env.alerts() and tx("bot.stale") == env.alerts()[-1]


async def test_place_names_follow_the_users_language(env):
    await env.user(1, lang="ru")
    await env.press(1, "ord:new")
    labels = [b.text for b in env.all_buttons(1)]
    assert "Самарканд" in labels and "Кошрабад" in labels
    await env.user(2, lang="uz_cyrl")
    await env.press(2, "ord:new")
    assert "Қўшработ" in [b.text for b in env.all_buttons(2)]
