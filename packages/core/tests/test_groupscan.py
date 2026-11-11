"""Reading taxi groups (decision 73): requests vs driver ads, request kinds, routes. Messages are synthetic."""
from datetime import datetime

import pytest
from tulporgo_core.enums import MessageClass, RequestKind
from tulporgo_core.groupscan import MIN_CONFIDENCE, RuleClassifier, detect
from tulporgo_core.models import Place
from tulporgo_core.places import PlaceIndex

NOW = datetime(2026, 11, 10, 6, 0)            # 11:00 local


@pytest.fixture
async def idx(s, places):
    qosh = places[0]
    s.add_all([Place(kind="poi", name_uz="Mayiz bozor", aliases=["mayiz bozori"], parent_id=qosh.id),
               Place(kind="mahalla", name_uz="Jo'sh", aliases=["josh"], parent_id=qosh.id),
               Place(kind="city", name_uz="Toshkent", name_ru="Ташкент")])
    await s.flush()
    return await PlaceIndex.load(s)


@pytest.mark.parametrize("text", [
    "Samarqandga taksi kerak 2 kishi",
    "Qoshrabotdan shaharga kim ketyapti?",
    "Ertaga 7da Toshkentga ketadigan moshin bormi",
    "2 kishi bor Joshdan Samarqandga",
    "Нужно такси до Самарканда",
    "Кто едет в Ташкент завтра?",
    "Samarqandga ketishim kerak, necha pul?",
])
def test_passenger_requests_are_requests(text):
    cls, conf = RuleClassifier().classify(text)
    assert cls == MessageClass.REQUEST and conf >= MIN_CONFIDENCE


@pytest.mark.parametrize("text", [
    "Samarqandga ketamiz 2 joy bor",
    "Toshkentga moshin bor 3 kishi kerak",
    "Cobalt bor, yo'lovchi olamiz Qo'shrabotdan",
    "Qo'shrabot - Samarqand 1 joy bor, pochta ham olaman",
    "Еду в Самарканд, есть 2 места",
    "Dostavka xizmati, 24/7",
])
def test_driver_ads_never_become_requests(text):
    # negative: a driver offering seats must never reach other drivers as a passenger request
    assert RuleClassifier().classify(text)[0] == MessageClass.DRIVER_AD


@pytest.mark.parametrize("text", ["Assalomu alaykum", "Bugun svet yo'q", "Rahmat aka", ""])
def test_chat_is_other(text):
    assert RuleClassifier().classify(text)[0] == MessageClass.OTHER


async def test_route_time_seats(idx):
    d = detect("Qoshrabotdan Samarqandga ertaga 8 da 2 kishi bor", idx, now=NOW)
    assert d and d.kind == RequestKind.PASSENGER and not d.cargo
    assert d.from_place.name == "Qo'shrabot" and d.to_place.name == "Samarqand"
    assert d.seats == 2 and d.depart_at == datetime(2026, 11, 11, 3, 0)


async def test_destination_only(idx):
    d = detect("Samarqandga taksi kerak", idx, now=NOW)
    assert d and d.from_place is None and d.to_place.name == "Samarqand" and d.depart_at is None


@pytest.mark.parametrize("text,kind,cargo", [
    ("Samarqandga pochta bor, kim olib ketadi?", RequestKind.PARCEL, False),
    ("Samarqandga yuk bor, damas kerak", RequestKind.CARGO, True),
    ("2 kishi bor yuk bilan Samarqandga, taksi kerak", RequestKind.PASSENGER, True),
    ("Samarqanddan dori olib kelib bering, taksi kerak", RequestKind.DELIVERY, False),
    ("Mayiz bozorga 2 kishi bor, kim ketadi?", RequestKind.BAZAAR, False),
    ("Samarqandga labo kerak soat 11 larga", RequestKind.CARGO, True),        # goods vehicle = cargo (survey)
    ("Samarqandga gazel kerak", RequestKind.CARGO, True),
    ("Samarqandga labo kerak 2 kishi bor", RequestKind.PASSENGER, True),      # negative: people ride along
    ("Samarqandga damas kerak", RequestKind.PASSENGER, False),                # negative: Damas carries people
])
async def test_kinds(idx, text, kind, cargo):
    d = detect(text, idx, now=NOW)
    assert d and d.kind == kind and d.cargo == cargo


async def test_mahalla_and_poi_belong_to_their_district(idx, places):
    d = detect("Joshdan Mayiz bozorga kim ketadi?", idx, now=NOW)
    assert d.from_place.area == places[0].id and d.to_place.area == places[0].id


@pytest.mark.parametrize("text", [
    "Samarqandga ketamiz 2 joy bor",             # driver ad
    "Toshkent - Buxoroga taksi kerak",           # no known place on either side... Toshkent is known, Buxoro is not
    "taksi kerak",                               # no place at all
    "salom",
])
async def test_detect_returns_none(idx, text):
    d = detect(text, idx, now=NOW)
    if text.startswith("Toshkent"):
        assert d is not None and d.from_place.name == "Toshkent" and d.to_place is None   # unknown side stays empty
    else:
        assert d is None
