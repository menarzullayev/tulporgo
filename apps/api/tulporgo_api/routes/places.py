"""Place search for the order form: GET /api/places?q=, /api/places/roots, /api/places/nearest, /{id}/children."""
import math
import time

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.errors import NotFound
from tulporgo_core.models import Place, User
from tulporgo_core.places import PlaceIndex

from ..deps import current_user, get_session
from .common import place_view

router = APIRouter(prefix="/places", tags=["places"])
INDEX_TTL = 600            # seconds; the index is rebuilt after this or when `invalidate_place_index` is called
NEAREST_MAX_KM = 50.0


def invalidate_place_index(app) -> None:
    app.state.place_index = None


async def get_index(request: Request, s: AsyncSession) -> PlaceIndex:
    st = request.app.state
    cached = getattr(st, "place_index", None)
    if cached is None or time.monotonic() - getattr(st, "place_index_at", 0) > INDEX_TTL:
        cached = await PlaceIndex.load(s)
        st.place_index, st.place_index_at = cached, time.monotonic()
    return cached


async def _views(s: AsyncSession, places: list[Place]) -> list[dict]:
    parent_ids = {p.parent_id for p in places if p.parent_id}
    names = {}
    if parent_ids:
        names = {p.id: p.name_uz for p in (await s.execute(select(Place).where(Place.id.in_(parent_ids)))).scalars()}
    return [place_view(p, names.get(p.parent_id)) for p in places]


@router.get("")
async def search(request: Request, q: str = Query(default="", max_length=64), _: User = Depends(current_user),
                 s: AsyncSession = Depends(get_session)):
    q = q.strip()
    if not q:                                                   # no query: the most used places first
        rows = (await s.execute(select(Place).where(Place.kind.in_(["city", "district", "poi"]))
                                .order_by(Place.popularity.desc(), Place.name_uz).limit(12))).scalars().all()
        return {"items": await _views(s, list(rows))}
    refs = (await get_index(request, s)).search(q, limit=10)
    by_id = {p.id: p for p in (await s.execute(select(Place).where(Place.id.in_([r.id for r in refs])))).scalars()}
    return {"items": await _views(s, [by_id[r.id] for r in refs if r.id in by_id])}


@router.get("/roots")
async def roots(_: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(select(Place).where(Place.parent_id.is_(None)).order_by(Place.name_uz))).scalars().all()
    return {"items": await _views(s, list(rows))}


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


@router.get("/nearest")
async def nearest(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
                  _: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    """Snap a map tap to the closest known place that has coordinates (no external geocoder)."""
    rows = (await s.execute(select(Place).where(Place.lat.is_not(None), Place.lon.is_not(None),
                                                Place.kind != "region"))).scalars().all()
    best = min(rows, key=lambda p: _km(lat, lon, p.lat, p.lon), default=None)
    if best is None or _km(lat, lon, best.lat, best.lon) > NEAREST_MAX_KM:
        raise NotFound("place_not_found")
    return {"item": (await _views(s, [best]))[0], "distance_km": round(_km(lat, lon, best.lat, best.lon), 2)}


@router.get("/{place_id}/children")
async def children(place_id: int, _: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    if await s.get(Place, place_id) is None:
        raise NotFound("place_not_found")
    rows = (await s.execute(select(Place).where(Place.parent_id == place_id)
                            .order_by(Place.popularity.desc(), Place.name_uz))).scalars().all()
    return {"items": await _views(s, list(rows))}
