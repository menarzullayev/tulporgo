from datetime import timedelta

import pytest
from conftest import make_driver, make_user
from tulporgo_core.db import utcnow
from tulporgo_core.enums import OfferStatus, RequestStatus, TripStatus
from tulporgo_core.errors import Conflict, Forbidden, Invalid
from tulporgo_core.events import OfferAccepted, RequestCreated
from tulporgo_core.models import Trip
from tulporgo_core.services import rides


async def _request(s, settings, places, bus=None, **kw):
    p = await make_user(s)
    a, b, _ = places
    r = await rides.create_request(s, p, settings, from_text="Qo'shrabot", to_text="Samarqand",
                                   from_place_id=a.id, to_place_id=b.id, bus=bus, **kw)
    return p, r


async def test_full_flow_with_counter_price(s, settings, places, bus):
    p, r = await _request(s, settings, places, bus)
    d = await make_driver(s, settings)
    assert d in await rides.matching_drivers(s, r, settings)
    o = await rides.send_offer(s, d, r, settings, 40_000, bus=bus)
    await rides.counter_offer(s, p, o, 35_000, bus=bus)
    t = await rides.respond_counter(s, d, o, accept=True, bus=bus)
    assert isinstance(t, Trip) and t.price == 35_000 and r.status == RequestStatus.MATCHED
    await rides.start_trip(s, d.user, t)
    await rides.complete_trip(s, p, t, bus=bus)
    assert t.status == TripStatus.COMPLETED and r.status == RequestStatus.COMPLETED
    assert any(isinstance(e, RequestCreated) for e in bus.published) and any(isinstance(e, OfferAccepted) for e in bus.published)


async def test_second_acceptance_is_rejected(s, settings, places):
    # negative: two offers accepted for one request → only the first makes a trip
    p, r = await _request(s, settings, places)
    d1, d2 = await make_driver(s, settings), await make_driver(s, settings)
    o1 = await rides.send_offer(s, d1, r, settings, 40_000)
    o2 = await rides.send_offer(s, d2, r, settings, 38_000)
    await rides.accept_offer(s, p, o2)
    with pytest.raises(Conflict):
        await rides.accept_offer(s, p, o1)
    assert o1.status in (OfferStatus.DECLINED, OfferStatus.SENT) and o2.status == OfferStatus.ACCEPTED


async def test_other_offers_declined_after_accept(s, settings, places):
    p, r = await _request(s, settings, places)
    d1, d2 = await make_driver(s, settings), await make_driver(s, settings)
    o1 = await rides.send_offer(s, d1, r, settings, 40_000)
    o2 = await rides.send_offer(s, d2, r, settings, 38_000)
    await rides.accept_offer(s, p, o2)
    await s.refresh(o1)
    assert o1.status == OfferStatus.DECLINED


async def test_driver_cancel_reopens_request_and_keeps_history(s, settings, places):
    p, r = await _request(s, settings, places)
    d1, d2 = await make_driver(s, settings), await make_driver(s, settings)
    t = await rides.accept_offer(s, p, await rides.send_offer(s, d1, r, settings, 40_000))
    await rides.cancel_trip(s, d1.user, t)
    assert r.status == RequestStatus.OPEN and t.status == TripStatus.CANCELLED
    t2 = await rides.accept_offer(s, p, await rides.send_offer(s, d2, r, settings, 42_000))
    assert t2.id != t.id and r.status == RequestStatus.MATCHED          # re-matched; first trip still stored


async def test_passenger_cancel_closes_request(s, settings, places):
    p, r = await _request(s, settings, places)
    d = await make_driver(s, settings)
    t = await rides.accept_offer(s, p, await rides.send_offer(s, d, r, settings, 40_000))
    await rides.cancel_trip(s, p, t)
    assert r.status == RequestStatus.CANCELLED


async def test_counter_must_be_lower_and_only_by_owner(s, settings, places):
    p, r = await _request(s, settings, places)
    d = await make_driver(s, settings)
    o = await rides.send_offer(s, d, r, settings, 40_000)
    with pytest.raises(Invalid):
        await rides.counter_offer(s, p, o, 45_000)                        # negative: counter higher than offer
    stranger = await make_user(s)
    with pytest.raises(Forbidden):
        await rides.counter_offer(s, stranger, o, 30_000)                 # negative: not the passenger


async def test_driver_without_subscription_cannot_offer(s, settings, free_settings, places):
    p, r = await _request(s, settings, places)
    d = await make_driver(s, settings)
    d.subscription_until = utcnow() - timedelta(days=1)                   # trial over
    with pytest.raises(Forbidden):
        await rides.send_offer(s, d, r, settings, 40_000)
    assert d not in await rides.matching_drivers(s, r, settings)
    o = await rides.send_offer(s, d, r, free_settings, 40_000)            # free period (decision 44) → allowed
    assert o.status == OfferStatus.SENT


async def test_request_rules(s, settings, places):
    a, b, _ = places
    p = await make_user(s)
    with pytest.raises(Invalid):
        await rides.create_request(s, p, settings, from_text="x", to_text="y", from_place_id=a.id, to_place_id=a.id)
    with pytest.raises(Invalid):
        await rides.create_request(s, p, settings, from_text="x", to_text="y", seats=9)
    for _ in range(rides.MAX_OPEN_REQUESTS):
        await rides.create_request(s, p, settings, from_text="x", to_text="y")
    with pytest.raises(Conflict):                                          # negative: spam guard
        await rides.create_request(s, p, settings, from_text="x", to_text="y")
    blocked = await make_user(s, is_blocked=True)
    with pytest.raises(Forbidden):
        await rides.create_request(s, blocked, settings, from_text="x", to_text="y")


async def test_expire(s, settings, places):
    p, r = await _request(s, settings, places)
    d = await make_driver(s, settings)
    o = await rides.send_offer(s, d, r, settings, 40_000)
    ids = await rides.expire_requests(s, now=r.expires_at + timedelta(minutes=1))
    await s.refresh(r)
    await s.refresh(o)
    assert ids == [r.id] and r.status == RequestStatus.EXPIRED and o.status == OfferStatus.EXPIRED


async def test_matching_prefers_home_area(s, settings, places):
    a, b, c = places
    p, r = await _request(s, settings, places)
    far = await make_driver(s, settings, home_place_id=c.id)
    near = await make_driver(s, settings, home_place_id=a.id)
    got = await rides.matching_drivers(s, r, settings)
    assert got.index(near) < got.index(far)


async def test_women_only_flag_copied(s, settings, places):
    a, b, _ = places
    w = await make_user(s, is_woman=True)
    r = await rides.create_request(s, w, settings, from_text="x", to_text="y", from_place_id=a.id, to_place_id=b.id)
    assert r.women_only is True
