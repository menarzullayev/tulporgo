"""Passenger order (decision 47): buttons (district → mahalla, time, seats, note), free text, Mini App button.
Guest Mode lives in guest.py; its deep link lands in `start_from_guest` below."""
import re
from datetime import datetime, time, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.db import utcnow
from tulporgo_core.enums import RequestSource
from tulporgo_core.models import Place, User
from tulporgo_core.parser import parse
from tulporgo_core.places import PlaceIndex
from tulporgo_core.services import pricing, rides

from .. import ephemeral
from ..config import get_extra
from . import picker
from .cards import order_preview
from .common import PRIVATE, UZT, btn, deep_link, int_arg, kb, local_to_utc, parse_cb, show, to_local
from .states import Order

router = Router(name="order")
router.message.filter(F.chat.type == PRIVATE)
fallback = Router(name="order_fallback")              # included LAST: free text and stale buttons
TIME_RE = re.compile(r"^\s*([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)\s*$")


# ---------- start ----------

@router.callback_query(F.data == "ord:new")
async def new_order(cb: CallbackQuery, state: FSMContext, session: AsyncSession, t, lang) -> None:
    await cb.answer()
    await state.clear()
    await state.update_data(o={"source": RequestSource.BUTTONS})
    await picker.ask_place(cb, state, session, t, lang, "f")


async def chosen_from(event, state: FSMContext, *, place: Place | None, text: str, session, t, lang, **_) -> None:
    o = (await state.get_data()).get("o") or {"source": RequestSource.BUTTONS}
    o.update(from_id=place.id if place else None, from_text=text)
    await state.update_data(o=o)
    await picker.ask_place(event, state, session, t, lang, "t")


async def chosen_to(event, state: FSMContext, *, place: Place | None, text: str, session, t, lang, **_) -> None:
    o = (await state.get_data()).get("o") or {"source": RequestSource.BUTTONS}
    if (place and place.id == o.get("from_id")) or text.strip().lower() == str(o.get("from_text", "")).strip().lower():
        await event.answer(t("bot.err.same_place"), show_alert=True)
        return
    o.update(to_id=place.id if place else None, to_text=text)
    await state.update_data(o=o)
    await state.set_state(Order.time)
    await show(event, t("bot.time.ask"), kb(
        [btn(f"⚡ {t('bot.time.now')}", "tm:now", style="primary")],
        [btn(t("bot.time.today"), "tm:d:0"), btn(t("bot.time.tomorrow"), "tm:d:1")]))


picker.register_chooser("f", chosen_from)
picker.register_chooser("t", chosen_to)


# ---------- time ----------

def _hours_keyboard(day: int, t):
    now = to_local(utcnow())
    hours = [h for h in range(24) if day == 1 or h > now.hour]
    rows = [[btn(f"{h:02d}:00", f"tm:h:{day}:{h}") for h in hours[i:i + 4]] for i in range(0, len(hours), 4)]
    rows.append([btn(f"↩ {t('common.back')}", "tm:back")])
    return kb(*rows)


@router.callback_query(StateFilter(Order.time), F.data == "tm:back")
async def time_back(cb: CallbackQuery, t) -> None:
    await cb.answer()
    await show(cb, t("bot.time.ask"), kb(
        [btn(f"⚡ {t('bot.time.now')}", "tm:now", style="primary")],
        [btn(t("bot.time.today"), "tm:d:0"), btn(t("bot.time.tomorrow"), "tm:d:1")]))


@router.callback_query(StateFilter(Order.time), F.data == "tm:now")
async def time_now(cb: CallbackQuery, state: FSMContext, t) -> None:
    await cb.answer()
    await _set_time(cb, state, None, t)


@router.callback_query(StateFilter(Order.time), F.data.startswith("tm:d:"))
async def time_day(cb: CallbackQuery, t) -> None:
    parts = parse_cb(cb.data, 3)
    day = int_arg(parts[2]) if parts else None
    if day not in (0, 1):
        await cb.answer()
        return
    await cb.answer()
    await show(cb, t("bot.time.pick_hour"), _hours_keyboard(day, t))


@router.callback_query(StateFilter(Order.time), F.data.startswith("tm:h:"))
async def time_hour(cb: CallbackQuery, t) -> None:
    parts = parse_cb(cb.data, 4)
    day, hour = (int_arg(parts[2]), int_arg(parts[3])) if parts else (None, None)
    if day not in (0, 1) or hour is None or hour > 23:
        await cb.answer()
        return
    await cb.answer()
    await show(cb, t("bot.time.pick_min", hour=f"{hour:02d}"), kb(
        [btn(f"{hour:02d}:{m:02d}", f"tm:m:{day}:{hour}:{m}") for m in (0, 15, 30, 45)],
        [btn(f"↩ {t('common.back')}", f"tm:d:{day}")]))


@router.callback_query(StateFilter(Order.time), F.data.startswith("tm:m:"))
async def time_minute(cb: CallbackQuery, state: FSMContext, t) -> None:
    parts = parse_cb(cb.data, 5)
    day, hour, minute = (int_arg(p) for p in parts[2:]) if parts else (None, None, None)
    if day is None or hour is None or minute is None or day not in (0, 1) or hour > 23 or minute > 59:
        await cb.answer()
        return
    await cb.answer()
    local = datetime.combine((to_local(utcnow()) + timedelta(days=day)).date(), time(hour, minute), UZT)
    await _set_time(cb, state, local_to_utc(local), t)


@router.message(StateFilter(Order.time), F.text, ~F.text.startswith("/"))
async def time_typed(msg: Message, state: FSMContext, t) -> None:
    m = TIME_RE.match(msg.text or "")
    if not m:
        await show(msg, t("bot.time.bad"))
        return
    now = to_local(utcnow())
    local = datetime.combine(now.date(), time(int(m[1]), int(m[2])), UZT)
    if local < now + timedelta(minutes=5):
        local += timedelta(days=1)                       # "07:30" typed in the evening means tomorrow morning
    await _set_time(msg, state, local_to_utc(local), t)


async def _set_time(event, state: FSMContext, depart: datetime | None, t) -> None:
    o = (await state.get_data()).get("o", {})
    o["depart"] = depart.isoformat() if depart else None
    await state.update_data(o=o)
    await state.set_state(Order.seats)
    await show(event, t("bot.seats.ask"), kb([btn(str(n), f"st:{n}") for n in (1, 2, 3, 4)]))


# ---------- seats, note ----------

@router.callback_query(StateFilter(Order.seats), F.data.startswith("st:"))
async def seats_button(cb: CallbackQuery, state: FSMContext, t) -> None:
    parts = parse_cb(cb.data, 2)
    n = int_arg(parts[1]) if parts else None
    if n is None or not 1 <= n <= 8:
        await cb.answer()
        return
    await cb.answer()
    await _set_seats(cb, state, n, t)


@router.message(StateFilter(Order.seats), F.text, ~F.text.startswith("/"))
async def seats_typed(msg: Message, state: FSMContext, t) -> None:
    text = (msg.text or "").strip()
    if not text.isdigit() or not 1 <= int(text) <= 8:
        await show(msg, t("bot.seats.bad"))
        return
    await _set_seats(msg, state, int(text), t)


async def _set_seats(event, state: FSMContext, n: int, t) -> None:
    o = (await state.get_data()).get("o", {})
    o["seats"] = n
    await state.update_data(o=o)
    await state.set_state(Order.note)
    await show(event, t("bot.note.ask"), kb([btn(t("bot.btn.skip"), "nt:skip")]))


@router.callback_query(StateFilter(Order.note), F.data == "nt:skip")
async def note_skip(cb: CallbackQuery, state: FSMContext, session, user, t) -> None:
    await cb.answer()
    await confirm_card(cb, state, session, user, t)


@router.message(StateFilter(Order.note), F.text, ~F.text.startswith("/"))
async def note_typed(msg: Message, state: FSMContext, session, user, t) -> None:
    o = (await state.get_data()).get("o", {})
    o["note"] = (msg.text or "").strip()[:200]
    await state.update_data(o=o)
    await confirm_card(msg, state, session, user, t)


# ---------- confirm ----------

def depart_of(o: dict) -> datetime | None:
    return datetime.fromisoformat(o["depart"]) if o.get("depart") else None


async def confirm_card(event, state: FSMContext, session: AsyncSession, user: User, t, extra_rows=()) -> None:
    o = (await state.get_data())["o"]
    hint = await pricing.price_hint(session, o.get("from_id"), o.get("to_id"))
    await state.set_state(Order.confirm)
    await show(event, order_preview(o, depart_of(o), hint, t, women=user.is_woman), kb(
        [btn(f"✅ {t('bot.btn.confirm')}", "cf:y", style="success"), btn(t("common.cancel"), "cf:n", style="danger")],
        *extra_rows))


@router.callback_query(StateFilter(Order.confirm), F.data == "cf:y")
async def confirm_yes(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, settings: Settings,
                      bus, t) -> None:
    o = (await state.get_data()).get("o")
    if not o:
        await cb.answer(t("bot.stale"), show_alert=True)
        return
    r = await rides.create_request(session, user, settings, from_text=o["from_text"], to_text=o["to_text"],
                                   from_place_id=o.get("from_id"), to_place_id=o.get("to_id"),
                                   depart_at=depart_of(o), seats=o.get("seats", 1), note=o.get("note"),
                                   source=o.get("source", RequestSource.BUTTONS), bus=bus)
    await cb.answer()
    await state.clear()
    await show(cb, t("bot.order.created") + f"\n\n{o['from_text']} → {o['to_text']}",
               kb([btn(f"✖ {t('bot.btn.cancel_request')}", f"rq:c:{r.id}", style="danger")]))


@router.callback_query(StateFilter(Order.confirm), F.data == "cf:n")
async def confirm_no(cb: CallbackQuery, state: FSMContext, t) -> None:
    await cb.answer()
    await state.clear()
    await show(cb, t("bot.order.dismissed"))


# ---------- free text (decision 47b) and Guest Mode deep link ----------

async def _offer_parsed(msg: Message, state: FSMContext, session: AsyncSession, user: User, t, o: dict) -> None:
    await state.set_state(Order.confirm)
    await state.update_data(o=o)
    await confirm_card(msg, state, session, user, t, extra_rows=([btn(f"✏ {t('bot.btn.change')}", "ord:new")],))


@fallback.message(StateFilter(default_state), F.chat.type == PRIVATE, F.text, ~F.text.startswith("/"))
async def free_text(msg: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings, t) -> None:
    parsed = parse(msg.text or "", await PlaceIndex.load(session), utcnow())
    if parsed is None:                                   # no route found → the buttons (never a dead end)
        await show(msg, t("bot.order.not_understood"), kb([btn(f"🚕 {t('bot.btn.order')}", "ord:new", style="primary")]))
        return
    o = {"source": RequestSource.TEXT, "from_text": parsed.from_text, "to_text": parsed.to_text,
         "from_id": parsed.from_place.id if parsed.from_place else None,
         "to_id": parsed.to_place.id if parsed.to_place else None, "seats": parsed.seats,
         "depart": parsed.depart_at.isoformat() if parsed.depart_at else None}
    if parsed.from_place:
        o["from_text"] = parsed.from_place.name
    if parsed.to_place:
        o["to_text"] = parsed.to_place.name
    await _offer_parsed(msg, state, session, user, t, o)


async def start_from_guest(msg: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings, t,
                           payload: str) -> bool:
    """`?start=g_<from>_<to>_<seats>_<depart minutes>` from a Guest Mode answer. False → not usable (plain greeting)."""
    parts = payload.split("_")
    if len(parts) != 5:
        return False
    from_id, to_id, seats, minutes = (int_arg(p) for p in parts[1:])
    if from_id is None or to_id is None or seats is None or minutes is None:
        return False
    a, b = (await session.get(Place, from_id), await session.get(Place, to_id))
    if a is None or b is None or a.id == b.id or not 1 <= seats <= 8:
        return False
    try:
        depart = local_to_utc(datetime.fromtimestamp(minutes * 60, tz=UZT)) if minutes else None
    except (OverflowError, OSError, ValueError):
        return False
    if depart and depart < utcnow() - timedelta(minutes=10):
        depart = None                                    # a stale link must not create a request in the past
    o = {"source": RequestSource.GUEST, "from_id": a.id, "from_text": a.name_uz, "to_id": b.id, "to_text": b.name_uz,
         "seats": seats, "depart": depart.isoformat() if depart else None}
    await _offer_parsed(msg, state, session, user, t, o)
    return True


@fallback.callback_query()
async def stale_button(cb: CallbackQuery, bot: Bot, settings: Settings, t) -> None:
    """Last resort: a button nobody handles (old message, finished flow) — never leave the spinner hanging.
    In a group, with `TULPORGO_EPHEMERAL_GROUP` on, only the one who pressed it is told (ephemerally, with a way to the
    private chat); if that cannot be delivered the usual alert is shown."""
    msg = cb.message
    if msg is not None and ephemeral.is_group(msg.chat.type) and get_extra().ephemeral_group:
        markup = kb([btn(f"🚕 {t('bot.group.btn')}", url=deep_link(settings, "order"), style="primary")])
        if await ephemeral.reply(bot, msg.chat.id, cb.from_user.id, t("bot.stale"), markup, callback_query_id=cb.id):
            await cb.answer()
            return
    await cb.answer(t("bot.stale"), show_alert=True)
