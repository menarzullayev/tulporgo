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
    # 2026-11-11 group survey: Russian and misspelt names of other regions' centres
    ("Toshkentga", "Toshkent shahri"),         # the capital, not Toshkent tumani of Toshkent viloyati
    ("Ташкент", "Toshkent shahri"),
    ("Тошкентдан", "Toshkent shahri"),
    ("Навойига", "Navoiy shahri"),
    ("Навои", "Navoiy shahri"),
    ("Бухара", "Buxoro shahri"),
    ("Джизак", "Jizzax shahri"),
    ("Фергана", "Farg'ona shahri"),
    ("Коканд", "Qo'qon shahri"),
    ("Нурата", "Nurota"),
    ("Нурабод", "Nurobod"),
    ("Урганчидан", "Urganch shahri"),          # colloquial linking -i- before the suffix
    ("Qarshi", "Qarshi shahri"),               # negative: a name that really ends in -i is untouched
    ("Toshkent viloyatiga", "Toshkent viloyati"),
])
async def test_what_passengers_type(idx, typed, expected):
    assert idx.exact(typed).name == expected


async def test_linking_i_needs_a_suffix(idx):
    assert idx.exact("Urganchi") is None       # negative: no suffix stripped -> no -i- fallback


async def test_survey_message_with_cyrillic_navoiy(idx):
    from tulporgo_core.groupscan import detect
    d = detect("Навойига кишлокдан 1киши бор хозирга", idx)
    assert d is not None and d.to_place.name == "Navoiy shahri" and d.from_place is None and d.seats == 1


async def test_generic_village_is_not_a_place(idx):
    from tulporgo_core.groupscan import detect
    d = detect("Shahardan qishloqga 3 kishi bor hozirga", idx)          # survey message
    assert d is not None and d.from_place.name == "Samarqand shahri" and d.to_place is None   # not "Katta qishloq"
    assert idx.exact("Katta qishloqqa").name == "Katta qishloq"         # negative: the real mahalla still resolves
    assert detect("Qishloqqa 2 kishi bor", idx) is None                  # single generic word: no place, no card


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


@pytest.mark.parametrize("text,frm,to", [                              # 2026-11-11 survey messages
    ("Ertalabga urganchidan zarofshonga taksi kerak", "Urganch shahri", "Zarafshon shahri"),
    ("Qoʻshrobotga taksi bormi sebistonda bir kishi bor", "Sebiston", "Qo'shrabot"),
    ("Sebistonda bir kishi bor", "Sebiston", None),                     # -da: where the passenger is
    ("Qovunchidan Qoshrabotga taksi kk 1 kishi bor", "Kovunchi", "Qo'shrabot"),
    ("Nurota 2 kishi bor taksi kerak", None, "Nurota"),                 # negative: -ta here is part of the name
])
async def test_survey_routes(idx, text, frm, to):
    from tulporgo_core.groupscan import detect
    d = detect(text, idx)
    assert d is not None
    assert (d.from_place.name if d.from_place else None) == frm and (d.to_place.name if d.to_place else None) == to


async def test_suffix_role(idx):
    from tulporgo_core.parser import suffix_role
    assert suffix_role("Nurotadan", idx) == "from" and suffix_role("Sebistonda", idx) == "from"
    assert suffix_role("Samarqandga", idx) == "to"
    assert suffix_role("Nurota", idx) is None and suffix_role("ertaga", idx) is None      # negatives
