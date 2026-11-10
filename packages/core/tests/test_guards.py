"""Defensive guards added while making the core type-clean: they must refuse, not crash with AttributeError."""
import pytest
from conftest import make_driver, make_user
from tulporgo_core.enums import OfferStatus, TripStatus
from tulporgo_core.errors import Conflict, NotFound
from tulporgo_core.models import Offer, Trip
from tulporgo_core.services import feedback, rides


async def test_rate_trip_with_missing_driver_is_not_found(s):
    p = await make_user(s)
    t = Trip(request_id=1, offer_id=1, driver_id=999_999, passenger_id=p.id, price=1, share_token="x",
             status=TripStatus.COMPLETED)
    with pytest.raises(NotFound):
        await feedback.rate(s, p, t, 5)


async def test_countered_offer_without_counter_price_is_refused(s, settings):
    d = await make_driver(s, settings)
    o = Offer(request_id=1, driver_id=d.id, price=30000, counter_price=None, status=OfferStatus.COUNTERED)
    with pytest.raises(Conflict):
        await rides.respond_counter(s, d, o, accept=True)
