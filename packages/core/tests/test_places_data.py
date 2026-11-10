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
