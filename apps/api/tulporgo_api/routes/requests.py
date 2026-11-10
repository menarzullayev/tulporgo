"""Passenger side: ride requests and the offers they collect (decisions 6, 7, 47)."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import OfferStatus, RequestSource
from tulporgo_core.errors import Forbidden, NotFound
from tulporgo_core.models import Offer, Place, RideRequest, Trip, User
from tulporgo_core.services import rides

from ..deps import current_user, get_bus, get_session, get_settings
from .common import Outbox, commit_and_publish, get_outbox, offer_view, request_view, to_utc_naive
from .trips import trip_payload

router = APIRouter(tags=["requests"])
VISIBLE_OFFERS = (OfferStatus.SENT, OfferStatus.COUNTERED, OfferStatus.ACCEPTED)


class RequestIn(BaseModel):
    from_place_id: int | None = None
    to_place_id: int | None = None
    from_text: str | None = Field(default=None, max_length=128)
    to_text: str | None = Field(default=None, max_length=128)
    depart_at: datetime | None = None            # ISO; no offset means Asia/Tashkent local time. Null = as soon as possible
    seats: int = Field(default=1, ge=1, le=8)
    note: str | None = Field(default=None, max_length=256)


class CounterIn(BaseModel):
    price: int = Field(ge=1, le=10_000_000)      # the service enforces the real bounds (lower than the offer, >= 1 000)


async def _place_text(s: AsyncSession, place_id: int | None, text: str | None) -> str:
    if text and text.strip():
        return text.strip()
    if place_id is None:
        return ""
    p = await s.get(Place, place_id)
    if p is None:
        raise NotFound("place_not_found")
    return p.name_uz


async def _check_place(s: AsyncSession, place_id: int | None) -> None:
    if place_id is not None and await s.get(Place, place_id) is None:
        raise NotFound("place_not_found")


@router.post("/requests", status_code=201)
async def create_request(body: RequestIn, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                         settings: Settings = Depends(get_settings), bus=Depends(get_bus),
                         out: Outbox = Depends(get_outbox)):
    await _check_place(s, body.from_place_id)
    await _check_place(s, body.to_place_id)
    r = await rides.create_request(
        s, user, settings, from_text=await _place_text(s, body.from_place_id, body.from_text),
        to_text=await _place_text(s, body.to_place_id, body.to_text), from_place_id=body.from_place_id,
        to_place_id=body.to_place_id, depart_at=to_utc_naive(body.depart_at), seats=body.seats, note=body.note,
        source=RequestSource.MINIAPP, bus=out)
    await commit_and_publish(s, out, bus)             # the bot notifies drivers on RequestCreated
    return request_view(r)


@router.get("/requests/mine")
async def my_requests(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(select(RideRequest).where(RideRequest.passenger_id == user.id)
                            .order_by(RideRequest.id.desc()).limit(30))).scalars().all()
    counts = {}
    if rows:
        counts = dict((await s.execute(
            select(Offer.request_id, func.count()).where(Offer.request_id.in_([r.id for r in rows]),
                                                         Offer.status.in_(VISIBLE_OFFERS))
            .group_by(Offer.request_id))).all())
    return {"items": [request_view(r, counts.get(r.id, 0)) for r in rows]}


@router.post("/requests/{request_id}/cancel")
async def cancel_request(request_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                         bus=Depends(get_bus), out: Outbox = Depends(get_outbox)):
    r = await rides.get_request(s, request_id)
    await rides.cancel_request(s, user, r, out)
    await commit_and_publish(s, out, bus)
    return request_view(r)


@router.get("/requests/{request_id}/offers")
async def request_offers(request_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    r = await rides.get_request(s, request_id)
    if r.passenger_id != user.id:
        raise Forbidden("not_your_request")
    offers = (await s.execute(select(Offer).where(Offer.request_id == r.id, Offer.status.in_(VISIBLE_OFFERS))
                              .order_by(Offer.price, Offer.id))).scalars().all()
    trip_id = (await s.execute(select(Trip.id).where(Trip.request_id == r.id)
                               .order_by(Trip.id.desc()))).scalars().first()
    return {"request": request_view(r, len(offers)), "offers": [offer_view(o) for o in offers], "trip_id": trip_id}


async def _offer(s: AsyncSession, offer_id: int) -> Offer:
    o = await s.get(Offer, offer_id)
    if o is None:
        raise NotFound("offer_not_found")
    return o


@router.post("/offers/{offer_id}/accept")
async def accept_offer(offer_id: int, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                       settings: Settings = Depends(get_settings), bus=Depends(get_bus),
                       out: Outbox = Depends(get_outbox)):
    o = await _offer(s, offer_id)
    t = await rides.accept_offer(s, user, o, out)
    await commit_and_publish(s, out, bus)
    return await trip_payload(s, t, user, settings)


@router.post("/offers/{offer_id}/counter")
async def counter_offer(offer_id: int, body: CounterIn, user: User = Depends(current_user),
                        s: AsyncSession = Depends(get_session), bus=Depends(get_bus), out: Outbox = Depends(get_outbox)):
    o = await _offer(s, offer_id)
    await rides.counter_offer(s, user, o, body.price, out)
    await commit_and_publish(s, out, bus)
    return offer_view(o)
