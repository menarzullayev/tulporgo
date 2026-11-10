"""Offers: the driver types a price (decision 7), the passenger accepts / counters / declines, the driver answers the
counter. Business rules live in tulporgo_core.services.rides; every button here re-checks ownership through it."""
import re
from typing import cast

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import OfferStatus, RequestStatus
from tulporgo_core.errors import Conflict, Forbidden, NotFound
from tulporgo_core.models import Driver, Offer, RideRequest, User
from tulporgo_core.services import drivers, rides

from .. import delivery
from . import states
from .cards import offer_card, offer_keyboard, price_keyboard, request_card
from .common import PRIVATE, btn, get_required, int_arg, kb, parse_cb, price, show, user_t

router = Router(name="offers")
router.message.filter(F.chat.type == PRIVATE)
PRICE_RE = re.compile(r"^\s*(\d[\d\s.,]*)\s*(?:so'?m|сум|uzs)?\s*$", re.I)


async def get_offer(session: AsyncSession, offer_id: int) -> Offer:
    o = await session.get(Offer, offer_id)
    if o is None:
        raise NotFound("offer_not_found")
    return o


async def my_driver(session: AsyncSession, user: User) -> Driver:
    d = await drivers.get_driver(session, user)
    if d is None:
        raise Forbidden("not_driver")
    return d


async def decline_offer(session: AsyncSession, passenger: User, o: Offer) -> Offer:
    """Passenger turns an offer down. (The core has no such service: ownership and state are checked here.)"""
    r = await rides.get_request(session, o.request_id)
    if r.passenger_id != passenger.id:
        raise Forbidden("not_your_request")
    if r.status != RequestStatus.OPEN or o.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise Conflict("offer_not_open")
    o.status = OfferStatus.DECLINED
    return o


def parse_price(text: str) -> int | None:
    m = PRICE_RE.match(text or "")
    if not m:
        return None
    digits = re.sub(r"\D", "", m[1])
    return int(digits) if digits else None


# ---------- driver: make an offer ----------

@router.callback_query(F.data.startswith("ofp:"))
async def offer_prices(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, t) -> None:
    parts = parse_cb(cb.data, 2)
    rid = int_arg(parts[1]) if parts else None
    if rid is None:
        await cb.answer()
        return
    await my_driver(session, user)
    r = await rides.get_request(session, rid)
    if r.status != RequestStatus.OPEN:
        raise Conflict("request_not_open")
    await cb.answer()
    await show(cb, request_card(r, t) + "\n\n" + t("bot.offer.pick_price"), price_keyboard(r, t))


@router.callback_query(F.data.startswith("ofc:"))
async def offer_custom(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, t) -> None:
    parts = parse_cb(cb.data, 2)
    rid = int_arg(parts[1]) if parts else None
    if rid is None:
        await cb.answer()
        return
    await my_driver(session, user)
    await cb.answer()
    await state.set_state(states.Offer.price)
    await state.update_data(rid=rid)
    await show(cb, t("bot.offer.type_price"))


async def _make_offer(event, session: AsyncSession, user: User, settings: Settings, bus, t, rid: int, amount: int):
    d = await my_driver(session, user)
    r = await rides.get_request(session, rid)
    o = await rides.send_offer(session, d, r, settings, amount, bus=bus)
    await show(event, f"✅ {t('bot.offer.sent', price=price(o.price, t))}",
               kb([btn(f"↩ {t('bot.btn.withdraw')}", f"ow:{o.id}")]))


@router.callback_query(F.data.startswith("ofq:"))
async def offer_quick(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, bus, t) -> None:
    parts = parse_cb(cb.data, 3)
    rid, amount = (int_arg(parts[1]), int_arg(parts[2])) if parts else (None, None)
    if rid is None or amount is None:
        await cb.answer()
        return
    await _make_offer(cb, session, user, settings, bus, t, rid, amount)
    await cb.answer()


@router.message(StateFilter(states.Offer.price), F.text, ~F.text.startswith("/"))
async def offer_typed(msg: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings, bus,
                      t) -> None:
    amount = parse_price(msg.text or "")
    if amount is None:
        await show(msg, t("bot.err.bad_price"))
        return
    rid = (await state.get_data()).get("rid", 0)
    await _make_offer(msg, session, user, settings, bus, t, rid, amount)   # an invalid amount raises → alert, state kept
    await state.clear()


@router.callback_query(F.data.startswith("ow:"))
async def withdraw(cb: CallbackQuery, session: AsyncSession, user: User, t) -> None:
    parts = parse_cb(cb.data, 2)
    oid = int_arg(parts[1]) if parts else None
    if oid is None:
        await cb.answer()
        return
    o = await rides.withdraw_offer(session, await my_driver(session, user), await get_offer(session, oid))
    await cb.answer()
    await show(cb, t("bot.offer.withdrawn", price=price(o.price, t)))


# ---------- passenger: accept / counter / decline ----------

@router.callback_query(F.data.startswith("oa:"))
async def accept(cb: CallbackQuery, session: AsyncSession, user: User, bus, t) -> None:
    parts = parse_cb(cb.data, 2)
    oid = int_arg(parts[1]) if parts else None
    if oid is None:
        await cb.answer()
        return
    trip = await rides.accept_offer(session, user, await get_offer(session, oid), bus)
    await cb.answer()
    await show(cb, f"✅ {t('bot.offer.accepted', price=price(trip.price, t))}")       # trip cards: notify.on_offer_accepted


@router.callback_query(F.data.startswith("od:"))
async def decline(cb: CallbackQuery, session: AsyncSession, user: User, bot: Bot, t) -> None:
    parts = parse_cb(cb.data, 2)
    oid = int_arg(parts[1]) if parts else None
    if oid is None:
        await cb.answer()
        return
    o = await decline_offer(session, user, await get_offer(session, oid))
    await cb.answer()
    await show(cb, t("bot.offer.declined"))
    d = await get_required(session, Driver, o.driver_id)
    r = await rides.get_request(session, o.request_id)
    td = user_t(d.user)
    await delivery.send(bot, d.user.tg_id, f"✖ {td('bot.offer.declined_driver', route=f'{r.from_text} → {r.to_text}')}")


@router.callback_query(F.data.startswith("cn:"))
async def counter_prompt(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, t) -> None:
    parts = parse_cb(cb.data, 2)
    oid = int_arg(parts[1]) if parts else None
    if oid is None:
        await cb.answer()
        return
    o = await get_offer(session, oid)
    r = await rides.get_request(session, o.request_id)
    if r.passenger_id != user.id:
        raise Forbidden("not_your_request")
    if r.status != RequestStatus.OPEN or o.status != OfferStatus.SENT:
        raise Conflict("offer_not_open")
    await cb.answer()
    await state.set_state(states.Counter.price)
    await state.update_data(oid=oid)
    quick = [btn(price(p, t), f"cq:{o.id}:{p}") for p in (o.price - 10_000, o.price - 5_000) if p >= 1000]
    await show(cb, t("bot.counter.ask", price=price(o.price, t)), kb(quick))


async def _counter(event, session: AsyncSession, user: User, bus, t, oid: int, amount: int) -> None:
    o = await rides.counter_offer(session, user, await get_offer(session, oid), amount, bus)   # event → the driver
    # counter_offer() has just stored the passenger's price on the offer
    await show(event, t("bot.counter.sent", price=price(cast(int, o.counter_price), t)))


@router.callback_query(F.data.startswith("cq:"))
async def counter_quick(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, bus, bot: Bot, t) -> None:
    parts = parse_cb(cb.data, 3)
    oid, amount = (int_arg(parts[1]), int_arg(parts[2])) if parts else (None, None)
    if oid is None or amount is None:
        await cb.answer()
        return
    await _counter(cb, session, user, bus, t, oid, amount)
    await cb.answer()
    await state.clear()


@router.message(StateFilter(states.Counter.price), F.text, ~F.text.startswith("/"))
async def counter_typed(msg: Message, state: FSMContext, session: AsyncSession, user: User, bus, bot: Bot, t) -> None:
    amount = parse_price(msg.text or "")
    if amount is None:
        await show(msg, t("bot.err.bad_price"))
        return
    await _counter(msg, session, user, bus, t, (await state.get_data()).get("oid", 0), amount)
    await state.clear()


# ---------- driver: answer the passenger's counter ----------

@router.callback_query(F.data.startswith("ra:"))
async def counter_accept(cb: CallbackQuery, session: AsyncSession, user: User, bus, t) -> None:
    parts = parse_cb(cb.data, 2)
    oid = int_arg(parts[1]) if parts else None
    if oid is None:
        await cb.answer()
        return
    res = await rides.respond_counter(session, await my_driver(session, user), await get_offer(session, oid), True, bus)
    await cb.answer()
    await show(cb, f"✅ {t('bot.offer.accepted', price=price(res.price, t))}")


@router.callback_query(F.data.startswith("rd:"))
async def counter_decline(cb: CallbackQuery, session: AsyncSession, user: User, bot: Bot, t) -> None:
    """Driver keeps their price: the offer is open again and the passenger gets it back (no counter ping-pong text)."""
    parts = parse_cb(cb.data, 2)
    oid = int_arg(parts[1]) if parts else None
    if oid is None:
        await cb.answer()
        return
    d = await my_driver(session, user)
    o = await rides.respond_counter(session, d, await get_offer(session, oid), False)
    await cb.answer()
    await show(cb, t("bot.counter.kept", price=price(o.price, t)))
    r: RideRequest = await rides.get_request(session, o.request_id)
    passenger = await get_required(session, User, r.passenger_id)
    tp = user_t(passenger)
    await delivery.send(bot, passenger.tg_id, f"ℹ {tp('bot.counter.refused')}\n\n{offer_card(o, d, r, tp)}",
                        offer_keyboard(o, tp))
