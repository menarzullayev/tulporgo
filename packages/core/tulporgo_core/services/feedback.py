"""Ratings and complaints (decision 13)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import ComplaintStatus, TripStatus
from ..errors import Conflict, Forbidden, Invalid
from ..models import Complaint, Driver, Rating, Trip, User


async def rate(s: AsyncSession, user: User, t: Trip, stars: int, comment: str | None = None) -> Rating:
    if t.status != TripStatus.COMPLETED:
        raise Conflict("trip_not_completed")
    if not (1 <= stars <= 5):
        raise Invalid("bad_stars")
    driver = await s.get(Driver, t.driver_id)
    if user.id == t.passenger_id:
        to_user = driver.user_id
    elif driver.user_id == user.id:
        to_user = t.passenger_id
    else:
        raise Forbidden("not_your_trip")
    if (await s.execute(select(Rating.id).where(Rating.trip_id == t.id, Rating.from_user_id == user.id))).first():
        raise Conflict("already_rated")
    r = Rating(trip_id=t.id, from_user_id=user.id, to_user_id=to_user, stars=stars, comment=(comment or "")[:512] or None)
    s.add(r)
    if to_user == driver.user_id:
        driver.rating_sum += stars
        driver.rating_count += 1
    await s.flush()
    return r


async def complain(s: AsyncSession, user: User, text: str, against: User | None = None, trip: Trip | None = None) -> Complaint:
    if not text or len(text.strip()) < 5:
        raise Invalid("complaint_too_short")
    c = Complaint(from_user_id=user.id, against_user_id=against.id if against else None,
                  trip_id=trip.id if trip else None, text=text.strip()[:4000])
    s.add(c)
    await s.flush()
    return c


async def resolve(s: AsyncSession, admin: User, c: Complaint, accepted: bool, resolution: str) -> Complaint:
    if not admin.is_admin:
        raise Forbidden("admin_only")
    if c.status != ComplaintStatus.OPEN:
        raise Conflict("complaint_closed")
    c.status = ComplaintStatus.RESOLVED if accepted else ComplaintStatus.REJECTED
    c.resolved_by_id, c.resolution = admin.id, (resolution or "")[:512]
    return c

