"""Group feed (decision 73): filters, recipients, Biznes priority, readers, duplicates. Every rule has a negative."""
from datetime import datetime, timedelta

import pytest
from conftest import make_driver
from tulporgo_core.config import Settings
from tulporgo_core.enums import Plan, RequestKind, UserbotStatus
from tulporgo_core.groupscan import Detection
from tulporgo_core.models import DriverFilter, GroupReader, UserbotAccount, UserbotGroup
from tulporgo_core.places import PlaceRef
from tulporgo_core.services import groupfeed as gf

NOW = datetime(2026, 11, 10, 13, 0)              # Tuesday 18:00 local
QOSH, SAM, JOSH, TOSH, JIZ = 1, 2, 3, 4, 5        # place ids; Jo'sh is a mahalla of Qo'shrabot
AREA = {QOSH: QOSH, SAM: SAM, JOSH: QOSH, TOSH: TOSH, JIZ: JIZ}
GROUP_X1, GROUP_X2 = -1001, -1002


def ref(pid, kind="district"):
    return PlaceRef(pid, str(pid), kind, area_id=AREA[pid] if AREA[pid] != pid else None)


def det(frm=JOSH, to=SAM, depart=None, seats=2, kind=RequestKind.PASSENGER):
    return Detection(kind, False, ref(frm) if frm else None, ref(to) if to else None, depart, seats, 0.9)


def flt(**kw):
    base = dict(name="kech", enabled=True, routes=[{"from": QOSH, "to": SAM}], time_from=None, time_to=None,
                include_asap=True, include_tomorrow=True, weekdays=[], seats_min=None, seats_max=None, kinds=[],
                group_chat_ids=[])
    base.update(kw)
    return DriverFilter(driver_id=0, **base)


def match(f, d, chat=GROUP_X1, now=NOW, corridors=()):
    return gf.filter_matches(f, d, chat, now, AREA.get, corridors)


def test_district_level_route():
    assert match(flt(), det(JOSH, SAM))                          # mahalla Jo'sh counts as Qo'shrabot
    assert not match(flt(), det(SAM, JOSH))                      # negative: the reverse direction is another route
    assert match(flt(), det(None, SAM))                          # origin not said, destination fits
    assert not match(flt(), det(None, TOSH))                     # negative


def test_on_the_way_needs_the_flag_and_a_corridor():
    corridor = [[SAM, JIZ, TOSH]]
    d = det(JIZ, TOSH)
    assert not match(flt(routes=[{"from": SAM, "to": TOSH}]), d, corridors=corridor)          # negative: no flag
    assert match(flt(routes=[{"from": SAM, "to": TOSH, "on_way": True}]), d, corridors=corridor)
    assert not match(flt(routes=[{"from": TOSH, "to": SAM, "on_way": True}]), d, corridors=corridor)  # wrong way


def test_time_window_asap_and_tomorrow():
    evening = flt(time_from="18:00", time_to="20:00")
    assert match(evening, det(depart=datetime(2026, 11, 10, 14, 0)))            # 19:00 local
    assert not match(evening, det(depart=datetime(2026, 11, 10, 16, 0)))        # negative: 21:00
    assert match(evening, det(depart=None))                                     # "hozir" at 18:00
    assert not match(flt(include_asap=False), det(depart=None))                 # negative
    tomorrow = det(depart=datetime(2026, 11, 11, 13, 30))
    assert match(evening, tomorrow) and not match(flt(include_tomorrow=False), tomorrow)
    night = flt(time_from="22:00", time_to="02:00")
    assert match(night, det(depart=datetime(2026, 11, 10, 20, 0)))              # 01:00 local next day
    assert not match(night, det(depart=datetime(2026, 11, 10, 7, 0)))           # negative: 12:00


def test_weekdays_seats_kinds_groups():
    assert match(flt(weekdays=[1]), det()) and not match(flt(weekdays=[5, 6]), det())       # Tuesday = 1
    assert not match(flt(seats_max=1), det(seats=2)) and not match(flt(seats_min=3), det(seats=2))
    assert match(flt(kinds=["parcel"]), det(kind=RequestKind.PARCEL))
    assert not match(flt(kinds=["parcel"]), det(kind=RequestKind.PASSENGER))
    assert match(flt(group_chat_ids=[GROUP_X1]), det()) and not match(flt(group_chat_ids=[GROUP_X2]), det())
    assert not match(flt(enabled=False), det())


async def _member(s, settings, chat=GROUP_X1, plan=None, consent=2, status=UserbotStatus.CONNECTED, **flt_kw):
    d = await make_driver(s, settings)
    if plan:
        d.plan, d.subscription_until = plan, NOW + timedelta(days=10)
    acc = UserbotAccount(driver_id=d.id, status=status, consent_version=consent, session_encrypted="x")
    s.add(acc)
    await s.flush()
    s.add(UserbotGroup(account_id=acc.id, chat_id=chat, title="x", enabled=True))
    f = flt(**flt_kw)
    f.driver_id = d.id
    s.add(f)
    await s.flush()
    return d, acc


async def test_recipients_members_only_biznes_first(s):
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    biz, _ = await _member(s, settings, plan=Plan.BUSINESS)
    pro, _ = await _member(s, settings, plan=Plan.PRO)
    outsider, _ = await _member(s, settings, chat=GROUP_X2, plan=Plan.BUSINESS)    # not in x1
    expired, _ = await _member(s, settings)                                          # trial over, no free period
    expired.subscription_until = NOW - timedelta(days=1)
    paused, _ = await _member(s, settings, plan=Plan.PRO)
    paused.feed_paused = True
    await s.flush()
    got = await gf.recipients(s, GROUP_X1, det(), settings, AREA.get, NOW)
    assert [(r.driver.id, r.delay) for r in got] == [(biz.id, timedelta(0)), (pro.id, gf.OTHERS_DELAY)]
    ids = {r.driver.id for r in got}
    assert outsider.id not in ids and expired.id not in ids and paused.id not in ids     # negatives


async def test_free_period_means_everyone_at_once(s, free_settings):
    a, _ = await _member(s, free_settings)
    got = await gf.recipients(s, GROUP_X1, det(), free_settings, AREA.get, NOW)
    assert [(r.driver.id, r.delay) for r in got] == [(a.id, timedelta(0))]


async def test_one_reader_per_wanted_group(s, settings):
    _, a1 = await _member(s, settings)
    _, a2 = await _member(s, settings)
    _, old = await _member(s, settings, consent=1)                              # only posting consent
    s.add(UserbotGroup(account_id=a1.id, chat_id=GROUP_X2, title="not selected", enabled=False))
    await s.flush()
    readers = await gf.assign_readers(s, NOW)
    assert set(readers) == {GROUP_X1} and readers[GROUP_X1] in {a1.id, a2.id}   # negative: x2 nobody selected
    assert readers[GROUP_X1] != old.id                                          # negative: no read consent


async def test_reader_failover_and_cleanup(s, settings):
    _, a1 = await _member(s, settings)
    _, a2 = await _member(s, settings)
    first = (await gf.assign_readers(s, NOW))[GROUP_X1]
    gone = a1 if first == a1.id else a2
    gone.status = UserbotStatus.STOPPED
    await s.flush()
    second = (await gf.assign_readers(s, NOW))[GROUP_X1]
    assert second != gone.id
    for f in (await s.execute(gf.select(DriverFilter))).scalars():
        f.enabled = False
    await s.flush()
    assert await gf.assign_readers(s, NOW) == {}                                 # nobody wants it -> not read
    assert (await s.execute(gf.select(GroupReader))).scalars().all() == []


@pytest.mark.parametrize("second_text,author2,same", [
    ("Samarqandga taksi kerak 2 kishi", 99, True),        # same text from someone else's repost
    ("Qoshrabotdan shaharga 2 kishi bor", 7, True),        # same author, same route and time
    ("Qoshrabotdan shaharga 2 kishi bor", 8, False),       # negative: another person
])
def test_duplicates_merge_across_groups(second_text, author2, same):
    dd = gf.Deduper()
    new, ev = dd.add(7, det(), "Samarqandga taksi kerak 2 kishi", GROUP_X1, 10, NOW)
    assert new
    new2, ev2 = dd.add(author2, det(), second_text, GROUP_X2, 20, NOW + timedelta(minutes=5))
    assert (not new2) is same
    if same:
        assert ev2 is ev and ev.links == [(GROUP_X1, 10), (GROUP_X2, 20)]


def test_duplicate_window_expires():
    dd = gf.Deduper()
    dd.add(7, det(), "x taksi kerak", GROUP_X1, 1, NOW)
    assert dd.add(7, det(), "x taksi kerak", GROUP_X2, 2, NOW + timedelta(minutes=31))[0]
