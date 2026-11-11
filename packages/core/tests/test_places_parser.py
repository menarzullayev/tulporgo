from datetime import datetime

import pytest
from tulporgo_core.parser import parse
from tulporgo_core.places import PlaceIndex, key, seed, strip_suffix, to_latin


@pytest.mark.parametrize("spelling", ["Qo'shrabot", "Qoshrabot", "Qo‘shrabot", "Qöşrabot", "Қўшработ", "qoʻshrabot"])
def test_one_key_for_every_spelling(spelling):
    assert key(spelling) == key("Qo'shrabot") == "koshrabot"


def test_q_and_k_x_and_h_unified():
    assert key("Samarqand") == key("Samarkand") == key("Самарканд")
    assert key("Xatirchi") == key("Hatirchi")


def test_suffixes():
    assert strip_suffix("Qo'shrabotdan") == "qo'shrabot"
    assert strip_suffix("Samarqandga") == "samarqand"
    assert strip_suffix("Ishtixon") == "ishtixon"           # negative: no suffix → unchanged
    assert strip_suffix("Uyda") == "uyda"                   # negative: stem would be too short


def test_to_latin_cyrillic():
    assert to_latin("Ўзбекистон") == "o'zbekiston"


async def test_index_exact_and_fuzzy(s, places):
    idx = await PlaceIndex.load(s)
    assert idx.exact("Кошрабад").name == "Qo'shrabot"        # alias
    assert idx.exact("Samarkandga").name == "Samarqand"
    assert [r.name for r in idx.search("samar")] == ["Samarqand"]
    assert idx.search("Qoshrabod")[0].name == "Qo'shrabot"   # typo → fuzzy
    assert idx.exact("Toshkent") is None                     # negative


async def test_seed_is_idempotent(s, tmp_path):
    (tmp_path / "regions_districts.csv").write_text(
        "region_code,region_uz,district_code,district_uz,kind\n,Samarqand viloyati,,Qo'shrabot tumani,tuman\n"
        ",Samarqand viloyati,,Samarqand,shahar\n", encoding="utf-8")
    (tmp_path / "samarqand_mahallas.csv").write_text(
        "district_uz,mahalla_uz,source\nQo'shrabot tumani,Qovunchi,test\n", encoding="utf-8")
    first = await seed(s, tmp_path)
    second = await seed(s, tmp_path)
    assert first == 5 and second == 0        # country, region, 2 districts, 1 mahalla; nothing on the 2nd run


NOW = datetime(2026, 11, 10, 3, 0)            # 08:00 in Tashkent (UTC+5)


async def idx_of(s):
    return await PlaceIndex.load(s)


@pytest.mark.parametrize("text,frm,to", [
    ("Qo'shrabot → Samarqand 07:30", "Qo'shrabot", "Samarqand"),
    ("Qoshrabot - Samarqand", "Qo'shrabot", "Samarqand"),
    ("Qoshrabotdan Samarqandga ertaga 8 da 2 kishi", "Qo'shrabot", "Samarqand"),
    ("Самарканд Кошрабад завтра 18:00", "Samarqand", "Qo'shrabot"),
    ("taksi kerak Samarqanddan Qovunchiga", "Samarqand", "Qovunchi"),
])
async def test_parse_routes(s, places, text, frm, to):
    r = parse(text, await idx_of(s), now=NOW)
    assert r and r.from_place.name == frm and r.to_place.name == to


async def test_parse_time_and_seats(s, places):
    idx = await idx_of(s)
    r = parse("Qoshrabotdan Samarqandga ertaga 8 da 2 kishi", idx, now=NOW)
    assert r.seats == 2 and r.depart_at == datetime(2026, 11, 11, 3, 0)      # 08:00 local tomorrow, stored UTC
    r = parse("Qo'shrabot → Samarqand 07:30", idx, now=NOW)                  # 07:30 already passed today → tomorrow
    assert r.depart_at == datetime(2026, 11, 11, 2, 30)
    r = parse("Samarqand - Qo'shrabot hozir", idx, now=NOW)
    assert r.depart_at is None and r.seats == 1


@pytest.mark.parametrize("text", ["", "salom", "narxi qancha?", "Toshkent - Buxoro"])
async def test_parse_returns_none_without_route(s, places, text):
    # negative: never guess a route that is not there (unknown places on both sides → buttons instead)
    assert parse(text, await idx_of(s), now=NOW) is None


async def test_only_approved_landmarks_are_seeded(s, tmp_path):
    (tmp_path / "regions_districts.csv").write_text(
        "region_code,region_uz,district_code,district_uz,kind\n,Samarqand viloyati,,Qo'shrabot,tuman\n", encoding="utf-8")
    (tmp_path / "landmarks.csv").write_text(
        "region_uz,district_uz,kind,name_uz,aliases,approved,note\n"
        "Samarqand viloyati,Qo'shrabot,mahalla,Jo'sh,Josh|Jush,yes,\n"
        "Samarqand viloyati,Qo'shrabot,poi,Mayiz bozor,Mayiz bozori,no,draft\n", encoding="utf-8")
    await seed(s, tmp_path)
    idx = await PlaceIndex.load(s)
    josh = idx.exact("Jushdan")
    assert josh and josh.name == "Jo'sh" and josh.area == idx.exact("Qo'shrabot").id    # belongs to its district
    assert idx.exact("Mayiz bozor") is None                                             # negative: not approved


async def test_only_approved_corridors_with_known_stops(s, tmp_path, places):
    from tulporgo_core.places import corridors
    (tmp_path / "corridors.csv").write_text(
        "name,stops,approved,note\nA,Qo'shrabot|Samarqand,yes,\nB,Samarqand|Qo'shrabot,no,\n"
        "C,Qo'shrabot|Atlantida,yes,\n", encoding="utf-8")
    idx = await PlaceIndex.load(s)
    assert corridors(idx, tmp_path) == [[places[0].id, places[1].id]]    # B not approved, C has an unknown stop
