"""Public trip status page data (decision 13: "share the trip with relatives"). NO authentication.

Whitelist only: route, departure time, trip status, car make/colour/plate and the driver's FIRST name. No phone
numbers, usernames, Telegram ids, passenger data or price. The token is the only secret (96 random bits).
"""
from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.enums import TripStatus
from tulporgo_core.models import Driver
from tulporgo_core.services import rides

from ..deps import get_session
from .common import to_local_iso

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{token}")
async def shared_trip(response: Response, token: str = Path(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
                      s: AsyncSession = Depends(get_session)):
    t = await rides.trip_by_share_token(s, token)
    r = await rides.get_request(s, t.request_id)
    d = await s.get(Driver, t.driver_id)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return {
        "status": t.status,
        "finished": t.status in (TripStatus.COMPLETED, TripStatus.CANCELLED),
        "from": r.from_text, "to": r.to_text, "depart_at": to_local_iso(r.depart_at),
        "driver_first_name": d.user.first_name,
        "car": {"make": d.car_make, "color": d.car_color, "plate": d.car_plate},
    }
