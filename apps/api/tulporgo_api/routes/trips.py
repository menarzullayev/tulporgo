"""Trips: list, start/complete/cancel, rating (decisions 6, 13)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.errors import NotFound
from tulporgo_core.models import Driver, Rating, Trip, User
from tulporgo_core.services import feedback, rides

from ..deps import current_user, get_bus, get_session, get_settings
from .common import Outbox, commit_and_publish, get_outbox, trip_view

router = APIRouter(prefix="/trips", tags=["trips"])


class RateIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=512)


async def trip_payload(s: AsyncSession, t: Trip, viewer: User, settings: Settings) -> dict:
    r = await rides.get_request(s, t.request_id)
    driver = await s.get(Driver, t.driver_id)
    passenger = await s.get(User, t.passenger_id)
    if driver is None or passenger is None:                     # NOT NULL foreign keys: only corrupt data gets here
        raise NotFound("trip_not_found")
    rated = (await s.execute(select(Rating.id).where(Rating.trip_id == t.id,
                                                     Rating.from_user_id == viewer.id))).first() is not None
    return {**trip_view(t, r, driver, passenger, viewer, settings), "rated": rated}


async def _trip(s: AsyncSession, trip_id: int) -> Trip:
    t = await s.get(Trip, trip_id)
    if t is None:
        raise NotFound("trip_not_found")
    return t


@router.get("/mine")
async def my_trips(user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                   settings: Settings = Depends(get_settings)):
    d = (await s.execute(select(Driver.id).where(Driver.user_id == user.id))).scalar_one_or_none()
    cond = Trip.passenger_id == user.id if d is None else or_(Trip.passenger_id == user.id, Trip.driver_id == d)
    rows = (await s.execute(select(Trip).where(cond).order_by(Trip.id.desc()).limit(30))).scalars().all()
    return {"items": [await trip_payload(s, t, user, settings) for t in rows]}


@router.get("/{trip_id}")
async def get_trip(trip_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                   settings: Settings = Depends(get_settings)):
    t = await _trip(s, trip_id)
    await rides._trip_actor(s, t, user)                    # participants only (403 not_your_trip)
    return await trip_payload(s, t, user, settings)


@router.post("/{trip_id}/start")
async def start_trip(trip_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                     settings: Settings = Depends(get_settings)):
    t = await rides.start_trip(s, user, await _trip(s, trip_id))
    return await trip_payload(s, t, user, settings)


@router.post("/{trip_id}/complete")
async def complete_trip(trip_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                        settings: Settings = Depends(get_settings), bus=Depends(get_bus),
                        out: Outbox = Depends(get_outbox)):
    t = await rides.complete_trip(s, user, await _trip(s, trip_id), out)
    await commit_and_publish(s, out, bus)
    return await trip_payload(s, t, user, settings)


@router.post("/{trip_id}/cancel")
async def cancel_trip(trip_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                      settings: Settings = Depends(get_settings), bus=Depends(get_bus),
                      out: Outbox = Depends(get_outbox)):
    t = await rides.cancel_trip(s, user, await _trip(s, trip_id), out)
    await commit_and_publish(s, out, bus)
    return await trip_payload(s, t, user, settings)


@router.post("/{trip_id}/rate")
async def rate_trip(trip_id: int, body: RateIn, user: User = Depends(current_user),
                    s: AsyncSession = Depends(get_session)):
    r = await feedback.rate(s, user, await _trip(s, trip_id), body.stars, body.comment)
    return {"ok": True, "stars": r.stars}
