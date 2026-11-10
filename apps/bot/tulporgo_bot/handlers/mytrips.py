"""/qatnovlarim — passenger: open requests (cancel) and trips; driver: my offers (withdraw) and my trips."""
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import OfferStatus, RequestStatus, TripStatus
from tulporgo_core.errors import Forbidden
from tulporgo_core.models import Offer, RideRequest, Trip, User
from tulporgo_core.services import drivers, rides

from . import notify
from .common import PRIVATE, btn, esc, int_arg, kb, parse_cb, price, show, time_plain
from .trips import get_trip, parties

router = Router(name="mytrips")
router.message.filter(F.chat.type == PRIVATE)
LIMIT = 5
ACTIVE_TRIP = (TripStatus.CONFIRMED, TripStatus.STARTED)


def _trip_line(trip: Trip, r: RideRequest, t) -> str:
    return f"• {esc(r.from_text)} → {esc(r.to_text)} · {price(trip.price, t)} · {t('bot.status.' + trip.status)}"


@router.message(Command("qatnovlarim"))
async def my_trips(msg: Message, state: FSMContext, session: AsyncSession, user: User, t) -> None:
    await state.clear()
    lines, rows = [f"<b>{t('bot.my.title')}</b>"], []

    reqs = list((await session.execute(select(RideRequest).where(
        RideRequest.passenger_id == user.id, RideRequest.status == RequestStatus.OPEN)
        .order_by(RideRequest.id.desc()).limit(LIMIT))).scalars())
    if reqs:
        lines.append(f"\n<b>{t('bot.my.open_requests')}</b>")
    for r in reqs:
        lines.append(f"• {esc(r.from_text)} → {esc(r.to_text)} · {time_plain(r.depart_at, t)}")
        rows.append([btn(f"✖ {t('bot.btn.cancel_request')}: {r.from_text} → {r.to_text}"[:60], f"rq:c:{r.id}", style="danger")])

    own = (await session.execute(select(Trip, RideRequest).join(RideRequest, RideRequest.id == Trip.request_id)
                                 .where(Trip.passenger_id == user.id).order_by(Trip.id.desc()).limit(LIMIT))).all()
    if own:
        lines.append(f"\n<b>{t('bot.my.trips')}</b>")
    for trip, r in own:
        lines.append(_trip_line(trip, r, t))
        if trip.status in ACTIVE_TRIP:
            rows.append([btn(f"🚕 {r.from_text} → {r.to_text}"[:60], f"mt:{trip.id}")])

    d = await drivers.get_driver(session, user)
    if d is not None:
        offers = (await session.execute(select(Offer, RideRequest).join(RideRequest, RideRequest.id == Offer.request_id)
                                        .where(Offer.driver_id == d.id,
                                               Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]))
                                        .order_by(Offer.id.desc()).limit(LIMIT))).all()
        if offers:
            lines.append(f"\n<b>{t('bot.my.offers')}</b>")
        for o, r in offers:
            lines.append(f"• {esc(r.from_text)} → {esc(r.to_text)} · {price(o.price, t)} · {t('bot.status.' + o.status)}")
            rows.append([btn(f"↩ {t('bot.btn.withdraw')}: {price(o.price, t)}"[:60], f"ow:{o.id}")])
        drv = (await session.execute(select(Trip, RideRequest).join(RideRequest, RideRequest.id == Trip.request_id)
                                     .where(Trip.driver_id == d.id).order_by(Trip.id.desc()).limit(LIMIT))).all()
        if drv:
            lines.append(f"\n<b>{t('bot.my.drive_trips')}</b>")
        for trip, r in drv:
            lines.append(_trip_line(trip, r, t))
            if trip.status in ACTIVE_TRIP:
                rows.append([btn(f"🚕 {r.from_text} → {r.to_text}"[:60], f"mt:{trip.id}")])

    if len(lines) == 1:
        lines.append(t("bot.my.empty"))
    await show(msg, "\n".join(lines), kb(*rows))


@router.callback_query(F.data.startswith("rq:c:"))
async def cancel_request(cb: CallbackQuery, session: AsyncSession, user: User, bus, t) -> None:
    parts = parse_cb(cb.data, 3)
    rid = int_arg(parts[2]) if parts else None
    if rid is None:
        await cb.answer()
        return
    await rides.cancel_request(session, user, await rides.get_request(session, rid), bus)
    await cb.answer()
    await show(cb, t("bot.my.request_cancelled"))


@router.callback_query(F.data.startswith("mt:"))
async def open_trip(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, bot: Bot) -> None:
    """Re-send the card of a live trip (with its buttons) — the original may be far up in the chat."""
    parts = parse_cb(cb.data, 2)
    tid = int_arg(parts[1]) if parts else None
    if tid is None:
        await cb.answer()
        return
    trip = await get_trip(session, tid)
    d, passenger = await parties(session, trip)
    if user.id not in (trip.passenger_id, d.user_id):
        raise Forbidden("not_your_trip")
    await cb.answer()
    r = await rides.get_request(session, trip.request_id)
    await notify.send_trip_card(bot, settings, trip, r, d, passenger, "driver" if user.id == d.user_id else "passenger")

