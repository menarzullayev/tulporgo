"""Mini App API for the group feed (decision 73), mounted under /api/userbot/feed by `tulporgo_userbot.api`.

    GET    /api/userbot/feed                    state: paused, delivery channel, consent, taxi groups, filters
    POST   /api/userbot/feed/filters            create a filter
    PUT    /api/userbot/feed/filters/{id}       replace a filter
    DELETE /api/userbot/feed/filters/{id}
    POST   /api/userbot/feed/pause   {paused}   pause / resume everything

Only the driver's own filters, only his selected taxi groups, only existing places. Errors: JSON {error, detail}.
"""
import re
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_api.deps import current_user, get_session
from tulporgo_core.enums import RequestKind
from tulporgo_core.models import Driver, DriverFilter, Place, User, UserbotGroup

from . import service
from .errors import Invalid, NotFound

router = APIRouter(prefix="/feed", tags=["userbot"])
MAX_FILTERS = 20
MAX_ROUTES = 10
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
Kind = Literal["passenger", "parcel", "cargo", "delivery", "bazaar"]


class RouteIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: int | None = Field(default=None, alias="from")
    to: int | None = None
    on_way: bool = False


class FilterIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    enabled: bool = True
    routes: list[RouteIn] = Field(default_factory=list, max_length=MAX_ROUTES)
    time_from: str | None = None
    time_to: str | None = None
    include_asap: bool = True
    include_tomorrow: bool = True
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    seats_min: int | None = Field(default=None, ge=1, le=8)
    seats_max: int | None = Field(default=None, ge=1, le=8)
    kinds: list[Kind] = Field(default_factory=list, max_length=5)
    group_chat_ids: list[int] = Field(default_factory=list, max_length=200)


class PauseIn(BaseModel):
    paused: bool


async def _driver(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)) -> Driver:
    return await service.require_driver(s, user)


async def _taxi_groups(s: AsyncSession, driver: Driver) -> list[UserbotGroup]:
    account = await service.get_account(s, driver)
    return [g for g in (account.groups if account else []) if g.enabled]


async def _validate(s: AsyncSession, driver: Driver, body: FilterIn) -> None:
    for v in (body.time_from, body.time_to):
        if v is not None and not HHMM.match(v):
            raise Invalid("bad_time")
    if any(d < 0 or d > 6 for d in body.weekdays):
        raise Invalid("bad_weekday")
    if body.seats_min and body.seats_max and body.seats_min > body.seats_max:
        raise Invalid("bad_seats")
    ids = {i for r in body.routes for i in (r.from_, r.to) if i is not None}
    if ids:
        found = set((await s.execute(select(Place.id).where(Place.id.in_(ids)))).scalars())
        if ids - found:
            raise Invalid("unknown_place")
    if any(r.from_ is None and r.to is None for r in body.routes):
        raise Invalid("empty_route")
    mine = {g.chat_id for g in await _taxi_groups(s, driver)}
    if set(body.group_chat_ids) - mine:
        raise Invalid("not_your_group")                       # never a group he did not select


def _apply(f: DriverFilter, body: FilterIn) -> None:
    f.name = body.name.strip()
    f.enabled = body.enabled
    f.routes = [{"from": r.from_, "to": r.to, "on_way": r.on_way} for r in body.routes]
    f.time_from, f.time_to = body.time_from, body.time_to
    f.include_asap, f.include_tomorrow = body.include_asap, body.include_tomorrow
    f.weekdays = sorted(set(body.weekdays))
    f.seats_min, f.seats_max = body.seats_min, body.seats_max
    f.kinds = sorted(set(body.kinds))
    f.group_chat_ids = sorted(set(body.group_chat_ids))


async def _out(s: AsyncSession, f: DriverFilter) -> dict:
    ids = {i for r in f.routes for i in (r.get("from"), r.get("to")) if i}
    names = dict((await s.execute(select(Place.id, Place.name_uz).where(Place.id.in_(ids)))).all()) if ids else {}

    def place(i):
        return {"id": i, "name": names.get(i, "?")} if i else None
    return {"id": f.id, "name": f.name, "enabled": f.enabled,
            "routes": [{"from": place(r.get("from")), "to": place(r.get("to")), "on_way": bool(r.get("on_way"))}
                       for r in f.routes],
            "time_from": f.time_from, "time_to": f.time_to, "include_asap": f.include_asap,
            "include_tomorrow": f.include_tomorrow, "weekdays": f.weekdays, "seats_min": f.seats_min,
            "seats_max": f.seats_max, "kinds": f.kinds, "group_chat_ids": f.group_chat_ids}


async def _state(s: AsyncSession, driver: Driver) -> dict:
    account = await service.get_account(s, driver)
    filters = (await s.execute(select(DriverFilter).where(DriverFilter.driver_id == driver.id)
                               .order_by(DriverFilter.id))).scalars().all()
    return {
        "paused": driver.feed_paused,
        "delivery_linked": driver.delivery_chat_id is not None,
        "connected": bool(account and account.session_encrypted),
        "consent_ok": bool(account and account.consent_at and account.consent_version >= service.CONSENT_VERSION),
        "groups": [{"chat_id": g.chat_id, "title": g.title} for g in await _taxi_groups(s, driver)],
        "filters": [await _out(s, f) for f in filters],
        "kinds": [k.value for k in RequestKind],
        "max_filters": MAX_FILTERS,
    }


async def _own(s: AsyncSession, driver: Driver, filter_id: int) -> DriverFilter:
    f = await s.get(DriverFilter, filter_id)
    if f is None or f.driver_id != driver.id:
        raise NotFound("filter_not_found")                   # someone else's filter looks like a missing one
    return f


@router.get("")
async def feed_state(driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session)):
    return await _state(s, driver)


@router.post("/filters")
async def filter_create(body: FilterIn, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session)):
    count = (await s.execute(select(func.count()).select_from(DriverFilter)
                             .where(DriverFilter.driver_id == driver.id))).scalar_one()
    if count >= MAX_FILTERS:
        raise Invalid("too_many_filters")
    await _validate(s, driver, body)
    f = DriverFilter(driver_id=driver.id)
    _apply(f, body)
    s.add(f)
    await s.flush()
    return await _out(s, f)


@router.put("/filters/{filter_id}")
async def filter_update(filter_id: int, body: FilterIn, driver: Driver = Depends(_driver),
                        s: AsyncSession = Depends(get_session)):
    f = await _own(s, driver, filter_id)
    await _validate(s, driver, body)
    _apply(f, body)
    await s.flush()
    return await _out(s, f)


@router.delete("/filters/{filter_id}")
async def filter_delete(filter_id: int, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session)):
    await s.delete(await _own(s, driver, filter_id))
    await s.flush()
    return {"ok": True}


@router.post("/pause")
async def feed_pause(body: PauseIn, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session)):
    driver.feed_paused = body.paused
    await s.flush()
    return await _state(s, driver)
