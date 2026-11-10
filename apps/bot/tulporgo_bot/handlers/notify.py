"""Event subscribers: turn domain events (published by this bot, the Mini App API or jobs) into Telegram messages.

Events are delivered after the publisher's transaction committed (see context.DeferredBus), so every handler here
opens its own session and sees the rows. Handlers must be idempotent: a repeated event may at worst resend a card."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.methods import SetChatMemberTag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tulporgo_core import i18n
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope
from tulporgo_core.enums import OfferStatus, RequestStatus, TripStatus
from tulporgo_core.events import (
    DriverVerified,
    OfferAccepted,
    OfferCountered,
    OfferCreated,
    ReferralGranted,
    RequestCreated,
    TripCompleted,
)
from tulporgo_core.models import Driver, Offer, RideRequest, Trip, User
from tulporgo_core.services import rides

from .. import delivery
from ..config import BotExtra
from .cards import (
    counter_keyboard,
    offer_card,
    offer_keyboard,
    rating_keyboard,
    request_card,
    request_keyboard,
    trip_html,
    trip_keyboard,
    trip_rich,
)
from .common import esc, get_required, person, price, user_t

log = logging.getLogger(__name__)
TERMINAL_OFFER = (OfferStatus.DECLINED, OfferStatus.WITHDRAWN, OfferStatus.EXPIRED, OfferStatus.ACCEPTED)


async def send_trip_card(bot: Bot, settings: Settings, trip: Trip, r: RideRequest, d: Driver, passenger: User,
                         role: str) -> None:
    """Trip card for one side: Rich Message with a table when the Bot API supports it, HTML otherwise."""
    user = d.user if role == "driver" else passenger
    t = user_t(user)
    markup = trip_keyboard(trip, role, settings, t, driver_user=d.user, started=trip.status == TripStatus.STARTED)
    await delivery.send_rich(bot, user.tg_id, trip_rich(trip, r, d, passenger, role == "driver", t),
                             trip_html(trip, r, d, passenger, role == "driver", t), markup)


class Notifier:
    def __init__(self, bot: Bot, maker: async_sessionmaker[AsyncSession], settings: Settings, extra: BotExtra) -> None:
        self.bot, self.maker, self.settings, self.extra = bot, maker, settings, extra
        self.tags = TagSync(bot, maker, extra)

    def subscribe(self, bus) -> None:
        for ev, fn in ((RequestCreated, self.on_request_created), (OfferCreated, self.on_offer_created),
                       (OfferCountered, self.on_offer_countered), (OfferAccepted, self.on_offer_accepted),
                       (TripCompleted, self.on_trip_completed), (DriverVerified, self.on_driver_verified),
                       (ReferralGranted, self.on_referral_granted)):
            bus.subscribe(ev, fn)

    # ----- passenger request → matching drivers -----
    async def on_request_created(self, ev: RequestCreated) -> None:
        async with session_scope(self.maker) as s:
            r = await rides.get_request(s, ev.request_id)
            if r.status != RequestStatus.OPEN:
                return
            closed = set((await s.execute(select(Offer.driver_id).where(
                Offer.request_id == r.id, Offer.status.in_(TERMINAL_OFFER)))).scalars())
            targets = [(d.user.tg_id, user_t(d.user)) for d in await rides.matching_drivers(s, r, self.settings)
                       if d.id not in closed]
            cards = [(tg, request_card(r, t), request_keyboard(r, t)) for tg, t in targets]
        for tg_id, text, markup in cards:                       # rate-limited inside delivery (≈30 msg/s, 429 retry)
            await delivery.send(self.bot, tg_id, text, markup)

    # ----- driver offer → passenger -----
    async def on_offer_created(self, ev: OfferCreated) -> None:
        async with session_scope(self.maker) as s:
            o = await s.get(Offer, ev.offer_id)
            r = await s.get(RideRequest, ev.request_id)
            if o is None or r is None or o.status != OfferStatus.SENT or r.status != RequestStatus.OPEN:
                return                                          # stale event: nothing to show
            d = await get_required(s, Driver, o.driver_id)
            passenger = await get_required(s, User, r.passenger_id)
            t = user_t(passenger)
            text, markup, tg_id = offer_card(o, d, r, t), offer_keyboard(o, t), passenger.tg_id
        await delivery.send(self.bot, tg_id, text, markup)

    # ----- passenger counter → driver -----
    async def on_offer_countered(self, ev: OfferCountered) -> None:
        async with session_scope(self.maker) as s:
            o = await s.get(Offer, ev.offer_id)
            if o is None or o.status != OfferStatus.COUNTERED:
                return
            if o.counter_price is None:                         # COUNTERED always carries the passenger's price
                return
            r = await get_required(s, RideRequest, o.request_id)
            d = await get_required(s, Driver, o.driver_id)
            t = user_t(d.user)
            text = (f"💬 <b>{t('bot.counter.title')}</b>\n📍 {esc(r.from_text)} → {esc(r.to_text)}\n"
                    f"{t('bot.counter.yours', price=price(o.price, t))}\n"
                    f"<b>{t('bot.counter.theirs', price=price(o.counter_price, t))}</b>")
            markup, tg_id = counter_keyboard(o, t), d.user.tg_id
        await delivery.send(self.bot, tg_id, text, markup)

    # ----- accepted → trip cards, losers informed -----
    async def on_offer_accepted(self, ev: OfferAccepted) -> None:
        async with session_scope(self.maker) as s:
            trip = await s.get(Trip, ev.trip_id)
            if trip is None:
                return
            r = await get_required(s, RideRequest, trip.request_id)
            d = await get_required(s, Driver, trip.driver_id)
            passenger = await get_required(s, User, trip.passenger_id)
            losers = list((await s.execute(select(Offer).where(
                Offer.request_id == r.id, Offer.id != ev.offer_id, Offer.status == OfferStatus.DECLINED,
                Offer.updated_at >= trip.created_at.replace(microsecond=0)))).scalars())
            lose_msgs = []
            for lo in losers:
                ld = await get_required(s, Driver, lo.driver_id)
                lose_msgs.append((ld.user.tg_id, user_t(ld.user)("bot.offer.lost", route=f"{r.from_text} → {r.to_text}")))
        await send_trip_card(self.bot, self.settings, trip, r, d, passenger, "passenger")
        await send_trip_card(self.bot, self.settings, trip, r, d, passenger, "driver")
        for tg_id, text in lose_msgs:
            await delivery.send(self.bot, tg_id, f"ℹ {esc(text)}")

    # ----- completed → ask both for a 1–5 rating -----
    async def on_trip_completed(self, ev: TripCompleted) -> None:
        async with session_scope(self.maker) as s:
            trip = await s.get(Trip, ev.trip_id)
            if trip is None or trip.status != TripStatus.COMPLETED:
                return
            d = await get_required(s, Driver, trip.driver_id)
            passenger = await get_required(s, User, trip.passenger_id)
            msgs = []
            for u, other, key in ((passenger, d.user, "bot.rate.ask_driver"), (d.user, passenger, "bot.rate.ask_passenger")):
                t = user_t(u)
                msgs.append((u.tg_id, f"🏁 {t(key, who=person(other))}", rating_keyboard(trip, t)))
        for tg_id, text, markup in msgs:
            await delivery.send(self.bot, tg_id, text, markup)

    # ----- verification / referral → thank the people, refresh member tags -----
    async def on_driver_verified(self, ev: DriverVerified) -> None:
        async with session_scope(self.maker) as s:
            d = await s.get(Driver, ev.driver_id)
            if d is None:
                return
            tg_id, t = d.user.tg_id, user_t(d.user)
        await delivery.send(self.bot, tg_id, f"✅ <b>{t('bot.verified')}</b>\n{t('bot.drv.verified_msg')}")
        await self.tags.sync()

    async def on_referral_granted(self, ev: ReferralGranted) -> None:
        async with session_scope(self.maker) as s:
            people = [await s.get(User, ev.referrer_id), await s.get(User, ev.referred_id)]
            msgs = [(u.tg_id, user_t(u)("bot.ref.granted", days=ev.days)) for u in people if u is not None]
        for tg_id, text in msgs:
            await delivery.send(self.bot, tg_id, f"🎉 {text}")
        await self.tags.sync()


class TagSync:
    """Member tags in the closed drivers group (Bot API 9.5 `setChatMemberTag`): "Elchi" for ambassadors,
    "Tasdiqlangan" for verified drivers. One tag per member (Telegram limits the length), applied once per change."""

    def __init__(self, bot: Bot, maker: async_sessionmaker[AsyncSession], extra: BotExtra) -> None:
        self.bot, self.maker, self.extra = bot, maker, extra
        self.applied: dict[int, str] = {}
        self.available = True

    @staticmethod
    def tag_for(d: Driver) -> str | None:
        if d.ambassador:
            return i18n.t("bot.tag.ambassador", "uz_new")
        if d.verified:
            return i18n.t("bot.tag.verified", "uz_new")
        return None

    async def sync(self) -> int:
        if not self.extra.drivers_group_id or not self.available:
            return 0
        async with session_scope(self.maker) as s:
            wanted = [(d.user.tg_id, self.tag_for(d)) for d in (await s.execute(select(Driver))).scalars()]
        done = 0
        for tg_id, tag in wanted:
            if tag is None or self.applied.get(tg_id) == tag:
                continue
            try:
                await delivery.call(self.bot, SetChatMemberTag(chat_id=self.extra.drivers_group_id, user_id=tg_id, tag=tag))
            except TelegramAPIError as e:
                if "not found" in str(e).lower() and "method" in str(e).lower():
                    self.available = False                      # an older Bot API server: stop trying
                    log.warning("setChatMemberTag is not available: %s", e)
                    return done
                log.info("tag for %s skipped: %s", tg_id, e)       # not a member of the group, etc.
                continue
            self.applied[tg_id] = tag
            done += 1
        return done
