"""Privacy policy §8: export and delete own data."""
import json

import pytest
from conftest import make_driver, make_user
from sqlalchemy import func, select
from tulporgo_core.enums import OfferStatus, RequestStatus, TripStatus, UserbotStatus
from tulporgo_core.errors import Conflict
from tulporgo_core.events import UserbotStopped
from tulporgo_core.models import Payment, Rating, RideRequest, Trip, User, UserbotAccount, UserbotGroup, UserbotPost
from tulporgo_core.services import billing, privacy, rides, users

SESSION = "gAAAAAB-secret-session-token"
DOC = "AgACAgIAAxkBAAI-doc-file-id"


async def _trip(s, settings, passenger, driver, bus):
    r = await rides.create_request(s, passenger, settings, from_text="Qo'shrabot", to_text="Samarqand", bus=bus)
    o = await rides.send_offer(s, driver, r, settings, price=30000, bus=bus)
    return await rides.accept_offer(s, passenger, o, bus=bus)


async def _with_userbot(s, driver, status=UserbotStatus.CONNECTED):
    acc = UserbotAccount(driver_id=driver.id, session_encrypted=SESSION, tg_user_id=555, status=status)
    s.add(acc)
    await s.flush()
    g = UserbotGroup(account_id=acc.id, chat_id=-100123, title="Qo'shrabot taksi")
    s.add(g)
    await s.flush()
    s.add(UserbotPost(group_id=g.id))
    await s.flush()
    return acc


async def test_export_contains_own_data_but_no_secrets(s, settings, bus):
    p = await make_user(s, phone="+998901234567", username="yolovchi")
    d = await make_driver(s, settings)
    d.license_file_id = DOC
    d.car_photo_file_id = DOC
    await _with_userbot(s, d)
    t = await _trip(s, settings, p, d, bus)
    await rides.complete_trip(s, p, t, bus=bus)
    await billing.create_payment(s, d.user, provider="p2p", plan="pro", months=1)

    pdata = await privacy.export_user_data(s, p)
    assert pdata["profile"]["phone"] == "+998901234567"
    assert pdata["requests"][0]["from"] == "Qo'shrabot"
    assert pdata["trips"][0]["role"] == "passenger"

    ddata = await privacy.export_user_data(s, d.user)
    assert ddata["driver"]["documents_on_file"] is True
    assert ddata["userbot"]["groups"] == [{"title": "Qo'shrabot taksi", "enabled": True}]
    assert ddata["trips"][0]["role"] == "driver"
    assert ddata["payments"][0]["plan"] == "pro"
    dumped = json.dumps(ddata, ensure_ascii=False)
    # negative: the encrypted session and Telegram file ids never leave the server
    assert SESSION not in dumped and DOC not in dumped


async def test_delete_refused_during_active_trip(s, settings, bus):
    p = await make_user(s)
    d = await make_driver(s, settings)
    t = await _trip(s, settings, p, d, bus)
    assert t.status == TripStatus.CONFIRMED
    with pytest.raises(Conflict):
        await privacy.delete_user_data(s, p)
    with pytest.raises(Conflict):
        await privacy.delete_user_data(s, d.user)


async def test_delete_passenger_anonymises_and_keeps_history(s, settings, bus):
    p = await make_user(s, phone="+998901234567", username="yolovchi", is_woman=True)
    tg = p.tg_id
    d = await make_driver(s, settings)
    t = await _trip(s, settings, p, d, bus)
    await rides.complete_trip(s, p, t, bus=bus)
    s.add(Rating(trip_id=t.id, from_user_id=p.id, to_user_id=d.user_id, stars=5, comment="Zo'r haydovchi"))
    open_r = await rides.create_request(s, p, settings, from_text="A", to_text="B", note="uy oldida")
    await s.flush()

    rep = await privacy.delete_user_data(s, p)

    assert rep.requests_cancelled == 1 and not rep.tg_id_kept_for_ban
    await s.refresh(p)
    assert (p.phone, p.username, p.first_name, p.is_woman, p.referral_code) == (None, None, None, False, None)
    assert p.tg_id < 0
    await s.refresh(open_r)
    assert open_r.status == RequestStatus.CANCELLED and open_r.note is None
    rating = (await s.execute(select(Rating).where(Rating.trip_id == t.id))).scalar_one()
    assert rating.stars == 5 and rating.comment is None            # driver's rating stays, words are removed
    assert await s.scalar(select(func.count()).select_from(Trip)) == 1   # the driver's history stays

    # the same person coming back gets a fresh account, not the anonymised one
    again = await users.get_or_create_user(s, tg, first_name="Yangi")
    assert again.id != p.id


async def test_delete_driver_removes_userbot_and_documents(s, settings, bus):
    d = await make_driver(s, settings)
    d.license_file_id = d.techpass_file_id = d.car_photo_file_id = DOC
    acc = await _with_userbot(s, d)
    passenger = await make_user(s)
    r = await rides.create_request(s, passenger, settings, from_text="A", to_text="B")
    o = await rides.send_offer(s, d, r, settings, price=20000)
    await billing.create_payment(s, d.user, provider="p2p", plan="pro", months=1)

    rep = await privacy.delete_user_data(s, d.user, bus=bus)

    assert rep.userbot_deleted and rep.offers_withdrawn == 1
    assert any(isinstance(e, UserbotStopped) and e.account_id == acc.id for e in bus.published)
    for model in (UserbotAccount, UserbotGroup, UserbotPost):
        assert await s.scalar(select(func.count()).select_from(model)) == 0
    await s.refresh(d)
    await s.refresh(o)
    assert (d.license_file_id, d.techpass_file_id, d.car_photo_file_id) == (None, None, None)
    assert d.car_plate.startswith("DELETED")
    assert o.status == OfferStatus.WITHDRAWN
    assert await s.scalar(select(func.count()).select_from(Payment)) == 1   # accounting record stays
    assert (await s.get(RideRequest, r.id)).status == RequestStatus.OPEN    # the passenger's request is untouched


async def test_blocked_user_keeps_tg_id_so_the_ban_holds(s):
    u = await make_user(s, phone="+998901234567", is_blocked=True)
    tg = u.tg_id
    rep = await privacy.delete_user_data(s, u)
    assert rep.tg_id_kept_for_ban
    assert (await s.execute(select(User).where(User.tg_id == tg))).scalar_one().is_blocked
    assert u.phone is None


async def test_paused_userbot_deleted_without_event(s, settings, bus):
    # negative: only a connected account has a live client to stop
    d = await make_driver(s, settings)
    await _with_userbot(s, d, status=UserbotStatus.PAUSED)
    await privacy.delete_user_data(s, d.user, bus=bus)
    assert not any(isinstance(e, UserbotStopped) for e in bus.published)
    assert await s.scalar(select(func.count()).select_from(UserbotAccount)) == 0
