"""Mini App API for the group feed (decision 73): CRUD of the driver's own filters with validation; negatives for
someone else's filter, groups he did not select, unknown places, bad times and the filter limit."""
import pytest
from test_userbot_api import make_api  # noqa: F401 - fixture
from tulporgo_core.models import Place
from userbot_fixtures import *  # noqa: F403
from userbot_helpers import make_account, make_driver


@pytest.fixture
async def places(s):
    a, b = Place(kind="district", name_uz="Qo'shrabot"), Place(kind="city", name_uz="Samarqand")
    s.add_all([a, b])
    await s.commit()
    return a, b


async def driver_api(s, settings, make_api):  # noqa: F811 - the fixture is passed in
    d = await make_driver(s, settings)
    await make_account(s, settings, d, groups=2)                # taxi groups -1001, -1002 selected
    return d, await make_api(settings, d.user.tg_id)


def body(places, **kw):
    b = {"name": "Kechki", "routes": [{"from": places[0].id, "to": places[1].id}], "time_from": "18:00",
         "time_to": "20:00", "weekdays": [0, 1, 2, 3, 4], "kinds": ["passenger", "parcel"], "group_chat_ids": [-1001]}
    b.update(kw)
    return b


async def test_state_and_crud(s, settings, make_api, factory, places):  # noqa: F811
    _, api = await driver_api(s, settings, make_api)
    r = await api("GET", "/feed")
    st = r.json()
    assert r.status_code == 200 and st["filters"] == [] and st["consent_ok"] is True and len(st["groups"]) == 2
    r = await api("POST", "/feed/filters", body(places))
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["routes"][0]["from"]["name"] == "Qo'shrabot" and f["kinds"] == ["parcel", "passenger"]
    r = await api("PUT", f"/feed/filters/{f['id']}", body(places, name="Ertalab", enabled=False))
    assert r.json()["name"] == "Ertalab" and r.json()["enabled"] is False
    assert (await api("POST", "/feed/pause", {"paused": True})).json()["paused"] is True
    assert (await api("DELETE", f"/feed/filters/{f['id']}")).status_code == 200
    assert (await api("GET", "/feed")).json()["filters"] == []


@pytest.mark.parametrize("bad,code", [
    ({"time_from": "25:00"}, "bad_time"),
    ({"weekdays": [7]}, "bad_weekday"),
    ({"seats_min": 4, "seats_max": 2}, "bad_seats"),
    ({"routes": [{"from": 999999, "to": None}]}, "unknown_place"),
    ({"routes": [{"from": None, "to": None}]}, "empty_route"),
    ({"group_chat_ids": [-1009999]}, "not_your_group"),
])
async def test_validation(s, settings, make_api, factory, places, bad, code):  # noqa: F811
    _, api = await driver_api(s, settings, make_api)
    r = await api("POST", "/feed/filters", body(places, **bad))
    assert r.status_code == 422 and r.json()["error"] == code


async def test_someone_elses_filter_is_not_found(s, settings, make_api, factory, places):  # noqa: F811
    _, owner = await driver_api(s, settings, make_api)
    fid = (await owner("POST", "/feed/filters", body(places))).json()["id"]
    _, other = await driver_api(s, settings, make_api)
    assert (await other("PUT", f"/feed/filters/{fid}", body(places))).status_code == 404     # negative
    assert (await other("DELETE", f"/feed/filters/{fid}")).status_code == 404
    assert len((await owner("GET", "/feed")).json()["filters"]) == 1


async def test_filter_limit(s, settings, make_api, factory, places, monkeypatch):  # noqa: F811
    from tulporgo_userbot import feedapi
    monkeypatch.setattr(feedapi, "MAX_FILTERS", 2)
    _, api = await driver_api(s, settings, make_api)
    for _ in range(2):
        assert (await api("POST", "/feed/filters", body(places))).status_code == 200
    r = await api("POST", "/feed/filters", body(places))
    assert r.status_code == 422 and r.json()["error"] == "too_many_filters"


async def test_requires_auth(s, settings, make_api, factory):  # noqa: F811
    _, api = await driver_api(s, settings, make_api)
    assert (await api("GET", "/feed", auth=False)).status_code == 401
