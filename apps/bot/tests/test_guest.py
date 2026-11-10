"""Guest Mode (Bot API 10.0): the bot is mentioned in a group and answers with answerGuestQuery."""
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerGuestQuery, GetMe
from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import tx
from sqlalchemy import select
from tulporgo_bot.handlers.guest import guest_payload, strip_mention
from tulporgo_core.models import RideRequest


def answer(env) -> AnswerGuestQuery:
    [call] = env.methods("AnswerGuestQuery")
    return call


async def test_mention_is_answered_with_route_and_a_deep_link(env):
    await env.user(1)
    await env.guest(1, "@tulporgobot Qo'shrabot → Samarqand 07:30 2 kishi")
    call = answer(env)
    assert call.guest_query_id == "gq-1"
    text = call.result.input_message_content.message_text
    assert "Qo'shrabot → Samarqand" in text and '<tg-time unix="' in text and tx("bot.seats_n", n=2) in text
    [button] = [b for row in call.result.reply_markup.inline_keyboard for b in row]
    assert button.url.startswith(f"https://t.me/tulporgobot?start=g_{env.qosh}_{env.sam}_2_")
    assert button.style == "primary"
    assert env.sent(1) == []                                  # nothing is posted into the group by send methods


async def test_deep_link_from_guest_answer_finishes_the_order_privately(env):
    await env.user(1)
    await env.guest(1, "@tulporgobot Qo'shrabot → Samarqand 2 kishi")
    payload = answer(env).result.reply_markup.inline_keyboard[0][0].url.split("start=")[1]
    await env.say(1, f"/start {payload}")
    assert env.buttons(1) == ["cf:y", "cf:n", "ord:new"]
    assert "Qo'shrabot → Samarqand" in env.last_text(1)
    await env.press(1, "cf:y")
    [r] = await env.db(lambda s: _all(s))
    assert (r.source, r.seats, r.from_place_id, r.to_place_id) == ("guest", 2, env.qosh, env.sam)


async def _all(s):
    return list((await s.execute(select(RideRequest))).scalars())


async def test_unreadable_mention_gets_a_hint_not_an_order(env):
    await env.user(1)
    await env.guest(1, "@tulporgobot salom hammaga")
    call = answer(env)
    assert call.result.input_message_content.message_text == tx("bot.guest.not_understood")
    assert call.result.reply_markup.inline_keyboard[0][0].url == "https://t.me/tulporgobot?start=order"


async def test_route_with_an_unknown_place_links_without_ids(env):
    await env.user(1)
    await env.guest(1, "@tulporgobot Qo'shrabot → Xyzland")
    url = answer(env).result.reply_markup.inline_keyboard[0][0].url
    assert url.endswith("start=order")                        # no half-filled order from an unknown place


async def test_bad_guest_payloads_fall_back_to_the_greeting(env):
    await env.user(1)
    bad = ["g_1_2_3", "g_x_y_z_w", f"g_{env.qosh}_{env.qosh}_1_0", f"g_{env.qosh}_{env.sam}_99_0", "g_0_0_1_0",
           f"g_{env.qosh}_{env.sam}_1_99999999999999999999", "g_999999_888888_1_0"]
    for payload in bad:
        await env.say(1, f"/start {payload}")
        assert env.buttons(1)[:2] == ["ord:new", "drv:reg"], payload      # plain greeting, never a confirm card
    assert await env.db(lambda s: _all(s)) == []


async def test_stale_guest_link_drops_the_past_departure(env):
    await env.user(1)
    await env.say(1, f"/start g_{env.qosh}_{env.sam}_1_100")             # minute 100 since 1970 — long gone
    assert env.buttons(1)[0] == "cf:y"
    assert tx("bot.when_now") in env.last_text(1)


async def test_blocked_user_gets_no_guest_answer(env):
    await env.user(1, blocked=True)
    await env.guest(1, "@tulporgobot Qo'shrabot → Samarqand")
    assert env.methods("AnswerGuestQuery") == []


async def test_expired_guest_query_does_not_crash(env):
    await env.user(1)
    env.fake.errors[AnswerGuestQuery] = TelegramBadRequest(
        method=GetMe(), message="Bad Request: guest query expired")
    await env.guest(1, "@tulporgobot Qo'shrabot → Samarqand")        # logged, no exception, no message to the user
    assert env.fake.failed and env.sent(1) == []


async def test_new_user_via_guest_gets_a_row_but_no_request(env):
    await env.guest(77, "@tulporgobot Qo'shrabot → Samarqand")
    assert await env.db(lambda s: _all(s)) == []


def test_payload_and_mention_helpers():
    assert strip_mention("@TulporGoBot Qo'shrabot → Samarqand", "tulporgobot") == "Qo'shrabot → Samarqand"
    assert strip_mention("@boshqabot Qo'shrabot", "tulporgobot") == "@boshqabot Qo'shrabot"      # other mentions stay
    assert guest_payload.__doc__ and strip_mention("", "tulporgobot") == ""
