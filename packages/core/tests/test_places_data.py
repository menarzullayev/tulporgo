"""The shipped places data (tulporgo_core/data) loads and resolves what passengers actually type."""
import pytest
from tulporgo_core.parser import parse
from tulporgo_core.places import PlaceIndex, seed


@pytest.fixture
async def idx(s):
    await seed(s)
    await s.flush()
    return await PlaceIndex.load(s)


async def test_counts(idx):
    kinds = {}
    for r in idx.refs:
        kinds[r.kind] = kinds.get(r.kind, 0) + 1
    assert kinds["region"] == 14
    assert kinds["district"] + kinds["city"] == 206
    assert kinds["mahalla"] >= 1000


@pytest.mark.parametrize("typed,expected", [
    ("Samarqand", "Samarqand shahri"),         # the city, not Samarqand tumani
    ("Самарканд", "Samarqand shahri"),
    ("Кошрабад", "Qo'shrabot"),
    ("Kattakurgan", "Kattaqo'rg'on shahri"),
    ("Urgut", "Urgut"),
])
async def test_what_passengers_type(idx, typed, expected):
    assert idx.exact(typed).name == expected


async def test_parse_with_real_data(idx):
    r = parse("Qo'shrabotdan Samarqandga 2 kishi", idx)
    assert r.from_place.name == "Qo'shrabot" and r.to_place.name == "Samarqand shahri" and r.seats == 2


async def test_mahallas_attach_to_samarqand_region_only(s, idx):
    # negative: a district name repeated in another region must not receive Samarqand mahallas
    from sqlalchemy import select
    from tulporgo_core.models import Place
    regions = {p.id: p.name_uz for p in (await s.execute(select(Place).where(Place.kind == "region"))).scalars()}
    districts = {p.id: p for p in (await s.execute(select(Place).where(Place.kind.in_(["district", "city"])))).scalars()}
    parents = {p.parent_id for p in (await s.execute(select(Place).where(Place.kind == "mahalla"))).scalars()}
    assert parents and all(regions[districts[pid].parent_id] == "Samarqand viloyati" for pid in parents if pid)


async def test_approved_landmarks_resolve_to_their_district(idx):
    qosh = idx.exact("Qo'shrabot")
    for typed in ("Jo'sh", "Joshdan", "O'razmat", "Chinor", "Sebiston", "Mayiz bozor", "Mol bozor", "bozorga"):
        ref = idx.exact(typed)
        assert ref is not None and ref.area == qosh.id, typed               # all in Qo'shrabot (owner, decision 74)
    assert idx.exact("Dagbit").area != qosh.id                              # negative: Dagbit is on the way, not here


async def test_real_corridor_makes_dagbit_on_the_way(idx):
    from tulporgo_core.enums import RequestKind
    from tulporgo_core.groupscan import Detection
    from tulporgo_core.models import DriverFilter
    from tulporgo_core.places import corridors
    from tulporgo_core.services.groupfeed import filter_matches
    roads = corridors(idx)
    qosh, sam, dagbit = idx.exact("Qo'shrabot"), idx.exact("Samarqand"), idx.exact("Dagbit")
    area = {r.id: r.area for r in idx.refs}.get
    det = Detection(RequestKind.PASSENGER, False, qosh, dagbit, None, 1, 0.9)
    f = DriverFilter(name="x", enabled=True, routes=[{"from": qosh.id, "to": sam.id, "on_way": True}], kinds=[],
                     weekdays=[], group_chat_ids=[], include_asap=True, include_tomorrow=True)
    from datetime import datetime
    assert filter_matches(f, det, -1, datetime(2026, 11, 10, 6, 0), area, roads)
    f.routes = [{"from": sam.id, "to": qosh.id, "on_way": True}]           # negative: the other direction
    assert not filter_matches(f, det, -1, datetime(2026, 11, 10, 6, 0), area, roads)
