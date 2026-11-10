from datetime import timedelta

import fakeredis.aioredis
import pytest
from conftest import make_driver, make_user
from tulporgo_core.db import utcnow
from tulporgo_core.enums import PaymentStatus, Plan, TripStatus
from tulporgo_core.errors import Conflict, Forbidden, Invalid
from tulporgo_core.events import InMemoryBus, OfferCreated, RedisBus, ReferralGranted, decode, encode
from tulporgo_core.services import billing, drivers, feedback, kpi, referral, rides, users


async def test_phone_and_plate_normalization():
    assert users.normalize_phone("+998 (90) 123-45-67") == "+998901234567"
    assert users.normalize_phone("901234567") == "+998901234567"
    assert drivers.normalize_plate("30 a 123 bc") == "30A123BC"
    with pytest.raises(Invalid):
        users.normalize_phone("+7 999 123 45 67")                       # negative: not an Uzbek mobile
    with pytest.raises(Invalid):
        drivers.normalize_plate("ABC 123")


async def test_register_requires_phone_and_unique_plate(s, settings):
    u = await make_user(s)
    with pytest.raises(Invalid):
        await drivers.register_driver(s, u, settings, car_make="Nexia", car_color="qora", car_plate="30A111BC")
    d = await make_driver(s, settings, plate="30A111BC")
    assert d.subscription_until > utcnow() + timedelta(days=6)           # 7-day trial
    with pytest.raises(Conflict):
        await make_driver(s, settings, plate="30 A 111 BC")              # negative: same plate, other spelling


async def test_verify_needs_docs_and_admin(s, settings):
    d = await make_driver(s, settings)
    admin = await make_user(s, is_admin=True)
    with pytest.raises(Invalid):
        await drivers.verify(s, admin, d, settings)                      # negative: no documents
    await drivers.submit_documents(s, d, "lic", "tech")
    with pytest.raises(Forbidden):
        await drivers.verify(s, await make_user(s), d, settings)         # negative: not an admin
    await drivers.verify(s, admin, d, settings)
    assert d.verified


async def test_referral_bonus_on_verification_once(s, settings):
    bus = InMemoryBus()
    inviter = await make_driver(s, settings)
    code = inviter.user.referral_code
    assert code and referral.code_from_start(f"ref_{code.lower()}") == code
    before = inviter.subscription_until
    newbie = await make_driver(s, settings, referral_code=code)
    admin = await make_user(s, is_admin=True)
    await drivers.submit_documents(s, newbie, "lic", "tech")
    newbie_before = newbie.subscription_until
    await drivers.verify(s, admin, newbie, settings, bus)
    assert inviter.subscription_until == before + timedelta(days=7) and inviter.ambassador
    assert newbie.subscription_until == newbie_before + timedelta(days=7)
    assert [e for e in bus.published if isinstance(e, ReferralGranted)]
    newbie.verified = False                                              # negative: a second verification
    await drivers.verify(s, admin, newbie, settings, bus)                # must not pay twice
    assert inviter.subscription_until == before + timedelta(days=7)


async def test_self_referral_rejected(s, settings):
    u = await make_user(s)
    await users.ensure_referral_code(s, u)
    with pytest.raises(Invalid):
        await referral.link(s, u, u.referral_code)


async def test_billing(s, settings, free_settings):
    assert billing.price_of(Plan.PRO, 3) == 177_000                      # no invented discount
    assert billing.stars_amount(29_000, settings) == round(29_000 / settings.stars_rate_uzs)
    d = await make_driver(s, settings)
    assert billing.effective_plan(d, free_settings).plan == Plan.BUSINESS
    p = await billing.create_payment(s, d.user, "p2p", Plan.PRO)
    until = d.subscription_until
    await billing.mark_paid(s, p, d)
    await billing.mark_paid(s, p, d)                                     # negative: idempotent
    assert p.status == PaymentStatus.PAID and d.plan == Plan.PRO
    assert d.subscription_until == until + timedelta(days=30)
    with pytest.raises(Invalid):
        billing.price_of(Plan.PRO, 2)


async def test_ratings_and_complaints(s, settings, places):
    a, b, _ = places
    p = await make_user(s)
    d = await make_driver(s, settings)
    r = await rides.create_request(s, p, settings, from_text="a", to_text="b", from_place_id=a.id, to_place_id=b.id)
    t = await rides.accept_offer(s, p, await rides.send_offer(s, d, r, settings, 30_000))
    with pytest.raises(Conflict):
        await feedback.rate(s, p, t, 5)                                  # negative: not completed yet
    await rides.complete_trip(s, p, t)
    assert t.status == TripStatus.COMPLETED
    await feedback.rate(s, p, t, 4, "yaxshi")
    assert d.rating == 4.0
    with pytest.raises(Conflict):
        await feedback.rate(s, p, t, 5)                                  # negative: once per trip
    c = await feedback.complain(s, p, "Haydovchi kechikdi", against=d.user, trip=t)
    with pytest.raises(Forbidden):
        await feedback.resolve(s, p, c, True, "ok")
    await feedback.resolve(s, await make_user(s, is_admin=True), c, True, "ogohlantirildi")


async def test_kpi(s, settings, places):
    await make_driver(s, settings)
    k = await kpi.compute(s)
    assert k.values["drivers"] == 1 and k.values["blocked_userbots"] == 0
    text = kpi.report(k)
    assert "Ro'yxatdan o'tgan haydovchilar: 1" in text and "maqsad 30 kun: 100" in text


async def test_events_roundtrip_and_redis_bus():
    e = OfferCreated(offer_id=1, request_id=2)
    assert decode(encode(e)) == e
    r = fakeredis.aioredis.FakeRedis()
    bus = RedisBus(r)
    got = []

    async def h(ev):
        got.append(ev)
    bus.subscribe(OfferCreated, h)
    import asyncio
    stop = asyncio.Event()
    task = asyncio.create_task(bus.listen(stop))
    await asyncio.sleep(0.05)
    await bus.publish(e)
    for _ in range(50):
        if got:
            break
        await asyncio.sleep(0.02)
    stop.set()
    await task
    assert got == [e]


async def test_failing_handler_does_not_block_others():
    bus = InMemoryBus()
    got = []

    async def bad(ev):
        raise RuntimeError("x")

    async def good(ev):
        got.append(ev)
    bus.subscribe(OfferCreated, bad)
    bus.subscribe(OfferCreated, good)
    await bus.publish(OfferCreated(1, 2))
    assert len(got) == 1
