"""Shared helpers for the Mini App routes: deferred event publishing, time zone handling, response serializers.

Events are collected during the request and published only after the DB commit, so a bot process reacting to
`RequestCreated` never looks for a row that is not visible yet.
"""
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.events import Event
from tulporgo_core.models import Driver, Offer, Place, RideRequest, Trip, User
from tulporgo_core.services import billing

TASHKENT = timezone(timedelta(hours=5), "Asia/Tashkent")     # Uzbekistan has no daylight saving time


class Outbox:
    """Duck-types the `bus` argument of the core services; `flush` publishes after the commit."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)

    async def flush(self, bus) -> None:
        events, self.events = self.events, []
        for e in events:
            await bus.publish(e)


def get_outbox() -> Outbox:
    return Outbox()


async def commit_and_publish(s: AsyncSession, out: Outbox, bus) -> None:
    await s.commit()
    await out.flush(bus)


def to_utc_naive(dt: datetime | None) -> datetime | None:
    """Client time -> naive UTC (the DB convention). A time without an offset means Asia/Tashkent local time."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TASHKENT)
    return dt.astimezone(UTC).replace(tzinfo=None)


def to_local_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC).astimezone(TASHKENT).isoformat(timespec="minutes")


def iso(dt: datetime | None) -> str | None:
    return dt.replace(tzinfo=UTC).isoformat(timespec="seconds") if dt else None


def share_url(settings: Settings, token: str) -> str:
    return f"{settings.miniapp_url.rstrip('/')}/#/share/{token}"


def referral_link(settings: Settings, user: User) -> str | None:
    return f"https://t.me/{settings.bot_username}?start=ref_{user.referral_code}" if user.referral_code else None


def driver_card(d: Driver, settings: Settings) -> dict:
    plan = billing.effective_plan(d, settings)
    return {
        "id": d.id, "status": d.status, "verified": d.verified, "car_make": d.car_make, "car_color": d.car_color,
        "car_plate": d.car_plate, "seats": d.seats, "has_photo": bool(d.car_photo_file_id),
        "has_documents": bool(d.license_file_id and d.techpass_file_id),
        "rating": d.rating, "rating_count": d.rating_count, "ambassador": d.ambassador,
        "plan": d.plan, "subscription_until": iso(d.subscription_until),
        "subscription_active": billing.subscription_active(d, settings),
        "effective_plan": plan.plan.value if plan else None,
    }


def place_view(p: Place, parent_name: str | None = None) -> dict:
    return {"id": p.id, "name": p.name_uz, "name_ru": p.name_ru, "kind": p.kind, "parent": parent_name,
            "lat": p.lat, "lon": p.lon}


def request_view(r: RideRequest, offers_count: int = 0) -> dict:
    return {
        "id": r.id, "status": r.status, "from_text": r.from_text, "to_text": r.to_text,
        "from_place_id": r.from_place_id, "to_place_id": r.to_place_id, "depart_at": to_local_iso(r.depart_at),
        "seats": r.seats, "women_only": r.women_only, "note": r.note, "price_hint": r.price_hint,
        "created_at": iso(r.created_at), "expires_at": iso(r.expires_at), "offers_count": offers_count,
    }


def offer_view(o: Offer) -> dict:
    """What a passenger sees about an offer: price, car, rating (decision 6). No phone, no plate, no username."""
    d = o.driver
    return {
        "id": o.id, "request_id": o.request_id, "status": o.status, "price": o.price, "counter_price": o.counter_price,
        "message": o.message, "created_at": iso(o.created_at),
        "driver": {"first_name": d.user.first_name, "car_make": d.car_make, "car_color": d.car_color,
                   "rating": d.rating, "rating_count": d.rating_count, "verified": d.verified},
    }


def trip_view(t: Trip, r: RideRequest, driver: Driver, passenger: User, viewer: User, settings: Settings) -> dict:
    """A trip as seen by one of its two participants; contact details go to the counterparty only."""
    is_driver = driver.user_id == viewer.id
    other = passenger if is_driver else driver.user
    return {
        "id": t.id, "request_id": t.request_id, "status": t.status, "price": t.price,
        "role": "driver" if is_driver else "passenger",
        "from_text": r.from_text, "to_text": r.to_text, "depart_at": to_local_iso(r.depart_at), "seats": r.seats,
        "women_only": r.women_only, "created_at": iso(t.created_at), "completed_at": iso(t.completed_at),
        "share_token": t.share_token, "share_url": share_url(settings, t.share_token),
        "car": {"make": driver.car_make, "color": driver.car_color, "plate": driver.car_plate},
        "driver_verified": driver.verified, "driver_rating": driver.rating,
        "counterparty": {"first_name": other.first_name, "username": other.username, "phone": other.phone},
    }
