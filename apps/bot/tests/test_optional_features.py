"""Three optional Telegram features, all behind flags that default to OFF (GOAL.md §4): trip topics (Bot API 9.3),
ephemeral group commands (10.2) and the trip-status widget (10.4). Each rule has a negative test: flag off → not a single
call; group chat → never a widget; oversize → refused before sending; Telegram error → the normal card still arrives."""
import json
import os
import time
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import CreateForumTopic, GetMe, SendMessage, SendRichMessage
from bot_harness import env, free_env, no_waiting, new_request, offer_by_ui, tx  # noqa: F401  (fixtures)
from sqlalchemy import select
from tulporgo_bot import delivery, topics, widgets
from tulporgo_bot.config import BotExtra, get_extra
from tulporgo_bot.handlers import commands
from tulporgo_bot.handlers.common import bind
from tulporgo_bot.widgets import SendWidget, WidgetError, check_widget
from tulporgo_core.models import Trip

PHONE_P, PHONE_D = "+998901234567", "+998902222222"
FLAGS = {"trip_topics": "TULPORGO_TRIP_TOPICS", "ephemeral_group": "TULPORGO_EPHEMERAL_GROUP",
         "widgets": "TULPORGO_WIDGETS"}


@pytest.fixture(autouse=True)
def fresh_state():
    topics._available.clear()
    delivery._warned.clear()
    yield


def turn_on(env, monkeypatch, *names: str) -> None:
    for n in names:
        monkeypatch.setenv(FLAGS[n], "true")
    env.runtime.notifier.extra = get_extra()


def bad(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=GetMe(), message=message)


async def trip_setup(env, accept: bool = True):
    await env.user(1, name="Pasajir", username="pas", phone=PHONE_P)
    await env.driver(2, name="Karim", username="drv", plate="30A123BC", verified=True)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    if accept:
        await env.press(1, f"oa:{oid}")
    return rid, oid


async def the_trip(env) -> Trip:
    return await env.db(lambda s: s.scalar(select(Trip).order_by(Trip.id.desc())))


def threads(env, uid: int) -> list[int | None]:
    return [getattr(c, "message_thread_id", None) for c in env.sent(uid)]


def api(env, name: str) -> list:
    return env.methods(name)


# =============================== A. trip topics ===============================

def test_flags_default_to_on(monkeypatch):
    # decision 55: approved by Saidakbar aka on 2026-11-10
    for var in FLAGS.values():
        monkeypatch.delenv(var, raising=False)
    extra = BotExtra(_env_file=None)                                       # type: ignore[call-arg]
    assert (extra.trip_topics, extra.ephemeral_group, extra.widgets) == (True, True, True)


@pytest.mark.parametrize("name", list(FLAGS))
def test_each_flag_can_be_switched_off(monkeypatch, name):
    # negative: "false" in deploy/.env really turns the feature off
    monkeypatch.setenv(FLAGS[name], "false")
    assert getattr(BotExtra(_env_file=None), name) is False               # type: ignore[call-arg]


async def test_topics_off_makes_no_topic_call_at_all(env):
    await trip_setup(env)
    t = await the_trip(env)
    await env.press(2, f"ts:{t.id}")
    await env.press(2, f"tc:{t.id}")
    assert not api(env, "CreateForumTopic") and not api(env, "GetMe")
    assert all(th is None for uid in (1, 2) for th in threads(env, uid))
    assert (t.passenger_topic_id, t.driver_topic_id) == (None, None)


async def test_topic_per_party_named_from_route_and_time_and_reused_for_updates(env, monkeypatch):
    turn_on(env, monkeypatch, "trip_topics")
    await trip_setup(env)
    t = await the_trip(env)
    made = api(env, "CreateForumTopic")
    assert {m.chat_id for m in made} == {1, 2}
    for m in made:
        assert m.name.startswith("🚕 Qo'shrabot → Samarqand · ") and len(m.name) <= 128
        assert m.icon_color in (7322096, 16766590, 13338331, 9367192, 16749490, 16478047)
    assert t.passenger_topic_id and t.driver_topic_id and t.passenger_topic_id != t.driver_topic_id
    assert threads(env, 1)[-1] == t.passenger_topic_id and threads(env, 2)[-1] == t.driver_topic_id   # the cards
    assert len(api(env, "GetMe")) == 1                                                                 # cached below

    await env.press(2, f"ts:{t.id}")                                    # started → passenger's topic
    assert threads(env, 1)[-1] == t.passenger_topic_id and env.said(1, tx("bot.trip.started_passenger"))
    await env.press(2, f"tc:{t.id}")                                    # completed → both rating prompts in their topics
    assert threads(env, 1)[-1] == t.passenger_topic_id and threads(env, 2)[-1] == t.driver_topic_id
    assert len(api(env, "CreateForumTopic")) == 2                       # nothing created a second time


async def test_cancel_goes_to_the_other_partys_topic(env, monkeypatch):
    turn_on(env, monkeypatch, "trip_topics")
    await trip_setup(env)
    t = await the_trip(env)
    await env.press(1, f"tx:{t.id}")
    await env.press(1, f"ty:{t.id}")
    assert threads(env, 2)[-1] == t.driver_topic_id and env.said(2, tx("bot.trip.cancelled_by_passenger"))


async def test_getme_without_topics_keeps_everything_in_the_main_chat(env, monkeypatch):
    turn_on(env, monkeypatch, "trip_topics")
    env.fake.has_topics = False
    await trip_setup(env)
    t = await the_trip(env)
    assert not api(env, "CreateForumTopic")
    assert all(th is None for th in threads(env, 1) + threads(env, 2))
    assert env.said(1, tx("bot.trip.confirmed")) and env.said(2, tx("bot.trip.confirmed"))     # cards still delivered
    assert (t.passenger_topic_id, t.driver_topic_id) == (None, None)


async def test_topic_creation_error_falls_back_to_the_main_chat(env, monkeypatch):
    turn_on(env, monkeypatch, "trip_topics")
    env.fake.errors[CreateForumTopic] = bad("Bad Request: topics are not enabled")
    await trip_setup(env)
    t = await the_trip(env)
    assert env.said(1, tx("bot.trip.confirmed")) and env.said(2, tx("bot.trip.confirmed"))
    assert all(th is None for th in threads(env, 1) + threads(env, 2))
    assert (t.passenger_topic_id, t.driver_topic_id) == (None, None)
    await env.press(2, f"ts:{t.id}")                                    # later updates: main chat, no new attempts
    assert env.said(1, tx("bot.trip.started_passenger")) and len(env.fake.failed) == 2


async def test_error_inside_an_existing_topic_resends_to_the_main_chat(env, monkeypatch):
    turn_on(env, monkeypatch, "trip_topics")
    await trip_setup(env)
    t = await the_trip(env)
    env.fake.errors[SendMessage] = [bad("Bad Request: message thread not found")]      # the user deleted the topic
    await env.press(2, f"ts:{t.id}")
    started = [c for c in env.sent(1, ("SendMessage",)) if tx("bot.trip.started_passenger") in c.text]
    assert len(started) == 1 and started[0].message_thread_id is None
    assert len(env.fake.failed) == 1


async def test_rich_card_failing_in_a_topic_is_resent_to_the_main_chat(env, monkeypatch):
    turn_on(env, monkeypatch, "trip_topics")
    env.fake.errors[SendRichMessage] = [bad("Bad Request: message thread not found")]
    await trip_setup(env)
    cards = [c for c in api(env, "SendRichMessage") if c.chat_id == 1]
    assert len(cards) == 1 and cards[0].message_thread_id is None


async def test_ensure_topic_reuses_the_stored_thread_and_my_trips_resends_into_it(env, monkeypatch):
    turn_on(env, monkeypatch, "trip_topics")
    await trip_setup(env)
    t = await the_trip(env)
    again = await topics.ensure_topic(env.bot, env.maker, env.runtime.notifier.extra, t.id, "passenger")
    assert again == t.passenger_topic_id and len(api(env, "CreateForumTopic")) == 2
    await env.press(1, f"mt:{t.id}")
    assert threads(env, 1)[-1] == t.passenger_topic_id


def test_topic_name_is_at_most_128_chars():
    r = SimpleNamespace(from_text="A" * 100, to_text="B" * 100, depart_at=None)
    assert len(topics.topic_name(r, bind("uz_new"))) == 128                 # type: ignore[arg-type]


# ============================ B. ephemeral group commands ============================

def group_scope_calls(env):
    return [c for c in api(env, "SetMyCommands") if type(c.scope).__name__ == "BotCommandScopeAllGroupChats"]


async def test_flag_off_publishes_no_group_commands_and_private_menu_is_unchanged(env):
    await commands.set_defaults(env.bot, BotExtra(ephemeral_group=False))
    assert not group_scope_calls(env)
    assert not [cmd for c in api(env, "SetMyCommands") for cmd in c.commands if cmd.is_ephemeral]
    default = [c for c in api(env, "SetMyCommands") if type(c.scope).__name__ == "BotCommandScopeDefault"][-3]
    assert [(c.command, c.description) for c in default.commands] == [
        (n, tx(f"bot.cmd.{n}")) for n in ("start", "qatnovlarim", "til", "yordam")]


async def test_flag_on_publishes_ephemeral_group_commands_only_in_group_scope(env):
    before = len(api(env, "SetMyCommands"))
    await commands.set_defaults(env.bot, BotExtra(ephemeral_group=True))
    calls = api(env, "SetMyCommands")[before:]
    group = [c for c in calls if type(c.scope).__name__ == "BotCommandScopeAllGroupChats"]
    assert len(group) == 3                                                    # uz, ru, en
    assert [(c.command, c.is_ephemeral) for c in group[0].commands] == [("taksi", True), ("yordam", True)]
    for c in calls:                                                           # private/default lists carry no ephemeral
        if c not in group:
            assert not any(cmd.is_ephemeral for cmd in c.commands)
            assert [x.command for x in c.commands] == ["start", "qatnovlarim", "til", "yordam"]


async def test_group_command_with_flag_off_stays_silent_as_before(env):
    await env.user(1)
    await env.say(1, "/taksi", chat="supergroup", ephemeral_message_id=5)
    assert not api(env, "SendMessage") and not env.fake.failed


async def test_group_command_is_answered_ephemerally_to_that_user_only(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    await env.say(1, "/taksi", chat="supergroup", ephemeral_message_id=5)
    (m,) = api(env, "SendMessage")
    assert m.chat_id == -1 and m.ephemeral_message_parameters.receiver_user_id == 1
    assert m.reply_parameters.ephemeral_message_id == 5
    assert tx("bot.group.private_only") in m.text
    (button,) = [b for row in m.reply_markup.inline_keyboard for b in row]
    assert button.url == "https://t.me/tulporgobot?start=order"
    await env.say(1, "/yordam", chat="supergroup")                            # plain group command: no reply target
    last = api(env, "SendMessage")[-1]
    assert last.reply_parameters is None and last.ephemeral_message_parameters.receiver_user_id == 1
    assert last.reply_markup.inline_keyboard[0][0].url.endswith("start=faq")


async def test_ephemeral_failure_or_late_reply_means_silence_not_a_group_message(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    env.fake.errors[SendMessage] = bad("Bad Request: ephemeral messages are not supported")
    await env.say(1, "/taksi", chat="supergroup", ephemeral_message_id=5)
    assert len(env.fake.failed) == 1 and not api(env, "SendMessage")          # no normal fallback: today it was silent
    env.fake.errors.clear()
    await env.say(1, "/taksi", chat="supergroup", ephemeral_message_id=6, date=int(time.time()) - 60)
    assert len(env.fake.failed) == 1 and not api(env, "SendMessage")          # 15 s window passed: not even tried


async def test_group_commands_for_other_bots_and_plain_text_get_nothing(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    await env.say(1, "/taksi@somebody_else_bot", chat="supergroup", ephemeral_message_id=5)
    await env.say(1, "Qo'shrabot → Samarqand 07:30", chat="supergroup")
    assert not api(env, "SendMessage")


async def test_private_commands_still_work_with_the_flag_on(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    await env.say(1, "/yordam")
    assert env.said(1, "Yordam")
    assert all(getattr(c, "ephemeral_message_parameters", None) is None for c in api(env, "SendMessage"))


async def group_press(env, uid: int = 1):
    await env.feed(callback_query={
        "id": "cbq-1", "from": env._from(uid), "chat_instance": "ci", "data": "zzz:old",
        "message": {"message_id": 500, "date": int(time.time()), "chat": {"id": -1001, "type": "supergroup", "title": "T"},
                    "from": {"id": 9_000_000, "is_bot": True, "first_name": "TulporGo"}, "text": "card"}})


async def test_stale_group_button_flag_off_shows_the_alert_as_before(env):
    await env.user(1)
    await group_press(env)
    assert env.alerts() == [tx("bot.stale")] and not api(env, "SendMessage")


async def test_stale_group_button_flag_on_is_answered_ephemerally_without_an_alert(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    await group_press(env)
    (m,) = api(env, "SendMessage")
    assert m.chat_id == -1001 and m.ephemeral_message_parameters.callback_query_id == "cbq-1"
    assert m.ephemeral_message_parameters.receiver_user_id == 1 and not env.alerts()


async def test_stale_group_button_ephemeral_failure_falls_back_to_todays_alert(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    env.fake.errors[SendMessage] = bad("Bad Request: ephemeral messages are not supported")
    await group_press(env)
    assert env.alerts() == [tx("bot.stale")]


async def test_stale_private_button_is_unchanged_with_the_flag_on(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    await env.press(1, "zzz:old")
    assert env.alerts() == [tx("bot.stale")] and not api(env, "SendMessage")


async def test_guest_mode_still_works_with_the_flag_on(env, monkeypatch):
    turn_on(env, monkeypatch, "ephemeral_group")
    await env.user(1)
    await env.guest(1, "@tulporgobot Qo'shrabot → Samarqand 07:30")
    assert len(api(env, "AnswerGuestQuery")) == 1 and not api(env, "SendMessage")


# ================================= C. widgets =================================

def sample(**over):
    trip = SimpleNamespace(id=7, status="confirmed", price=40000)
    r = SimpleNamespace(from_text="Qo'shrabot", to_text="Samarqand", depart_at=None)
    d = SimpleNamespace(car_make="Cobalt", car_color="oq", car_plate="30A123BC")
    for k, v in over.items():
        setattr(r if k in ("from_text", "to_text") else trip, k, v)
    return trip, r, d


async def test_widgets_off_sends_no_widget(env):
    await trip_setup(env)
    assert not api(env, "SendWidget") and env.said(1, tx("bot.trip.confirmed"))


async def test_widget_follows_the_card_in_private_chats_with_the_brand_look(env, monkeypatch):
    turn_on(env, monkeypatch, "widgets")
    await trip_setup(env)
    sent = api(env, "SendWidget")
    assert sorted(w.chat_id for w in sent) == [1, 2]
    w = sent[0]
    assert env.said(1, tx("bot.trip.confirmed")) and env.said(2, tx("bot.trip.confirmed"))     # the normal cards too
    assert env.fake.calls.index(w) > env.fake.calls.index(api(env, "SendRichMessage")[0])
    html = w.html
    for needle in ("#FFC72C", "#111214", "#FFFFFF", "prefers-color-scheme:dark", "Qo'shrabot", "Cobalt",
                   "40 000", "30A123BC", tx("bot.status.confirmed")):
        assert needle in html
    assert "http" not in html and "<script" not in html and "src=" not in html and "<link" not in html
    data = json.loads(w.chat_data)
    assert data["price"] == 40000 and data["status"] == "confirmed" and "Samarqand" in data["route"]
    assert len(w.chat_data.encode()) <= 1024 and widgets.compressed_size(html) <= 4096 and 50 <= w.height <= 600


async def test_widget_error_still_delivers_the_trip_card(env, monkeypatch):
    turn_on(env, monkeypatch, "widgets")
    env.fake.errors[SendWidget] = bad("Bad Request: method not found")
    await trip_setup(env)
    assert len(env.fake.failed) == 2 and not api(env, "SendWidget")
    assert env.said(1, tx("bot.trip.confirmed")) and env.said(2, tx("bot.trip.confirmed"))


async def test_widget_goes_into_the_trip_topic_when_both_flags_are_on(env, monkeypatch):
    turn_on(env, monkeypatch, "widgets", "trip_topics")
    await trip_setup(env)
    t = await the_trip(env)
    by_chat = {w.chat_id: w.message_thread_id for w in api(env, "SendWidget")}
    assert by_chat == {1: t.passenger_topic_id, 2: t.driver_topic_id}


def test_widget_values_are_html_escaped():
    trip, r, d = sample(from_text="<img src=x onerror=alert(1)>&", to_text='"><script>x</script>')
    html = widgets.build_trip_widget(trip, r, d, bind("uz_new")).html
    assert "<img" not in html and "<script>" not in html.split("</style>")[1]
    assert "&lt;img" in html and "&amp;" in html


def test_long_texts_are_clipped_so_the_limits_hold():
    trip, r, d = sample(from_text="A" * 500, to_text="Ж" * 500)
    w = widgets.build_trip_widget(trip, r, d, bind("ru"))
    assert len(w.chat_data.encode()) <= 1024 and widgets.compressed_size(w.html) <= 4096


def test_oversize_widgets_are_refused_before_sending():
    big = "x" * 40000
    with pytest.raises(WidgetError, match="bytes"):
        check_widget(SendWidget(chat_id=1, html=big))                               # > 32768 raw
    noisy = os.urandom(6000).hex()                                                  # 12000 bytes raw, > 4096 compressed
    assert len(noisy) < 32768
    with pytest.raises(WidgetError, match="zlib"):
        check_widget(SendWidget(chat_id=1, html=noisy))
    with pytest.raises(WidgetError, match="chat_data"):
        check_widget(SendWidget(chat_id=1, html="<b>x</b>", chat_data="y" * 1025))
    with pytest.raises(WidgetError, match="public_data"):
        check_widget(SendWidget(chat_id=1, html="<b>x</b>", public_data="y" * 1025))
    with pytest.raises(WidgetError, match="html"):
        check_widget(SendWidget(chat_id=1, html=""))
    with pytest.raises(WidgetError, match="height"):
        check_widget(SendWidget(chat_id=1, html="<b>x</b>", height=700))
    with pytest.raises(WidgetError, match="width"):
        check_widget(SendWidget(chat_id=1, html="<b>x</b>", width=100))
    with pytest.raises(WidgetError, match="caption"):
        check_widget(SendWidget(chat_id=1, html="<b>x</b>", caption="c" * 1025))
    check_widget(SendWidget(chat_id=1, html="<b>x</b>", height=140, width=300))     # the limits themselves are fine


async def test_oversize_widget_makes_no_call(env):
    huge = widgets.TripWidget(html=os.urandom(6000).hex(), chat_data="{}", height=140)
    env.fake.calls.clear()                                                          # start-up menus are not the point
    assert await widgets.send_trip_widget(env.bot, 1, huge) is None
    assert not env.fake.calls and not env.fake.failed


async def test_a_group_chat_never_gets_a_widget(env):
    trip, r, d = sample()
    w = widgets.build_trip_widget(trip, r, d, bind("uz_new"))
    env.fake.calls.clear()
    with pytest.raises(WidgetError, match="private"):
        check_widget(SendWidget(chat_id=-1001, html=w.html))
    assert await widgets.send_trip_widget(env.bot, -1001, w) is None
    assert await widgets.send_trip_widget(env.bot, 0, w) is None
    assert not env.fake.calls and not env.fake.failed


async def test_send_widget_is_a_raw_bot_api_call(env):
    trip, r, d = sample()
    w = widgets.build_trip_widget(trip, r, d, bind("uz_new"))
    assert await widgets.send_trip_widget(env.bot, 1, w, thread_id=9) is not None
    (m,) = api(env, "SendWidget")
    assert SendWidget.__api_method__ == "sendWidget" and m.message_thread_id == 9


async def test_production_defaults_all_on_together(env, monkeypatch):
    """Decision 55: all three on at once (as in production) — the trip still works end to end, the widget lands in the
    party's own trip topic, and the plain card is still delivered for old clients."""
    turn_on(env, monkeypatch, "trip_topics", "ephemeral_group", "widgets")
    await trip_setup(env)
    t = await the_trip(env)
    assert t.passenger_topic_id and t.driver_topic_id
    assert env.said(1, tx("bot.trip.confirmed")) and env.said(2, tx("bot.trip.confirmed"))
    widgets_sent = {w.chat_id: w.message_thread_id for w in api(env, "SendWidget")}
    assert widgets_sent == {1: t.passenger_topic_id, 2: t.driver_topic_id}
    await env.press(2, f"ts:{t.id}")
    await env.press(2, f"tc:{t.id}")
    assert (await the_trip(env)).status == "completed"
    assert len(api(env, "CreateForumTopic")) == 2

