"""Passenger request → driver offers → (counter) → accept → trip (decisions 6, 7, 13)."""
import secrets
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import utcnow
from ..enums import DriverStatus, OfferStatus, RequestSource, RequestStatus, TripStatus
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..events import OfferAccepted, OfferCountered, OfferCreated, RequestClosed, RequestCreated, TripCompleted
from ..models import Driver, Offer, RideRequest, Trip, User
from . import billing, pricing

MAX_OPEN_REQUESTS = 3
MAX_PRICE = 5_000_000


async def create_request(s: AsyncSession, passenger: User, settings: Settings, *, from_text: str, to_text: str,
                         from_place_id: int | None = None, to_place_id: int | None = None,
                         depart_at: datetime | None = None, seats: int = 1, note: str | None = None,
                         source: str = RequestSource.BUTTONS, bus=None) -> RideRequest:
    if passenger.is_blocked:
        raise Forbidden("blocked")
    if not (1 <= seats <= 8):
        raise Invalid("bad_seats")
    if not from_text.strip() or not to_text.strip():
        raise Invalid("route_required")
    if from_place_id and from_place_id == to_place_id:
        raise Invalid("same_place")
    now = utcnow()
    if depart_at and depart_at < now - timedelta(minutes=10):
        raise Invalid("depart_in_past")
    open_count = len((await s.execute(select(RideRequest.id).where(
        RideRequest.passenger_id == passenger.id, RideRequest.status == RequestStatus.OPEN))).all())
    if open_count >= MAX_OPEN_REQUESTS:
        raise Conflict("too_many_open_requests")
    r = RideRequest(passenger_id=passenger.id, from_text=from_text.strip()[:128], to_text=to_text.strip()[:128],
                    from_place_id=from_place_id, to_place_id=to_place_id, depart_at=depart_at, seats=seats,
                    women_only=passenger.is_woman, note=(note or "").strip()[:256] or None, source=source,
                    expires_at=max(now, depart_at or now) + timedelta(minutes=settings.request_ttl_minutes))
    r.price_hint = await pricing.price_hint(s, from_place_id, to_place_id)
    s.add(r)
    await s.flush()
    if bus:
        await bus.publish(RequestCreated(r.id))
    return r


async def get_request(s: AsyncSession, request_id: int) -> RideRequest:
    r = await s.get(RideRequest, request_id)
    if r is None:
        raise NotFound("request_not_found")
    return r


async def cancel_request(s: AsyncSession, passenger: User, r: RideRequest, bus=None) -> RideRequest:
    if r.passenger_id != passenger.id:
        raise Forbidden("not_your_request")
    if r.status != RequestStatus.OPEN:
        raise Conflict("request_not_open")
    r.status = RequestStatus.CANCELLED
    await _close_offers(s, r.id)
    if bus:
        await bus.publish(RequestClosed(r.id, r.status))
    return r


async def expire_requests(s: AsyncSession, now: datetime | None = None, bus=None) -> list[int]:
    now = now or utcnow()
    ids = [i for (i,) in (await s.execute(select(RideRequest.id).where(
        RideRequest.status == RequestStatus.OPEN, RideRequest.expires_at < now))).all()]
    if ids:
        await s.execute(update(RideRequest).where(RideRequest.id.in_(ids)).values(status=RequestStatus.EXPIRED))
        await s.execute(update(Offer).where(Offer.request_id.in_(ids),
                                            Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]))
                        .values(status=OfferStatus.EXPIRED))
        if bus:
            for i in ids:
                await bus.publish(RequestClosed(i, RequestStatus.EXPIRED))
    return ids


async def matching_drivers(s: AsyncSession, r: RideRequest, settings: Settings, limit: int = 200) -> list[Driver]:
    """Active, subscribed, unblocked drivers with enough seats; home-area drivers first, then by rating."""
    rows = (await s.execute(
        select(Driver).join(User, User.id == Driver.user_id)
        .where(Driver.status == DriverStatus.ACTIVE, User.is_blocked.is_(False), Driver.seats >= r.seats,
               Driver.user_id != r.passenger_id)
    )).scalars().all()
    now = utcnow()
    rows = [d for d in rows if billing.subscription_active(d, settings, now)]
    home = {r.from_place_id, r.to_place_id} - {None}
    rows.sort(key=lambda d: (d.home_place_id not in home, -(d.rating or 0), d.id))
    return rows[:limit]


async def send_offer(s: AsyncSession, driver: Driver, r: RideRequest, settings: Settings, price: int,
                     message: str | None = None, bus=None) -> Offer:
    if driver.status != DriverStatus.ACTIVE:
        raise Forbidden("driver_not_active")
    if not billing.subscription_active(driver, settings):
        raise Forbidden("subscription_required")
    if r.status != RequestStatus.OPEN:
        raise Conflict("request_not_open")
    if r.passenger_id == driver.user_id:
        raise Invalid("own_request")
    if not (1_000 <= price <= MAX_PRICE):
        raise Invalid("bad_price")
    if driver.seats < r.seats:
        raise Invalid("not_enough_seats")
    o = (await s.execute(select(Offer).where(Offer.request_id == r.id, Offer.driver_id == driver.id))).scalar_one_or_none()
    if o and o.status in (OfferStatus.ACCEPTED, OfferStatus.WITHDRAWN, OfferStatus.DECLINED, OfferStatus.EXPIRED):
        raise Conflict("offer_closed")
    if o is None:
        o = Offer(request_id=r.id, driver_id=driver.id, price=price)
        s.add(o)
    o.price, o.counter_price, o.status, o.message = price, None, OfferStatus.SENT, (message or "")[:256] or None
    await s.flush()
    if bus:
        await bus.publish(OfferCreated(o.id, r.id))
    return o


async def counter_offer(s: AsyncSession, passenger: User, o: Offer, counter_price: int, bus=None) -> Offer:
    r = await get_request(s, o.request_id)
    if r.passenger_id != passenger.id:
        raise Forbidden("not_your_request")
    if r.status != RequestStatus.OPEN or o.status != OfferStatus.SENT:
        raise Conflict("offer_not_open")
    if not (1_000 <= counter_price < o.price):
        raise Invalid("counter_must_be_lower")
    o.counter_price, o.status = counter_price, OfferStatus.COUNTERED
    if bus:
        await bus.publish(OfferCountered(o.id, counter_price))
    return o


async def respond_counter(s: AsyncSession, driver: Driver, o: Offer, accept: bool, bus=None) -> Offer | Trip:
    """Driver agrees to the passenger's price → trip at that price; or declines → offer back at the driver's price."""
    if o.driver_id != driver.id:
        raise Forbidden("not_your_offer")
    if o.status != OfferStatus.COUNTERED:
        raise Conflict("no_counter")
    if not accept:
        o.status, o.counter_price = OfferStatus.SENT, None
        return o
    return await _make_trip(s, o, o.counter_price, bus)


async def accept_offer(s: AsyncSession, passenger: User, o: Offer, bus=None) -> Trip:
    r = await get_request(s, o.request_id)
    if r.passenger_id != passenger.id:
        raise Forbidden("not_your_request")
    if o.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise Conflict("offer_not_open")
    return await _make_trip(s, o, o.price, bus)


async def _make_trip(s: AsyncSession, o: Offer, price: int, bus) -> Trip:
    r = await get_request(s, o.request_id)
    # atomic OPEN → MATCHED: of two concurrent acceptances only one updates the row (works on every backend)
    res = await s.execute(update(RideRequest).where(RideRequest.id == r.id, RideRequest.status == RequestStatus.OPEN)
                          .values(status=RequestStatus.MATCHED).execution_options(synchronize_session="fetch"))
    if res.rowcount != 1:
        raise Conflict("request_not_open")
    t = Trip(request_id=r.id, offer_id=o.id, driver_id=o.driver_id, passenger_id=r.passenger_id, price=price,
             share_token=secrets.token_urlsafe(12))
    o.status, o.price = OfferStatus.ACCEPTED, price
    s.add(t)
    try:
        await s.flush()                                    # unique(offer_id): one trip per offer
    except IntegrityError as e:
        raise Conflict("already_matched") from e
    await s.execute(update(Offer).where(Offer.request_id == r.id, Offer.id != o.id,
                                        Offer.status.in_([OfferStatus.SENT, OfferStatus.COUNTERED]))
                    .values(status=OfferStatus.DECLINED))
    if bus:
        await bus.publish(OfferAccepted(o.id, t.id))
    return t


async def withdraw_offer(s: AsyncSession, driver: Driver, o: Offer) -> Offer:
    if o.driver_id != driver.id:
        raise Forbidden("not_your_offer")
    if o.status not in (OfferStatus.SENT, OfferStatus.COUNTERED):
        raise Conflict("offer_not_open")
    o.status = OfferStatus.WITHDRAWN
    return o


async def _trip_actor(s: AsyncSession, t: Trip, user: User) -> str:
    if t.passenger_id == user.id:
        return "passenger"
    d = await s.get(Driver, t.driver_id)
    if d and d.user_id == user.id:
        return "driver"
    raise Forbidden("not_your_trip")


async def start_trip(s: AsyncSession, user: User, t: Trip) -> Trip:
    if await _trip_actor(s, t, user) != "driver":
        raise Forbidden("driver_only")
    if t.status != TripStatus.CONFIRMED:
        raise Conflict("trip_not_confirmed")
    t.status, t.started_at = TripStatus.STARTED, utcnow()
    return t


async def complete_trip(s: AsyncSession, user: User, t: Trip, bus=None) -> Trip:
    await _trip_actor(s, t, user)
    if t.status not in (TripStatus.CONFIRMED, TripStatus.STARTED):
        raise Conflict("trip_not_active")
    t.status, t.completed_at = TripStatus.COMPLETED, utcnow()
    r = await get_request(s, t.request_id)
    r.status = RequestStatus.COMPLETED
    if bus:
        await bus.publish(TripCompleted(t.id))
    return t


async def cancel_trip(s: AsyncSession, user: User, t: Trip, bus=None) -> Trip:
    """Driver cancels before start → the request reopens for other drivers; passenger cancels → request closed."""
    actor = await _trip_actor(s, t, user)
    if t.status != TripStatus.CONFIRMED:
        raise Conflict("trip_not_cancellable")
    t.status, t.cancelled_by_id = TripStatus.CANCELLED, user.id
    r = await get_request(s, t.request_id)
    o = await s.get(Offer, t.offer_id)
    o.status = OfferStatus.WITHDRAWN
    if actor == "driver" and r.expires_at and r.expires_at > utcnow():
        r.status = RequestStatus.OPEN                      # other drivers can offer again; the cancelled trip stays
        if bus:                                            # as history (complaints, driver reliability)
            await bus.publish(RequestCreated(r.id))
    else:
        r.status = RequestStatus.CANCELLED
        await _close_offers(s, r.id)
        if bus:
            await bus.publish(RequestClosed(r.id, r.status))
    return t


async def trip_by_share_token(s: AsyncSession, token: str) -> Trip:
    t = (await s.execute(select(Trip).where(Trip.share_token == token))).scalar_one_or_none()
    if t is None:
        raise NotFound("trip_not_found")
    return t


async def _close_offers(s: AsyncSession, request_id: int) -> None:
    await s.execute(update(Offer).where(Offer.request_id == request_id,
                                        or_(Offer.status == OfferStatus.SENT, Offer.status == OfferStatus.COUNTERED))
                    .values(status=OfferStatus.DECLINED))
