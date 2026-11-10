"""Message cards (pure functions: models + `t` → HTML / rich blocks). No I/O, so they are easy to test."""
from datetime import datetime
from urllib.parse import quote

from tulporgo_core.models import Driver, Offer, RideRequest, Trip, User

from .common import btn, contact_html, esc, kb, person, price, rating_text, time_html, time_plain, to_local, unix


def route(from_text: str, to_text: str) -> str:
    return f"📍 {esc(from_text)} → {esc(to_text)}"


def seats_line(n: int, t) -> str:
    return f"👥 {t('bot.seats_n', n=n)}"


def order_preview(o: dict, depart: datetime | None, hint: int | None, t, women: bool = False) -> str:
    """The confirmation card the passenger sees before the request is created."""
    lines = [f"<b>{t('bot.order.confirm_title')}</b>", route(o["from_text"], o["to_text"]),
             f"🕐 {time_html(depart, t)}", seats_line(o["seats"], t)]
    if o.get("note"):
        lines.append(f"📝 {esc(o['note'])}")
    if hint:
        lines.append(f"💰 {t('bot.price_hint', price=price(hint, t))}")
    if women:
        lines.append(f"👩 {t('bot.women_marker')}")
    return "\n".join(lines)


def request_card(r: RideRequest, t) -> str:
    """What a driver sees: route, time, seats, price hint, women-only marker. No passenger identity."""
    lines = [f"<b>{t('bot.driver.new_request')}</b>", route(r.from_text, r.to_text),
             f"🕐 {time_html(r.depart_at, t)}", seats_line(r.seats, t)]
    if r.price_hint:
        lines.append(f"💰 {t('bot.price_hint', price=price(r.price_hint, t))}")
    if r.women_only:
        lines.append(f"👩 {t('bot.women_marker')}")
    if r.note:
        lines.append(f"📝 {esc(r.note)}")
    return "\n".join(lines)


def car_line(d: Driver) -> str:
    return f"🚗 {esc(d.car_make)}, {esc(d.car_color)}, {esc(d.car_plate)}"


def offer_card(o: Offer, d: Driver, r: RideRequest, t) -> str:
    """What the passenger sees for an offer: car, driver rating, badge, price — but no phone number yet."""
    badge = f" · ✅ {t('bot.verified')}" if d.verified else ""
    lines = [f"<b>{t('bot.offer.title')}</b>", route(r.from_text, r.to_text), car_line(d),
             f"{rating_text(d, t)}{badge}", f"💰 <b>{price(o.price, t)}</b>"]
    if o.message:
        lines.append(f"💬 {esc(o.message)}")
    return "\n".join(lines)


def trip_html(trip: Trip, r: RideRequest, d: Driver, passenger: User, for_driver: bool, t) -> str:
    """Plain HTML trip card — the fallback when Rich Messages are not available."""
    other = passenger if for_driver else d.user
    lines = [f"<b>{t('bot.trip.confirmed')}</b>", route(r.from_text, r.to_text), f"🕐 {time_html(r.depart_at, t)}",
             f"💰 {price(trip.price, t)}", car_line(d), seats_line(r.seats, t),
             f"👤 {t('bot.trip.passenger' if for_driver else 'bot.trip.driver')}: {contact_html(other)}"]
    return "\n".join(lines)


def trip_rich(trip: Trip, r: RideRequest, d: Driver, passenger: User, for_driver: bool, t) -> list[dict]:
    """Rich Message blocks (Bot API 10.1): heading + table with route, time, price, car, contact."""
    other = passenger if for_driver else d.user
    when = (t("bot.when_now") if r.depart_at is None else
            {"type": "date_time", "text": time_plain(r.depart_at, t), "unix_time": unix(r.depart_at),
             "date_time_format": "dt"})
    contact = " · ".join(x for x in (other.first_name or "", other.phone or "", f"@{other.username}" if other.username else "") if x)
    rows = [(t("bot.trip.route"), f"{r.from_text} → {r.to_text}"), (t("bot.trip.time"), when),
            (t("bot.trip.price"), price(trip.price, t)),
            (t("bot.trip.car"), f"{d.car_make}, {d.car_color}, {d.car_plate}"),
            (t("bot.trip.seats"), str(r.seats)),
            (t("bot.trip.passenger" if for_driver else "bot.trip.driver"), contact or "—")]
    cells = [[{"align": "left", "valign": "middle", "text": label, "is_header": True},
              {"align": "left", "valign": "middle", "text": value}] for label, value in rows]
    return [{"type": "heading", "text": t("bot.trip.confirmed"), "size": 2},
            {"type": "table", "cells": cells, "is_bordered": True, "is_striped": True}]


def share_url(settings, trip: Trip, t) -> str:
    link = f"https://t.me/{settings.bot_username}?start=trip_{trip.share_token}"
    return f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(t('bot.share_text'), safe='')}"


def trip_status(trip: Trip, r: RideRequest, d: Driver, t) -> str:
    """Read-only card for the people the passenger shared the trip with (decision 13)."""
    started = to_local(trip.started_at).strftime("%H:%M") if trip.started_at else "—"
    return "\n".join([f"<b>{t('bot.share.title')}</b>", route(r.from_text, r.to_text), f"🕐 {time_html(r.depart_at, t)}",
                      car_line(d), f"👤 {person(d.user)}", f"{t('bot.share.status')}: {t('bot.status.' + trip.status)}",
                      f"{t('bot.share.started')}: {started}"])


# ---------- keyboards that belong to the cards ----------

def request_keyboard(r: RideRequest, t):
    return kb([btn(f"💰 {t('bot.btn.make_offer')}", f"ofp:{r.id}", style="primary")])


def quick_prices(hint: int | None) -> list[int]:
    """Prices around the route's price hint (decision 7); no hint → no invented numbers, the driver types one."""
    if not hint:
        return []
    return sorted({p for p in (hint - 5000, hint, hint + 5000) if p >= 1000})


def price_keyboard(r: RideRequest, t):
    quick = [btn(price(p, t), f"ofq:{r.id}:{p}") for p in quick_prices(r.price_hint)]
    return kb(quick, [btn(f"✍ {t('bot.btn.other_price')}", f"ofc:{r.id}")])


def offer_keyboard(o: Offer, t):
    return kb([btn(f"✅ {t('bot.btn.accept')}", f"oa:{o.id}", style="success"),
               btn(f"💬 {t('bot.btn.counter')}", f"cn:{o.id}")],
              [btn(f"✖ {t('bot.btn.decline')}", f"od:{o.id}", style="danger")])


def counter_keyboard(o: Offer, t):
    return kb([btn(f"✅ {t('bot.btn.accept')}", f"ra:{o.id}", style="success"),
               btn(f"✖ {t('bot.btn.decline')}", f"rd:{o.id}", style="danger")])


def trip_keyboard(trip: Trip, role: str, settings, t, driver_user: User | None = None, started: bool = False):
    """role = driver | passenger. Driver: Start / Complete / Cancel. Passenger: Share / Complete / Cancel."""
    rows = []
    if role == "driver":
        if not started:
            rows.append([btn(f"▶ {t('bot.btn.start_trip')}", f"ts:{trip.id}", style="primary")])
    else:
        rows.append([btn(f"🔗 {t('bot.btn.share')}", url=share_url(settings, trip, t))])
        if driver_user is not None and driver_user.username:
            rows.append([btn(f"💬 {t('bot.btn.write_driver')}", url=f"https://t.me/{driver_user.username}")])
    rows.append([btn(f"🏁 {t('bot.btn.complete')}", f"tc:{trip.id}", style="success"),
                 btn(f"✖ {t('bot.btn.cancel_trip')}", f"tx:{trip.id}", style="danger")])
    return kb(*rows)


def rating_keyboard(trip: Trip, t):
    return kb([btn(f"⭐{n}", f"rt:{trip.id}:{n}") for n in range(1, 6)],
              [btn(f"📝 {t('bot.btn.complaint')}", f"cm:{trip.id}")])
