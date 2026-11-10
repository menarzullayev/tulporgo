import pytest

pytest_plugins = ["api_fixtures"]  # shared fixtures; a file named conftest.py would shadow the core one


def test_me_creates_profile_without_phone_or_driver(env, H):
    res = env.client.get("/api/me", headers=H(10, first_name="Ali", username="ali_u", lang="ru"))
    assert res.status_code == 200
    me = res.json()
    assert me["first_name"] == "Ali" and me["driver"] is None and me["phone_set"] is False
    assert me["referral_link"] is None and me["free_period"] is True


def test_me_never_exposes_phone_number(env, H):
    env.make_user(10, phone="+998901234567")
    res = env.client.get("/api/me", headers=H(10))
    assert res.json()["phone_set"] is True
    assert "998901234567" not in res.text


@pytest.mark.parametrize("path,method", [("/api/me", "get"), ("/api/me", "patch"), ("/api/plans", "get"),
                                         ("/api/places", "get"), ("/api/requests/mine", "get"),
                                         ("/api/trips/mine", "get"), ("/api/driver/offers", "get")])
def test_authenticated_routes_reject_missing_auth(env, path, method):
    res = getattr(env.client, method)(path)
    assert res.status_code == 401


def test_forged_and_expired_auth_rejected(env, sign):
    c = env.client
    forged = sign(10, token="999:OTHER-TOKEN")
    assert c.get("/api/me", headers={"Authorization": f"tma {forged}"}).status_code == 401
    expired = sign(10, age=25 * 3600)
    assert c.get("/api/me", headers={"Authorization": f"tma {expired}"}).status_code == 401
    assert c.get("/api/me", headers={"Authorization": f"Bearer {sign(10)}"}).status_code == 401


def test_blocked_user_is_refused(env, H):
    env.make_user(10, is_blocked=True)
    assert env.client.get("/api/me", headers=H(10)).status_code == 403


def test_patch_me_updates_language_and_marker(env, H):
    res = env.client.patch("/api/me", json={"lang": "ru", "is_woman": True}, headers=H(10))
    assert res.status_code == 200 and res.json()["lang"] == "ru" and res.json()["is_woman"] is True
    # a partial patch keeps the other field
    res = env.client.patch("/api/me", json={"lang": "uz_cyrl"}, headers=H(10))
    assert res.json()["lang"] == "uz_cyrl" and res.json()["is_woman"] is True


def test_patch_me_rejects_unknown_language(env, H):
    res = env.client.patch("/api/me", json={"lang": "klingon"}, headers=H(10))
    assert res.status_code == 422 and res.json()["error"] == "bad_lang"
    assert env.client.get("/api/me", headers=H(10)).json()["lang"] != "klingon"


def test_plans_come_from_core_billing(env, H):
    res = env.client.get("/api/plans", headers=H(10)).json()
    prices = {p["plan"]: p["price_uzs"] for p in res["plans"]}
    assert prices == {"basic": 29_000, "pro": 59_000, "business": 99_000}     # decision 10
    assert res["free_period"] is True and res["trial_days"] == 7


# ---- places ----
def test_search_finds_every_spelling(env, H):
    for q in ("koshrabad", "Qo'shrabot", "qushrabot"):
        names = [p["name"] for p in env.client.get("/api/places", params={"q": q}, headers=H(10)).json()["items"]]
        assert "Qo'shrabot" in names, q
    items = env.client.get("/api/places", params={"q": "Самарканд"}, headers=H(10)).json()["items"]
    assert items and items[0]["name"] == "Samarqand shahri" and items[0]["parent"] == "Samarqand viloyati"


def test_search_without_query_returns_popular_places_first(env, H):
    items = env.client.get("/api/places", headers=H(10)).json()["items"]
    assert [p["name"] for p in items][:2] == ["Samarqand shahri", "Qo'shrabot"]
    assert all(p["kind"] in ("city", "district", "poi") for p in items)


def test_search_no_match_and_overlong_query(env, H):
    assert env.client.get("/api/places", params={"q": "zzzzzzzz"}, headers=H(10)).json() == {"items": []}
    assert env.client.get("/api/places", params={"q": "a" * 65}, headers=H(10)).status_code == 422


def test_place_index_is_cached_on_app_state_and_rebuildable(env, H):
    from tulporgo_api.routes.places import invalidate_place_index
    env.client.get("/api/places", params={"q": "samarqand"}, headers=H(10))
    app = env.client.app
    first = app.state.place_index
    env.client.get("/api/places", params={"q": "samarqand"}, headers=H(10))
    assert app.state.place_index is first                  # served from the cache
    invalidate_place_index(app)
    env.client.get("/api/places", params={"q": "samarqand"}, headers=H(10))
    assert app.state.place_index is not first              # rebuilt on demand


def test_children_and_roots(env, H):
    kids = env.client.get("/api/places/2/children", headers=H(10)).json()["items"]
    assert {p["name"] for p in kids} == {"Qo'shrabot", "Samarqand shahri", "Oqtepa"}
    assert [p["name"] for p in env.client.get("/api/places/roots", headers=H(10)).json()["items"]] == ["O'zbekiston"]
    assert env.client.get("/api/places/5/children", headers=H(10)).json() == {"items": []}


def test_children_of_unknown_place_is_404(env, H):
    res = env.client.get("/api/places/99999/children", headers=H(10))
    assert res.status_code == 404 and res.json()["error"] == "place_not_found"


def test_nearest_snaps_to_closest_known_place(env, H):
    res = env.client.get("/api/places/nearest", params={"lat": 39.66, "lon": 66.97}, headers=H(10)).json()
    assert res["item"]["name"] == "Samarqand shahri" and res["distance_km"] < 5


def test_nearest_far_from_anything_is_404_and_bad_coordinates_422(env, H):
    far = env.client.get("/api/places/nearest", params={"lat": 41.3, "lon": 69.2}, headers=H(10))   # Tashkent
    assert far.status_code == 404 and far.json()["error"] == "place_not_found"
    assert env.client.get("/api/places/nearest", params={"lat": 91, "lon": 0}, headers=H(10)).status_code == 422
