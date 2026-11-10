from datetime import timedelta

from tulporgo_core.db import utcnow
from tulporgo_core.events import OfferAccepted, OfferCountered, RequestClosed, RequestCreated
from tulporgo_core.models import RideRequest

pytest_plugins = ["api_fixtures"]  # shared fixtures; a file named conftest.py would shadow the core one


def test_create_request_from_place_ids(env, H):
    res = env.client.post("/api/requests", json={"from_place_id": 3, "to_place_id": 4, "seats": 2, "note": "2 ta sumka"},
                          headers=H(1))
    assert res.status_code == 201
    r = res.json()
    assert (r["from_text"], r["to_text"]) == ("Qo'shrabot", "Samarqand shahri")     # texts filled from the places
    assert r["status"] == "open" and r["seats"] == 2 and r["note"] == "2 ta sumka" and r["women_only"] is False
    assert r["depart_at"] is None


def test_create_request_publishes_event_only_after_commit(env, H):
    seen = []

    async def handler(event):                     # a bot process would read the request when the event arrives
        maker = env.client.app.state.maker
        async with maker() as s:
            seen.append(await s.get(RideRequest, event.request_id))

    env.bus.subscribe(RequestCreated, handler)
    r = env.client.post("/api/requests", json={"from_text": "Qovunchi", "to_text": "Samarqand"}, headers=H(1)).json()
    assert env.bus.published == [RequestCreated(r["id"])]
    assert seen and seen[0] is not None and seen[0].source == "miniapp"        # visible: the commit came first


def test_failed_request_publishes_nothing(env, H):
    env.client.post("/api/requests", json={"from_text": " ", "to_text": "Samarqand"}, headers=H(1))
    assert env.bus.published == []


def test_depart_at_is_tashkent_time_by_default(env, H):
    r = env.client.post("/api/requests", json={"from_place_id": 3, "to_place_id": 4,
                                               "depart_at": "2099-01-01T07:30"}, headers=H(1)).json()
    assert r["depart_at"] == "2099-01-01T07:30+05:00"

    async def stored(s):
        return (await s.get(RideRequest, r["id"])).depart_at
    assert env.db(stored).isoformat() == "2099-01-01T02:30:00"                    # naive UTC in the database


def test_depart_at_with_explicit_offset_is_converted(env, H):
    r = env.client.post("/api/requests", json={"from_place_id": 3, "to_place_id": 4,
                                               "depart_at": "2099-01-01T07:30:00+00:00"}, headers=H(1)).json()
    assert r["depart_at"] == "2099-01-01T12:30+05:00"


def test_request_validation_failures(env, H):
    post = lambda **b: env.client.post("/api/requests", json=b, headers=H(1))   # noqa: E731
    past = (utcnow() - timedelta(hours=2)).isoformat()
    assert post(from_place_id=3, to_place_id=4, depart_at=past).json()["error"] == "depart_in_past"
    assert post(from_place_id=3, to_place_id=3).json()["error"] == "same_place"
    assert post(from_text="", to_text="Samarqand").json()["error"] == "route_required"
    assert post(from_place_id=999, to_place_id=4).json()["error"] == "place_not_found"
    assert post(from_place_id=3, to_place_id=4, seats=9).status_code == 422
    assert post(from_place_id=3, to_place_id=4, seats=0).status_code == 422
    assert post(from_place_id=3, to_place_id=4, depart_at="not a date").status_code == 422
    assert post(from_place_id=3, to_place_id=4, note="x" * 300).status_code == 422
    assert env.client.get("/api/requests/mine", headers=H(1)).json()["items"] == []


def test_request_needs_auth(env):
    assert env.client.post("/api/requests", json={"from_place_id": 3, "to_place_id": 4}).status_code == 401


def test_woman_marker_is_copied_onto_the_request(env, H):
    env.make_user(1, is_woman=True)
    assert env.client.post("/api/requests", json={"from_place_id": 3, "to_place_id": 4},
                           headers=H(1)).json()["women_only"] is True


def test_too_many_open_requests(env, flow, H):
    for _ in range(3):
        flow.request(1)
    res = env.client.post("/api/requests", json={"from_place_id": 3, "to_place_id": 4}, headers=H(1))
    assert res.status_code == 409 and res.json()["error"] == "too_many_open_requests"


def test_my_requests_lists_only_own_with_offer_counts(env, flow, H):
    mine, other = flow.request(1), flow.request(2)
    d = env.make_driver(5, "30A555BC")
    flow.offer(mine["id"], d, 40_000)
    items = env.client.get("/api/requests/mine", headers=H(1)).json()["items"]
    assert [i["id"] for i in items] == [mine["id"]] and items[0]["offers_count"] == 1
    assert other["id"] not in [i["id"] for i in items]


def test_cancel_request(env, flow, H):
    r = flow.request(1)
    res = env.client.post(f"/api/requests/{r['id']}/cancel", headers=H(1))
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert RequestClosed(r["id"], "cancelled") in env.bus.published


def test_cancel_someone_elses_request_is_forbidden(env, flow, H):
    r = flow.request(1)
    res = env.client.post(f"/api/requests/{r['id']}/cancel", headers=H(2))
    assert res.status_code == 403 and res.json()["error"] == "not_your_request"
    assert env.client.get("/api/requests/mine", headers=H(1)).json()["items"][0]["status"] == "open"


def test_cancel_twice_and_unknown_request(env, flow, H):
    r = flow.request(1)
    env.client.post(f"/api/requests/{r['id']}/cancel", headers=H(1))
    assert env.client.post(f"/api/requests/{r['id']}/cancel", headers=H(1)).json()["error"] == "request_not_open"
    assert env.client.post("/api/requests/9999/cancel", headers=H(1)).status_code == 404


# ---- offers ----
def test_offers_list_shows_price_car_and_rating_but_no_contact_data(env, flow, H):
    r = flow.request(1)
    d = env.make_driver(5, "30A555BC", first_name="Sardor", rating_sum=9, rating_count=2)
    flow.offer(r["id"], d, 45_000)
    res = env.client.get(f"/api/requests/{r['id']}/offers", headers=H(1))
    body = res.json()
    offer = body["offers"][0]
    assert offer["price"] == 45_000 and offer["status"] == "sent"
    assert offer["driver"] == {"first_name": "Sardor", "car_make": "Cobalt", "car_color": "oq", "rating": 4.5,
                               "rating_count": 2, "verified": False}
    assert "998901234567" not in res.text and "30A555BC" not in res.text      # no phone, no plate before the trip
    assert body["trip_id"] is None and body["request"]["offers_count"] == 1


def test_offers_sorted_by_price_and_withdrawn_offers_hidden(env, flow, H):
    r = flow.request(1)
    d1, d2 = env.make_driver(5, "30A555BC"), env.make_driver(6, "30A666BC")
    flow.offer(r["id"], d1, 60_000)
    o2 = flow.offer(r["id"], d2, 40_000)
    assert [o["price"] for o in env.client.get(f"/api/requests/{r['id']}/offers", headers=H(1)).json()["offers"]] \
        == [40_000, 60_000]
    from tulporgo_core.models import Driver, Offer
    from tulporgo_core.services import rides

    async def withdraw(s):
        await rides.withdraw_offer(s, await s.get(Driver, d2), await s.get(Offer, o2))
    env.db(withdraw)
    assert [o["price"] for o in env.client.get(f"/api/requests/{r['id']}/offers", headers=H(1)).json()["offers"]] \
        == [60_000]


def test_offers_of_someone_elses_request_are_forbidden(env, flow, H):
    r = flow.request(1)
    flow.offer(r["id"], env.make_driver(5, "30A555BC"))
    res = env.client.get(f"/api/requests/{r['id']}/offers", headers=H(2))
    assert res.status_code == 403 and res.json()["error"] == "not_your_request"
    assert env.client.get("/api/requests/9999/offers", headers=H(1)).status_code == 404


def test_accept_offer_creates_trip_and_publishes(env, flow, H):
    t = flow.trip()
    trip = t["trip"]
    assert trip["status"] == "confirmed" and trip["price"] == 50_000 and trip["role"] == "passenger"
    assert trip["car"]["plate"] == "30A123BC" and trip["share_token"] and trip["rated"] is False
    assert OfferAccepted(t["offer_id"], trip["id"]) in env.bus.published
    again = env.client.post(f"/api/offers/{t['offer_id']}/accept", headers=H(1))
    assert again.status_code == 409                                                      # no second trip
    assert env.client.get(f"/api/requests/{t['request']['id']}/offers", headers=H(1)).json()["trip_id"] == trip["id"]


def test_accept_someone_elses_offer_is_forbidden(env, flow, H):
    r = flow.request(1)
    o = flow.offer(r["id"], env.make_driver(5, "30A555BC"))
    res = env.client.post(f"/api/offers/{o}/accept", headers=H(2))
    assert res.status_code == 403 and res.json()["error"] == "not_your_request"
    assert env.client.get("/api/trips/mine", headers=H(1)).json()["items"] == []


def test_accept_after_request_was_cancelled_and_unknown_offer(env, flow, H):
    r = flow.request(1)
    o = flow.offer(r["id"], env.make_driver(5, "30A555BC"))
    env.client.post(f"/api/requests/{r['id']}/cancel", headers=H(1))
    assert env.client.post(f"/api/offers/{o}/accept", headers=H(1)).status_code == 409
    assert env.client.post("/api/offers/9999/accept", headers=H(1)).json()["error"] == "offer_not_found"


def test_only_one_of_several_offers_can_win(env, flow, H):
    r = flow.request(1)
    o1 = flow.offer(r["id"], env.make_driver(5, "30A555BC"), 50_000)
    o2 = flow.offer(r["id"], env.make_driver(6, "30A666BC"), 55_000)
    assert env.client.post(f"/api/offers/{o1}/accept", headers=H(1)).status_code == 200
    assert env.client.post(f"/api/offers/{o2}/accept", headers=H(1)).status_code == 409


def test_counter_offer_flow(env, flow, H):
    r = flow.request(1)
    o = flow.offer(r["id"], env.make_driver(5, "30A555BC"), 50_000)
    res = env.client.post(f"/api/offers/{o}/counter", json={"price": 40_000}, headers=H(1))
    assert res.status_code == 200 and res.json()["status"] == "countered" and res.json()["counter_price"] == 40_000
    assert OfferCountered(o, 40_000) in env.bus.published
    listed = env.client.get(f"/api/requests/{r['id']}/offers", headers=H(1)).json()["offers"]
    assert listed[0]["status"] == "countered"                                           # still visible while countered


def test_counter_must_be_lower_than_the_offer(env, flow, H):
    r = flow.request(1)
    o = flow.offer(r["id"], env.make_driver(5, "30A555BC"), 50_000)
    for price in (50_000, 60_000, 500):
        res = env.client.post(f"/api/offers/{o}/counter", json={"price": price}, headers=H(1))
        assert res.status_code == 422 and res.json()["error"] == "counter_must_be_lower"
    assert env.client.post(f"/api/offers/{o}/counter", json={"price": 0}, headers=H(1)).status_code == 422
    assert env.client.post(f"/api/offers/{o}/counter", json={}, headers=H(1)).status_code == 422
    assert not [e for e in env.bus.published if isinstance(e, OfferCountered)]


def test_counter_by_someone_else_or_on_closed_offer(env, flow, H):
    r = flow.request(1)
    o = flow.offer(r["id"], env.make_driver(5, "30A555BC"), 50_000)
    assert env.client.post(f"/api/offers/{o}/counter", json={"price": 40_000}, headers=H(2)).status_code == 403
    env.client.post(f"/api/offers/{o}/accept", headers=H(1))
    assert env.client.post(f"/api/offers/{o}/counter", json={"price": 40_000}, headers=H(1)).status_code == 409
    assert env.client.post("/api/offers/9999/counter", json={"price": 40_000}, headers=H(1)).status_code == 404
