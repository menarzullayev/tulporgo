"""Passenger ↔ driver ↔ trip ↔ rating, end to end through the real dispatcher (fake Telegram, SQLite)."""
from datetime import timedelta

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import GetMe, SendMessage, SendRichMessage
from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import new_request, offer_by_ui, som, tx, walk_to_confirm
from sqlalchemy import select
from tulporgo_bot.delivery import strip_tags
from tulporgo_core.db import utcnow
from tulporgo_core.models import Complaint, Driver, Offer, Rating, RideRequest, Trip, User

PHONE_P, PHONE_D = "+998901234567", "+998902222222"


async def people(env, drivers=1):
    await env.user(1, name="Pasajir", username="pas", phone=PHONE_P)
    await env.driver(2, name="Karim", username="drv", plate="30A123BC", verified=True)
    await env.db(lambda s: _set_phone(s, 2))
    for i in range(1, drivers):
        await env.driver(2 + i, name=f"D{i}", plate=f"30A12{i}BC")


async def _set_phone(s, tg):
    (await s.scalar(select(User).where(User.tg_id == tg))).phone = PHONE_D


async def one(env, model, **where):
    q = select(model)
    for k, v in where.items():
        q = q.where(getattr(model, k) == v)
    return await env.db(lambda s: s.scalar(q.order_by(model.id.desc())))


async def rows(env, model):
    return list(await env.db(lambda s: _scalars(s, model)))


async def _scalars(s, model):
    return list((await s.execute(select(model))).scalars())


async def trip_of(env):
    return await one(env, Trip)


# ---------- the happy path ----------

async def test_full_flow_with_counter_price(env):
    await people(env)
    await env.user(1, name="Pasajir", username="pas", phone=PHONE_P)
    await walk_to_confirm(env, note=None)                                   # the passenger orders by buttons
    await env.press(1, "cf:y")
    rid = await env.db(lambda s: s.scalar(select(RideRequest.id)))
    card = env.last_text(2)                                                 # 1) the driver sees the request
    assert '<tg-time unix="' in env.last_text(2, raw=True)                  # departure as a date_time entity
    assert "Qo'shrabot → Samarqand" in card and tx("bot.seats_n", n=2) in card
    assert env.buttons(2) == [f"ofp:{rid}"]
    assert env.sent(1)[-1].reply_markup is not None                         # (passenger only got "request sent")

    oid = await offer_by_ui(env, 2, rid, "40 000")                          # 2) the driver offers 40 000
    assert tx("bot.offer.sent", price=som(40000)) in strip_tags(env.texts(2)[-1])
    offer_card = env.last_text(1)                                           # 3) the passenger sees car, rating, price
    assert "Cobalt, oq, 30A123BC" in offer_card and tx("bot.verified") in offer_card and "40 000" in offer_card
    assert tx("bot.rating_new") in offer_card
    assert PHONE_D not in offer_card and "drv" not in offer_card            # no contact before the deal
    assert env.buttons(1) == [f"oa:{oid}", f"cn:{oid}", f"od:{oid}"]
    styles = {b.callback_data: b.style for b in env.all_buttons(1) if b.callback_data and b.callback_data.startswith(("oa", "od"))}
    assert styles[f"oa:{oid}"] == "success" and styles[f"od:{oid}"] == "danger"

    await env.press(1, f"cn:{oid}")                                         # 4) counter 30 000
    assert f"cq:{oid}:30000" in env.buttons(1)
    await env.press(1, f"cq:{oid}:30000")
    assert "30 000" in env.last_text(2) and env.buttons(2) == [f"ra:{oid}", f"rd:{oid}"]
    await env.press(2, f"ra:{oid}")                                         # 5) the driver agrees → trip

    trip = await trip_of(env)
    assert trip.price == 30000 and trip.status == "confirmed"
    p_card, d_card = env.sent(1, ("SendRichMessage",))[-1], env.sent(2, ("SendRichMessage",))[-1]
    p_text, d_text = repr(p_card.rich_message.blocks), repr(d_card.rich_message.blocks)
    assert "table" in p_text and "30 000" in p_text and "Cobalt" in p_text and PHONE_D in p_text and "@drv" in p_text
    assert PHONE_P in d_text and "@pas" in d_text and "date_time" in p_text
    assert [x for x in markup_cb(p_card)] == [f"tc:{trip.id}", f"tx:{trip.id}"]
    assert any(b.url and b.url.startswith("https://t.me/share/url?url=") and trip.share_token in b.url
               for b in p_card.reply_markup.inline_keyboard[0])             # "share trip" link (decision 13)
    assert markup_cb(d_card) == [f"ts:{trip.id}", f"tc:{trip.id}", f"tx:{trip.id}"]

    await env.press(2, f"ts:{trip.id}")                                     # 6) start → passenger told
    assert (await trip_of(env)).status == "started"
    assert tx("bot.trip.started_passenger") in env.last_text(1)
    await env.press(1, f"tc:{trip.id}")                                     # 7) complete → both asked for a rating
    assert (await trip_of(env)).status == "completed"
    assert env.buttons(1)[:5] == [f"rt:{trip.id}:{n}" for n in range(1, 6)]
    assert env.buttons(2)[:5] == [f"rt:{trip.id}:{n}" for n in range(1, 6)]
    await env.press(1, f"rt:{trip.id}:5")
    await env.press(2, f"rt:{trip.id}:4")
    driver = await one(env, Driver)
    assert (driver.rating_sum, driver.rating_count) == (5, 1)               # passenger rated the driver
    assert await env.db(lambda s: s.scalar(select(Rating.stars).where(Rating.from_user_id == driver.user_id))) == 4


def markup_cb(call):
    return [b.callback_data for row in call.reply_markup.inline_keyboard for b in row if b.callback_data]


# ---------- offers: who may do what ----------

async def test_other_drivers_only_get_the_card_and_losers_are_told(env):
    await people(env, drivers=2)
    rid = await new_request(env, 1, seats=2)
    assert env.buttons(2) == [f"ofp:{rid}"] and env.buttons(3) == [f"ofp:{rid}"]
    o2 = await offer_by_ui(env, 2, rid, "40000")
    await offer_by_ui(env, 3, rid, "38000")
    await env.press(1, f"oa:{o2}")
    assert env.said(1, tx("bot.offer.accepted", price=som(40000)))
    lost = tx("bot.offer.lost", route="Qo'shrabot → Samarqand")
    assert lost in env.last_text(3) and env.sent(1, ("SendRichMessage",))
    assert len(env.sent(3, ("SendRichMessage",))) == 0                      # the loser gets no trip card
    await env.press(1, f"oa:{o2}")                                          # accepting twice changes nothing
    assert len(await rows(env, Trip)) == 1


async def test_stranger_cannot_accept_counter_or_decline_someone_elses_offer(env):
    await people(env)
    await env.user(9)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    for action in (f"oa:{oid}", f"cn:{oid}", f"od:{oid}", f"cq:{oid}:30000"):
        await env.press(9, action)
        assert env.alerts()[-1] == tx("bot.err.not_your_request")
    assert (await one(env, Offer)).status == "sent" and await trip_of(env) is None


async def test_non_driver_cannot_offer_or_answer_counters(env):
    await people(env)
    await env.user(9)
    rid = await new_request(env, 1)
    await env.press(9, f"ofp:{rid}")
    assert env.alerts()[-1] == tx("bot.err.not_driver")
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(9, f"ra:{oid}")
    assert env.alerts()[-1] == tx("bot.err.not_driver")
    await env.press(1, f"cq:{oid}:30000")
    await env.driver(5, plate="30A555BC")
    await env.press(5, f"ra:{oid}")                                         # a driver, but not THIS offer's driver
    assert env.alerts()[-1] == tx("bot.err.not_your_offer")
    assert await trip_of(env) is None


async def test_bad_prices_are_refused(env):
    await people(env)
    rid = await new_request(env, 1)
    await env.press(2, f"ofp:{rid}")
    await env.press(2, f"ofc:{rid}")
    await env.say(2, "arzon")
    assert tx("bot.err.bad_price") in env.last_text(2)                      # not a number → asked again
    await env.say(2, "500")
    assert env.last_text(2) == tx("bot.err.bad_price")                      # below the core minimum
    assert await one(env, Offer) is None
    await env.say(2, "45000")                                               # the state was kept: a good price works
    assert (await one(env, Offer)).price == 45000


async def test_counter_must_be_lower_and_numeric(env):
    await people(env)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(1, f"cn:{oid}")
    await env.say(1, "50000")
    assert env.last_text(1) == tx("bot.err.counter_must_be_lower")
    await env.say(1, "narx")
    assert tx("bot.err.bad_price") in env.last_text(1)
    assert (await one(env, Offer)).status == "sent"
    await env.say(1, "35000")
    assert (await one(env, Offer)).counter_price == 35000


async def test_driver_keeps_the_price_after_a_counter(env):
    await people(env)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(1, f"cq:{oid}:30000")
    await env.press(2, f"rd:{oid}")
    o = await one(env, Offer)
    assert (o.status, o.price, o.counter_price) == ("sent", 40000, None)
    assert tx("bot.counter.refused") in env.last_text(1) and env.buttons(1) == [f"oa:{oid}", f"cn:{oid}", f"od:{oid}"]


async def test_passenger_declines_and_driver_is_told(env):
    await people(env)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(1, f"od:{oid}")
    assert (await one(env, Offer)).status == "declined"
    assert tx("bot.offer.declined_driver", route="Qo'shrabot → Samarqand") in env.last_text(2)
    await env.press(1, f"oa:{oid}")                                         # a declined offer cannot be accepted
    assert env.alerts()[-1] == tx("bot.err.offer_not_open") and await trip_of(env) is None


async def test_driver_can_withdraw_but_not_after_acceptance(env):
    await people(env)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    assert f"ow:{oid}" in env.buttons(2)
    await env.press(2, f"ow:{oid}")
    assert (await one(env, Offer)).status == "withdrawn"
    rid2 = await new_request(env, 1)
    oid2 = await offer_by_ui(env, 2, rid2, "41000")
    await env.press(1, f"oa:{oid2}")
    await env.press(2, f"ow:{oid2}")
    assert env.alerts()[-1] == tx("bot.err.offer_not_open")


async def test_expired_subscription_gets_no_cards_and_cannot_offer(env):
    await people(env)
    await env.db(lambda s: _expire_sub(s, 2))
    rid = await new_request(env, 1)
    assert env.sent(2) == []                                                # no card for a driver without a subscription
    await env.press(2, f"ofq:{rid}:40000")
    assert env.alerts()[-1] == tx("bot.err.subscription_required")
    assert await one(env, Offer) is None


async def _expire_sub(s, tg):
    d = await s.scalar(select(Driver).join(User, User.id == Driver.user_id).where(User.tg_id == tg))
    d.subscription_until = utcnow() - timedelta(days=1)


async def test_free_period_keeps_everyone_active(free_env):
    env = free_env
    await people(env)
    await env.db(lambda s: _expire_sub(s, 2))
    rid = await new_request(env, 1)
    assert env.buttons(2) == [f"ofp:{rid}"]                                 # decision 44: free period


async def test_blocked_driver_and_own_request_get_no_card(env):
    await people(env)
    await env.user(2, blocked=True)
    rid = await new_request(env, 1)
    assert env.sent(2) == []
    await env.user(2, blocked=False, phone=PHONE_D)
    await env.driver(5, plate="30A555BC")
    rid2 = await new_request(env, 5)                                        # a driver's own request is not shown to them
    assert env.buttons(5) == [] and env.buttons(2) == [f"ofp:{rid2}"]       # the unblocked driver 2 sees only the other's


async def test_women_marker_and_note_in_driver_card(env):
    await people(env)
    await env.user(1, woman=True)
    await new_request(env, 1, note="yuk bor")
    card = env.last_text(2)
    assert tx("bot.women_marker") in card and "yuk bor" in card


async def test_quick_prices_around_the_hint(env):
    await people(env)
    rid = await new_request(env, 1, hint=40_000)
    assert "40 000" in env.texts(2)[0]                                      # the card shows the hint
    await env.press(2, f"ofp:{rid}")
    assert env.buttons(2) == [f"ofq:{rid}:35000", f"ofq:{rid}:40000", f"ofq:{rid}:45000", f"ofc:{rid}"]
    await env.press(2, f"ofq:{rid}:45000")
    assert (await one(env, Offer)).price == 45000


async def test_no_quick_prices_without_a_hint(env):
    await people(env)
    rid = await new_request(env, 1)
    await env.press(2, f"ofp:{rid}")
    assert env.buttons(2) == [f"ofc:{rid}"]                                 # never an invented price


async def test_offer_on_a_closed_request_is_refused(env):
    await people(env)
    rid = await new_request(env, 1)
    await env.press(1, f"rq:c:{rid}")
    await env.press(2, f"ofq:{rid}:40000")
    assert env.alerts()[-1] == tx("bot.err.request_not_open")


# ---------- the trip ----------

async def started_trip(env, start=True):
    await people(env)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(1, f"oa:{oid}")
    trip = await trip_of(env)
    if start:
        await env.press(2, f"ts:{trip.id}")
    return rid, trip


async def test_only_the_driver_starts_and_strangers_do_nothing(env):
    rid, trip = await started_trip(env, start=False)
    await env.user(9)
    await env.press(1, f"ts:{trip.id}")
    assert env.alerts()[-1] == tx("bot.err.driver_only")
    await env.press(9, f"ts:{trip.id}")
    assert env.alerts()[-1] == tx("bot.err.not_your_trip")
    for data in (f"tc:{trip.id}", f"tx:{trip.id}", f"ty:{trip.id}"):
        await env.press(9, data)
        assert env.alerts()[-1] == tx("bot.err.not_your_trip")
    assert (await trip_of(env)).status == "confirmed"


async def test_passenger_cannot_cancel_a_started_trip(env):
    rid, trip = await started_trip(env)
    await env.press(1, f"ty:{trip.id}")
    assert env.alerts()[-1] == tx("bot.err.trip_not_cancellable")
    assert (await trip_of(env)).status == "started"
    await env.press(2, f"ts:{trip.id}")                                     # and it cannot be started twice
    assert env.alerts()[-1] == tx("bot.err.trip_not_confirmed")


async def test_cancel_asks_first_and_no_keeps_the_trip(env):
    rid, trip = await started_trip(env, start=False)
    await env.press(1, f"tx:{trip.id}")
    assert env.buttons(1)[-2:] == [f"ty:{trip.id}", f"tn:{trip.id}"]
    await env.press(1, f"tn:{trip.id}")
    assert (await trip_of(env)).status == "confirmed" and env.methods("DeleteMessage")


async def test_driver_cancels_before_start_request_reopens_for_others(env):
    await people(env, drivers=2)
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(1, f"oa:{oid}")
    trip = await trip_of(env)
    n3 = len(env.sent(3))
    await env.press(2, f"ty:{trip.id}")
    assert (await trip_of(env)).status == "cancelled"
    assert (await env.db(lambda s: s.get(RideRequest, rid))).status == "open"
    assert tx("bot.trip.cancelled_by_driver_reopened") in env.last_text(1)
    assert len(env.sent(3)) == n3 + 1                                       # the request goes out to the others again
    assert env.sent(2)[-1] is not None and len([c for c in env.sent(2) if "ofp:" in str(c.reply_markup)]) == 1
    # the cancelling driver is not asked again: his offer is withdrawn (closed for him)


async def test_passenger_cancels_before_start_driver_is_told(env):
    rid, trip = await started_trip(env, start=False)
    await env.press(1, f"ty:{trip.id}")
    assert (await env.db(lambda s: s.get(RideRequest, rid))).status == "cancelled"
    assert tx("bot.trip.cancelled_by_passenger") in env.last_text(2)


async def test_rating_rules(env):
    rid, trip = await started_trip(env)
    await env.press(1, f"rt:{trip.id}:5")                                   # before completion
    assert env.alerts()[-1] == tx("bot.err.trip_not_completed")
    await env.press(1, f"tc:{trip.id}")
    await env.user(9)
    await env.press(9, f"rt:{trip.id}:5")
    assert env.alerts()[-1] == tx("bot.err.not_your_trip")
    await env.press(1, f"rt:{trip.id}:6")
    assert env.alerts()[-1] == tx("bot.err.bad_stars")
    await env.press(1, f"rt:{trip.id}:5")
    await env.press(1, f"rt:{trip.id}:1")                                   # second rating of the same trip
    assert env.alerts()[-1] == tx("bot.err.already_rated")
    assert (await one(env, Driver)).rating == 5.0


async def test_complaint_flow_notifies_admins_and_validates(env):
    await env.user(50, name="Admin", admin=True)
    rid, trip = await started_trip(env)
    await env.press(1, f"tc:{trip.id}")
    await env.press(1, f"cm:{trip.id}")
    await env.say(1, "yo'q")                                               # too short
    assert env.last_text(1) == tx("bot.err.complaint_too_short")
    assert await one(env, Complaint) is None
    await env.say(1, "Haydovchi kech keldi va mazmunsiz gapirdi")
    c = await one(env, Complaint)
    assert c.trip_id == trip.id and c.against_user_id == (await one(env, Driver)).user_id
    assert tx("bot.complaint.thanks") in env.last_text(1)
    assert "kech keldi" in env.last_text(50)                                # the admin got it
    await env.say(1, "yana yozaman")                                        # the flow ended: free text is not a complaint
    assert len(await rows(env, Complaint)) == 1


async def test_complaint_about_someone_elses_trip_is_refused(env):
    rid, trip = await started_trip(env)
    await env.user(9)
    await env.press(9, f"cm:{trip.id}")
    assert env.alerts()[-1] == tx("bot.err.not_your_trip")
    await env.say(9, "Men bu qatnovni ko'rmaganman")
    assert await one(env, Complaint) is None


async def test_general_complaint_from_help(env):
    await env.user(1)
    await env.say(1, "/yordam")
    await env.press(1, "cm:0")
    await env.say(1, "Ilova menga yoqmadi, tuzating")
    c = await one(env, Complaint)
    assert c.trip_id is None and c.against_user_id is None


# ---------- delivery: fallbacks, 429, blocked bot ----------

async def test_rich_message_failure_falls_back_to_plain_html(env):
    await people(env)
    env.fake.errors[SendRichMessage] = TelegramBadRequest(method=SendRichMessage(chat_id=1, rich_message={"html": "x"}),
                                                          message="Bad Request: method not found")
    rid = await new_request(env, 1)
    oid = await offer_by_ui(env, 2, rid, "40000")
    await env.press(1, f"oa:{oid}")
    d_card = env.last_text(2)
    assert "Cobalt" in d_card and PHONE_P in d_card and "30 000" not in d_card and "40 000" in d_card
    assert env.sent(1, ("SendMessage",))[-1].reply_markup is not None
    assert not env.sent(1, ("SendRichMessage",)) or env.fake.errors                # the rich attempt was made first


async def test_retry_after_is_honoured_then_delivered(env):
    await people(env, drivers=2)
    env.fake.errors[SendMessage] = [TelegramRetryAfter(method=SendMessage(chat_id=1, text="x"), message="Too Many Requests",
                                                       retry_after=2)]
    await new_request(env, 1)
    assert env.buttons(2) and env.buttons(3)                                # both drivers got their card in the end


async def test_driver_who_blocked_the_bot_does_not_stop_the_others(env):
    await people(env, drivers=2)
    env.fake.errors[SendMessage] = [TelegramForbiddenError(method=SendMessage(chat_id=1, text="x"),
                                                           message="Forbidden: bot was blocked by the user")]
    rid = await new_request(env, 1)
    assert sum(1 for d in (2, 3) if env.buttons(d) == [f"ofp:{rid}"]) == 1


async def test_domain_error_rolls_back_and_unexpected_error_is_polite(env, monkeypatch):
    await people(env)
    rid = await new_request(env, 1)
    from tulporgo_core.services import rides
    boom = {"n": 0}
    real = rides.send_offer

    async def failing(*a, **kw):
        boom["n"] += 1
        raise RuntimeError("database exploded")
    monkeypatch.setattr(rides, "send_offer", failing)
    await env.press(2, f"ofq:{rid}:40000")
    assert env.alerts()[-1] == tx("common.error") and boom["n"] == 1        # no stack trace for the user
    monkeypatch.setattr(rides, "send_offer", real)
    await env.press(2, f"ofq:{rid}:40000")
    assert (await one(env, Offer)).price == 40000                            # and the bot keeps working


async def test_events_are_not_delivered_when_the_update_fails(env):
    await people(env)
    rid = await new_request(env, 1)
    n_before = len(env.bus.published)
    await env.press(2, f"ofq:{rid}:100")                                     # bad price → Invalid → rolled back
    assert len(env.bus.published) == n_before and await one(env, Offer) is None


async def test_user_text_is_html_escaped_in_every_card(env):
    await env.user(1, phone=PHONE_P)
    await env.driver(2, name="Drv & Co", username="drv")
    await env.db(lambda s: _make_make(s, "<i>Cobalt</i>"))
    rid = await new_request(env, 1, note="<b>shoshiling</b> & tez")
    raw = env.last_text(2, raw=True)
    assert "&lt;b&gt;shoshiling&lt;/b&gt; &amp; tez" in raw and "<b>shoshiling" not in raw
    oid = await offer_by_ui(env, 2, rid, "40000")
    assert "&lt;i&gt;Cobalt&lt;/i&gt;" in env.last_text(1, raw=True)
    env.fake.errors[SendRichMessage] = TelegramBadRequest(method=GetMe(), message="Bad Request: no rich messages")
    await env.press(1, f"oa:{oid}", name="<b>Pas</b>")                     # trip cards fall back to HTML
    assert "&lt;b&gt;Pas&lt;/b&gt;" in env.last_text(2, raw=True) and "<b>Pas</b>" not in env.last_text(2, raw=True)


async def _make_make(s, value):
    (await s.scalar(select(Driver))).car_make = value
