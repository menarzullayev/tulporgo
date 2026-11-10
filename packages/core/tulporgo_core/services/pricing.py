"""Price hint for a route (decision 7: "bot yo'nalish bo'yicha o'rtacha narxni maslahat qiladi")."""
import statistics
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import utcnow
from ..enums import TripStatus
from ..models import RideRequest, Trip

MIN_SAMPLES = 3
WINDOW_DAYS = 60


async def price_hint(s: AsyncSession, from_place_id: int | None, to_place_id: int | None) -> int | None:
    """Median price of matched trips on the same route (either direction) in the last 60 days, rounded to 1 000 so'm.
    None until there are at least 3 trips — no invented numbers."""
    if not from_place_id or not to_place_id:
        return None
    since = utcnow() - timedelta(days=WINDOW_DAYS)
    rows = (await s.execute(
        select(Trip.price).join(RideRequest, RideRequest.id == Trip.request_id)
        .where(Trip.created_at >= since, Trip.status != TripStatus.CANCELLED,
               or_((RideRequest.from_place_id == from_place_id) & (RideRequest.to_place_id == to_place_id),
                   (RideRequest.from_place_id == to_place_id) & (RideRequest.to_place_id == from_place_id)))
    )).scalars().all()
    if len(rows) < MIN_SAMPLES:
        return None
    return int(round(statistics.median(rows) / 1000) * 1000)
