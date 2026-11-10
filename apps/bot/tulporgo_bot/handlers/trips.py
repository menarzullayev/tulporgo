"""The trip itself: start / complete / cancel, ratings, complaints (decision 13). Cards are sent by notify.py on the
`OfferAccepted` / `TripCompleted` events; the buttons land here."""
from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import RequestStatus
from tulporgo_core.errors import Forbidden, NotFound
from tulporgo_core.models import Driver, Trip, User
from tulporgo_core.services import feedback, rides

from .. import delivery
from . import states
from .cards import trip_keyboard
from .common import PRIVATE, btn, esc, int_arg, kb, parse_cb, person, show, user_t
from .recipients import admin_targets

router = Router(name="trips")
router.message.filter(F.chat.type == PRIVATE)


async def get_trip(session: AsyncSession, trip_id: int) -> Trip:
    trip = await session.get(Trip, trip_id)
    if trip is None:
        raise NotFound("trip_not_found")
    return trip


async def parties(session: AsyncSession, trip: Trip) -> tuple[Driver, User]:
    return await session.get(Driver, trip.driver_id), await session.get(User, trip.passenger_id)


def _id(cb: CallbackQuery, n: int = 2) -> int | None:
    parts = parse_cb(cb.data, n)
    return int_arg(parts[1]) if parts else None


@router.callback_query(F.data.startswith("ts:"))
async def start_trip(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, bot: Bot, t) -> None:
    tid = _id(cb)
    if tid is None:
        await cb.answer()
        return
    trip = await rides.start_trip(session, user, await get_trip(session, tid))
    await cb.answer(t("bot.trip.started_driver"))
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=trip_keyboard(trip, "driver", settings, t, started=True))
    _, passenger = await parties(session, trip)
    await delivery.send(bot, passenger.tg_id, f"▶ {user_t(passenger)('bot.trip.started_passenger')}")


@router.callback_query(F.data.startswith("tc:"))
async def complete_trip(cb: CallbackQuery, session: AsyncSession, user: User, bus, t) -> None:
    tid = _id(cb)
    if tid is None:
        await cb.answer()
        return
    await rides.complete_trip(session, user, await get_trip(session, tid), bus)    # TripCompleted → rating prompts
    await cb.answer(t("bot.trip.completed"))
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("tx:"))
async def cancel_ask(cb: CallbackQuery, session: AsyncSession, user: User, t) -> None:
    tid = _id(cb)
    if tid is None:
        await cb.answer()
        return
    trip = await get_trip(session, tid)
    driver, _ = await parties(session, trip)
    if user.id not in (trip.passenger_id, driver.user_id):
        raise Forbidden("not_your_trip")
    await cb.answer()
    if isinstance(cb.message, Message):
        await cb.message.answer(t("bot.trip.cancel_ask"), reply_markup=kb(
            [btn(f"✖ {t('bot.btn.cancel_yes')}", f"ty:{trip.id}", style="danger"), btn(t("common.no"), f"tn:{trip.id}")]))


@router.callback_query(F.data.startswith("tn:"))
async def cancel_no(cb: CallbackQuery) -> None:
    await cb.answer()
    if isinstance(cb.message, Message):
        await cb.message.delete()


@router.callback_query(F.data.startswith("ty:"))
async def cancel_yes(cb: CallbackQuery, session: AsyncSession, user: User, bus, bot: Bot, t) -> None:
    tid = _id(cb)
    if tid is None:
        await cb.answer()
        return
    trip = await rides.cancel_trip(session, user, await get_trip(session, tid), bus)
    await cb.answer()
    await show(cb, t("bot.trip.cancelled"))
    driver, passenger = await parties(session, trip)
    r = await rides.get_request(session, trip.request_id)
    if user.id == passenger.id:
        other, text = driver.user, "bot.trip.cancelled_by_passenger"
    else:
        other, text = passenger, ("bot.trip.cancelled_by_driver_reopened" if r.status == RequestStatus.OPEN
                                  else "bot.trip.cancelled_by_driver")
    await delivery.send(bot, other.tg_id, f"✖ {user_t(other)(text)}\n📍 {r.from_text} → {r.to_text}")


# ---------- rating (1–5) ----------

@router.callback_query(F.data.startswith("rt:"))
async def rate(cb: CallbackQuery, session: AsyncSession, user: User, t) -> None:
    parts = parse_cb(cb.data, 3)
    tid, stars = (int_arg(parts[1]), int_arg(parts[2])) if parts else (None, None)
    if tid is None or stars is None:
        await cb.answer()
        return
    await feedback.rate(session, user, await get_trip(session, tid), stars)
    await cb.answer()
    await show(cb, t("bot.rate.thanks", stars=stars))


# ---------- complaints (/yordam → "Shikoyat", or from a rating prompt) ----------

@router.callback_query(F.data.startswith("cm:"))
async def complaint_start(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, t) -> None:
    tid = _id(cb)
    if tid is None:
        await cb.answer()
        return
    if tid:
        trip = await get_trip(session, tid)
        driver, _ = await parties(session, trip)
        if user.id not in (trip.passenger_id, driver.user_id):
            raise Forbidden("not_your_trip")
    await cb.answer()
    await state.set_state(states.Complaint.text)
    await state.update_data(trip_id=tid)
    await show(cb, t("bot.complaint.ask"))


@router.message(StateFilter(states.Complaint.text), F.text, ~F.text.startswith("/"))
async def complaint_text(msg: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings,
                         bot: Bot, t) -> None:
    tid = (await state.get_data()).get("trip_id") or 0
    trip = await get_trip(session, tid) if tid else None
    against = None
    if trip:
        driver, passenger = await parties(session, trip)
        against = passenger if user.id == driver.user_id else driver.user
    c = await feedback.complain(session, user, msg.text or "", against, trip)     # too short → alert, state kept
    await state.clear()
    await show(msg, t("bot.complaint.thanks"))
    for admin_id, ta in await admin_targets(session, settings):
        head = ta("bot.admin.new_complaint", id=c.id, who=person(user))
        await delivery.send(bot, admin_id, f"📝 {head}\n\n{esc(c.text[:500])}")
