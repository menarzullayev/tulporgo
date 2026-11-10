import json

import pytest
from tulporgo_core.events import RequestClosed, RequestCreated, TripCompleted

pytest_plugins = ["api_fixtures"]  # shared fixtures; a file named conftest.py would shadow the core one

SHARE_KEYS = {"status", "finished", "from", "to", "depart_at", "driver_first_name", "car"}


def test_trips_mine_for_both_roles(env, flow, H):
    t = flow.trip()
    p = env.client.get("/api/trips/mine", headers=H(1)).json()["items"]
    d = env.client.get("/api/trips/mine", headers=H(2)).json()["items"]
    assert [x["id"] for x in p] == [x["id"] for x in d] == [t["trip"]["id"]]
    assert (p[0]["role"], d[0]["role"]) == ("passenger", "driver")
    assert env.client.get("/api/trips/mine", headers=H(3)).json()["items"] == []           # strangers see nothing


def test_contact_details_only_go_to_the_counterparty(env, flow, H):
    env.make_user(1, phone="+998900000000", first_name="Aziza", username="aziza_u")
    t = flow.trip()
    seen_by_passenger = env.client.get(f"/api/trips/{t['trip']['id']}", headers=H(1)).json()["counterparty"]
    seen_by_driver = env.client.get(f"/api/trips/{t['trip']['id']}", headers=H(2)).json()["counterparty"]
    assert seen_by_passenger["phone"] == "+998901234567" and seen_by_passenger["first_name"] == "Bobur"
    assert seen_by_driver["phone"] == "+998900000000" and seen_by_driver["username"] == "aziza_u"


def test_stranger_cannot_read_or_change_a_trip(env, flow, H):
    tid = flow.trip()["trip"]["id"]
    assert env.client.get(f"/api/trips/{tid}", headers=H(3)).json()["error"] == "not_your_trip"
    for action in ("complete", "cancel", "start"):
        res = env.client.post(f"/api/trips/{tid}/{action}", headers=H(3))
        assert res.status_code == 403, action
    assert env.client.get("/api/trips/9999", headers=H(1)).status_code == 404
    assert env.client.get(f"/api/trips/{tid}", headers=H(1)).json()["status"] == "confirmed"
    env.client.post(f"/api/trips/{tid}/complete", headers=H(1))
    res = env.client.post(f"/api/trips/{tid}/rate", json={"stars": 5}, headers=H(3))        # stranger rates a finished trip
    assert res.status_code == 403 and res.json()["error"] == "not_your_trip"


def test_only_the_driver_starts_a_trip(env, flow, H):
    tid = flow.trip()["trip"]["id"]
    assert env.client.post(f"/api/trips/{tid}/start", headers=H(1)).json()["error"] == "driver_only"
    res = env.client.post(f"/api/trips/{tid}/start", headers=H(2))
    assert res.status_code == 200 and res.json()["status"] == "started" and res.json()["role"] == "driver"
    assert env.client.post(f"/api/trips/{tid}/start", headers=H(2)).status_code == 409


def test_complete_trip_and_event(env, flow, H):
    tid = flow.trip()["trip"]["id"]
    res = env.client.post(f"/api/trips/{tid}/complete", headers=H(1))
    assert res.status_code == 200 and res.json()["status"] == "completed" and res.json()["completed_at"]
    assert TripCompleted(tid) in env.bus.published
    assert env.client.post(f"/api/trips/{tid}/complete", headers=H(1)).json()["error"] == "trip_not_active"
    assert env.client.post(f"/api/trips/{tid}/cancel", headers=H(1)).status_code == 409


def test_passenger_cancel_closes_request_driver_cancel_reopens_it(env, flow, H):
    a = flow.trip(1, 2, "30A111BC")
    assert env.client.post(f"/api/trips/{a['trip']['id']}/cancel", headers=H(1)).json()["status"] == "cancelled"
    assert RequestClosed(a["request"]["id"], "cancelled") in env.bus.published
    b = flow.trip(3, 4, "30A222BC")
    assert env.client.post(f"/api/trips/{b['trip']['id']}/cancel", headers=H(4)).json()["status"] == "cancelled"
    assert RequestCreated(b["request"]["id"]) in env.bus.published[-1:]                    # other drivers may offer again
    reopened = env.client.get("/api/requests/mine", headers=H(3)).json()["items"][0]
    assert reopened["status"] == "open"


def test_cannot_cancel_a_started_trip(env, flow, H):
    tid = flow.trip()["trip"]["id"]
    env.client.post(f"/api/trips/{tid}/start", headers=H(2))
    assert env.client.post(f"/api/trips/{tid}/cancel", headers=H(1)).json()["error"] == "trip_not_cancellable"


def test_rate_driver_updates_rating_once(env, flow, H):
    tid = flow.trip()["trip"]["id"]
    env.client.post(f"/api/trips/{tid}/complete", headers=H(1))
    res = env.client.post(f"/api/trips/{tid}/rate", json={"stars": 5, "comment": "Zo'r haydovchi"}, headers=H(1))
    assert res.status_code == 200 and res.json() == {"ok": True, "stars": 5}
    assert env.client.get(f"/api/trips/{tid}", headers=H(1)).json()["rated"] is True
    assert env.client.get(f"/api/trips/{tid}", headers=H(1)).json()["driver_rating"] == 5.0
    dup = env.client.post(f"/api/trips/{tid}/rate", json={"stars": 1}, headers=H(1))
    assert dup.status_code == 409 and dup.json()["error"] == "already_rated"
    assert env.client.get(f"/api/trips/{tid}", headers=H(1)).json()["driver_rating"] == 5.0   # unchanged


def test_rating_negative_cases(env, flow, H):
    tid = flow.trip()["trip"]["id"]
    early = env.client.post(f"/api/trips/{tid}/rate", json={"stars": 5}, headers=H(1))
    assert early.status_code == 409 and early.json()["error"] == "trip_not_completed"
    env.client.post(f"/api/trips/{tid}/complete", headers=H(1))
    for bad in ({"stars": 0}, {"stars": 6}, {"stars": "five"}, {}, {"stars": 5, "comment": "x" * 600}):
        assert env.client.post(f"/api/trips/{tid}/rate", json=bad, headers=H(1)).status_code == 422
    assert env.client.get(f"/api/trips/{tid}", headers=H(1)).json()["rated"] is False


# ---- public share page (decision 13) ----
def test_share_page_needs_no_auth_and_shows_only_the_whitelist(env, flow):
    t = flow.trip()
    res = env.client.get(f"/api/share/{t['trip']['share_token']}")                          # no Authorization header
    assert res.status_code == 200
    body = res.json()
    assert set(body) == SHARE_KEYS
    assert body["status"] == "confirmed" and body["finished"] is False
    assert (body["from"], body["to"]) == ("Qo'shrabot", "Samarqand shahri")
    assert body["driver_first_name"] == "Bobur"
    assert body["car"] == {"make": "Cobalt", "color": "oq", "plate": "30A123BC"}
    assert res.headers["cache-control"] == "no-store" and "noindex" in res.headers["x-robots-tag"]


def test_share_page_leaks_no_phone_or_personal_data(env, flow):
    env.make_user(1, phone="+998905555555", first_name="Malika", username="malika_secret")
    t = flow.trip(price=48_500)
    # also give the driver a username so a leak of it would be visible
    env.db(lambda s: _set_username(s, t["driver_tg"], "bobur_secret"))
    raw = env.client.get(f"/api/share/{t['trip']['share_token']}").text
    for forbidden in ("998905555555", "905555555", "+998901234567", "901234567", "malika_secret", "bobur_secret",
                      "Malika", "phone", "username", "tg_id", "price", "48500", "48_500"):
        assert forbidden not in raw, forbidden
    assert "Bobur" in raw                                                                  # the first name is allowed
    assert json.loads(raw).keys() == SHARE_KEYS


async def _set_username(s, tg_id, username):
    from sqlalchemy import select
    from tulporgo_core.models import User
    (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one().username = username


def test_share_page_follows_trip_status(env, flow, H):
    t = flow.trip()
    tok = t["trip"]["share_token"]
    env.client.post(f"/api/trips/{t['trip']['id']}/start", headers=H(2))
    assert env.client.get(f"/api/share/{tok}").json()["status"] == "started"
    env.client.post(f"/api/trips/{t['trip']['id']}/complete", headers=H(1))
    body = env.client.get(f"/api/share/{tok}").json()
    assert body["status"] == "completed" and body["finished"] is True


@pytest.mark.parametrize("token", ["doesnotexist1234", "AAAAAAAAAAAAAAAA"])
def test_share_unknown_token_is_404(env, token):
    res = env.client.get(f"/api/share/{token}")
    assert res.status_code == 404 and res.json()["error"] == "trip_not_found"


@pytest.mark.parametrize("token", ["short", "has space in it", "a" * 65, "../../etc/passwd", "x%27%20OR%201=1"])
def test_share_malformed_token_is_rejected(env, token):
    assert env.client.get(f"/api/share/{token}").status_code in (404, 422)


def test_share_cannot_be_guessed_from_trip_id(env, flow):
    t = flow.trip()
    assert env.client.get(f"/api/share/{t['trip']['id']}").status_code in (404, 422)


def test_trip_share_url_points_at_the_hash_route(env, flow):
    t = flow.trip()
    assert t["trip"]["share_url"] == f"https://tulporgo.uz/app/#/share/{t['trip']['share_token']}"
