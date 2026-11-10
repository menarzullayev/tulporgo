import httpx
import pytest
from tulporgo_api.telegram_api import TelegramUploader, UploadFailed
from tulporgo_core.events import DriverRegistered
from tulporgo_core.models import Driver

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"\x00" * 64
BODY = {"phone": "+998 90 123 45 67", "car_make": "Cobalt", "car_color": "oq", "car_plate": "30 A 123 BC", "seats": 4}


def register(env, H, tg=7, **over):
    return env.client.post("/api/driver", json={**BODY, **over}, headers=H(tg))


def files(**kw):
    return {k: (f"{k}.bin", v, "application/octet-stream") for k, v in kw.items()}


def stored(env, driver_id):
    async def go(s):
        d = await s.get(Driver, driver_id)
        return d.license_file_id, d.techpass_file_id, d.car_photo_file_id
    return env.db(go)


def test_register_driver(env, H):
    res = register(env, H)
    assert res.status_code == 201
    me = res.json()
    d = me["driver"]
    assert d["car_plate"] == "30A123BC" and d["status"] == "active" and d["verified"] is False
    assert d["subscription_active"] is True and d["has_documents"] is False
    assert me["phone_set"] is True and "998901234567" not in res.text
    assert me["referral_link"].startswith("https://t.me/tulporgobot?start=ref_")
    assert DriverRegistered(d["id"]) in env.bus.published
    assert env.client.get("/api/me", headers=H(7)).json()["driver"]["id"] == d["id"]


def test_register_uses_phone_already_on_file(env, H):
    env.make_user(7, phone="+998901234567")
    body = {k: v for k, v in BODY.items() if k != "phone"}
    assert env.client.post("/api/driver", json=body, headers=H(7)).status_code == 201


def test_register_needs_a_phone(env, H):
    body = {k: v for k, v in BODY.items() if k != "phone"}
    res = env.client.post("/api/driver", json=body, headers=H(7))
    assert res.status_code == 422 and res.json()["error"] == "phone_required"
    assert env.bus.published == []


@pytest.mark.parametrize("over,code", [({"phone": "12345"}, "bad_phone"), ({"phone": "+7 999 123 45 67"}, "bad_phone"),
                                       ({"car_plate": "ABC"}, None), ({"car_plate": "99 ZZ 999 99"}, "bad_plate"),
                                       ({"home_place_id": 9999}, "place_not_found")])
def test_register_rejects_bad_input(env, H, over, code):
    res = register(env, H, **over)
    assert res.status_code in (404, 422)
    if code:
        assert res.json()["error"] == code
    assert env.client.get("/api/me", headers=H(7)).json()["driver"] is None


@pytest.mark.parametrize("over", [{"seats": 0}, {"seats": 9}, {"car_make": ""}, {"car_color": "x"}])
def test_register_validates_fields(env, H, over):
    assert register(env, H, **over).status_code == 422


def test_register_twice_and_duplicate_plate(env, H):
    assert register(env, H).status_code == 201
    again = register(env, H)
    assert again.status_code == 409 and again.json()["error"] == "already_driver"
    plate = register(env, H, tg=8)
    assert plate.status_code == 409 and plate.json()["error"] == "plate_taken"


def test_register_requires_auth(env):
    assert env.client.post("/api/driver", json=BODY).status_code == 401


def test_register_links_referral_code(env, H):
    inviter = register(env, H, tg=7).json()["referral_link"].split("ref_")[1]
    res = register(env, H, tg=8, car_plate="30 A 456 BC", referral_code=f"ref_{inviter}")
    assert res.status_code == 201

    async def referred(s):
        from sqlalchemy import select
        from tulporgo_core.models import User
        return (await s.execute(select(User).where(User.tg_id == 8))).scalar_one().referred_by_id
    assert env.db(referred) is not None
    # an unknown code is ignored, never an error
    assert register(env, H, tg=9, car_plate="30 A 789 BC", referral_code="NOSUCH").status_code == 201


# ---- documents ----
def test_documents_are_forwarded_to_storage_chat_and_only_file_ids_are_kept(env, H, tmp_path):
    driver_id = register(env, H).json()["driver"]["id"]
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=PNG, car_photo=PDF))
    assert res.status_code == 200
    assert res.json()["driver"]["has_documents"] is True and res.json()["driver"]["has_photo"] is True
    assert stored(env, driver_id) == ("FILE-ID-1", "FILE-ID-2", "FILE-ID-3")
    calls = env.uploader.calls
    assert [c["chat_id"] for c in calls] == [env.settings.storage_chat_id] * 3
    assert [c["content_type"] for c in calls] == ["image/jpeg", "image/png", "application/pdf"]
    assert [c["filename"] for c in calls] == [f"license-{driver_id}.jpg", f"techpass-{driver_id}.png",
                                              f"car_photo-{driver_id}.pdf"]       # names come from sniffing, not the client
    assert all("998" not in c["caption"] for c in calls)                          # no personal data in captions
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == ["api.db"]       # nothing written to disk


def test_uploaded_documents_are_never_spooled_to_disk(env, H, monkeypatch):
    import tempfile

    from starlette import formparsers
    spools = []

    class Watching(tempfile.SpooledTemporaryFile):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            spools.append(self)

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", Watching)
    register(env, H)
    big = JPEG + b"\x00" * (3 * 1024 * 1024)                  # well above Starlette's default 1 MB spool limit
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=big, techpass=big))
    assert res.status_code == 200
    assert len(spools) == 2 and not any(sp._rolled for sp in spools)      # stayed in memory, never hit a temp file


def test_spool_watcher_would_catch_a_disk_spill(env, H, monkeypatch):
    """Control for the test above: with Starlette's stock 1 MB limit the same upload DOES roll over to disk."""
    import tempfile

    from starlette import formparsers
    spools = []

    class Watching(tempfile.SpooledTemporaryFile):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            spools.append(self)

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", Watching)
    monkeypatch.setattr(formparsers.MultiPartParser, "spool_max_size", 1024 * 1024)
    register(env, H)
    big = JPEG + b"\x00" * (3 * 1024 * 1024)
    env.client.post("/api/driver/documents", headers=H(7), files=files(license=big, techpass=big))
    assert any(sp._rolled for sp in spools)


def test_documents_without_car_photo(env, H):
    driver_id = register(env, H).json()["driver"]["id"]
    assert env.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=JPEG)).status_code == 200
    assert stored(env, driver_id) == ("FILE-ID-1", "FILE-ID-2", None)


def test_documents_require_a_driver_profile(env, H):
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=JPEG))
    assert res.status_code == 403 and res.json()["error"] == "not_a_driver"
    assert env.uploader.calls == []


def test_documents_require_auth(env):
    assert env.client.post("/api/driver/documents", files=files(license=JPEG, techpass=JPEG)).status_code == 401
    assert env.uploader.calls == []


def test_documents_both_files_required(env, H):
    driver_id = register(env, H).json()["driver"]["id"]
    for f in (files(license=JPEG), files(techpass=JPEG), files(car_photo=JPEG)):
        res = env.client.post("/api/driver/documents", headers=H(7), files=f)
        assert res.status_code == 422 and res.json()["error"] == "documents_required"
    assert env.uploader.calls == [] and stored(env, driver_id) == (None, None, None)


@pytest.mark.parametrize("junk", [b"just some text", b"", b"<html><script>alert(1)</script></html>", b"MZ\x90\x00exe"])
def test_documents_reject_non_image_content_whatever_the_name(env, H, junk):
    driver_id = register(env, H).json()["driver"]["id"]
    res = env.client.post("/api/driver/documents", headers=H(7), files={
        "license": ("license.jpg", junk, "image/jpeg"), "techpass": ("techpass.jpg", JPEG, "image/jpeg")})
    assert res.status_code == 422 and res.json()["error"] in ("bad_file_type", "documents_required")
    assert env.uploader.calls == [] and stored(env, driver_id) == (None, None, None)


def test_documents_reject_oversized_files(env, H):
    driver_id = register(env, H).json()["driver"]["id"]
    big = JPEG + b"\x00" * (8 * 1024 * 1024)
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=big, techpass=JPEG))
    assert res.status_code == 413 and res.json()["error"] == "file_too_large"
    assert env.uploader.calls == [] and stored(env, driver_id) == (None, None, None)


def test_upload_failure_stores_nothing(env, H):
    driver_id = register(env, H).json()["driver"]["id"]
    env.uploader.fail = True
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=JPEG))
    assert res.status_code == 502 and res.json()["error"] == "upload_failed"
    assert stored(env, driver_id) == (None, None, None)


def test_documents_need_a_configured_storage_chat(env, H):
    register(env, H)
    env.client.app.state.settings.storage_chat_id = None
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=JPEG))
    assert res.status_code == 503 and res.json()["error"] == "storage_not_configured"
    assert env.uploader.calls == []


# ---- the real uploader, against a mocked Bot API transport (no network) ----
async def test_uploader_returns_file_id_and_posts_multipart():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["body"] = str(request.url), request.content
        return httpx.Response(200, json={"ok": True, "result": {"document": {"file_id": "BQAD-xyz"}}})

    up = TelegramUploader("123:FAKE", transport=httpx.MockTransport(handler))
    assert await up.send_document(-100, "license.jpg", JPEG, "image/jpeg", "cap") == "BQAD-xyz"
    assert seen["url"] == "https://api.telegram.org/bot123:FAKE/sendDocument"
    assert b'name="chat_id"' in seen["body"] and b"-100" in seen["body"] and b'name="document"' in seen["body"]


@pytest.mark.parametrize("response", [
    httpx.Response(400, json={"ok": False, "description": "chat not found"}),
    httpx.Response(200, json={"ok": True, "result": {}}),
    httpx.Response(502, text="<html>bad gateway</html>"),
])
async def test_uploader_failure_never_leaks_the_token(response):
    up = TelegramUploader("123:SECRET-TOKEN", transport=httpx.MockTransport(lambda r: response))
    with pytest.raises(UploadFailed) as e:
        await up.send_document(-100, "a.jpg", JPEG, "image/jpeg")
    assert "SECRET-TOKEN" not in str(e.value) and "SECRET-TOKEN" not in repr(e.value.__cause__)


async def test_uploader_network_error_never_leaks_the_token():
    def boom(request):
        raise httpx.ConnectError("cannot reach " + str(request.url))

    up = TelegramUploader("123:SECRET-TOKEN", transport=httpx.MockTransport(boom))
    with pytest.raises(UploadFailed) as e:
        await up.send_document(-100, "a.jpg", JPEG, "image/jpeg")
    assert "SECRET-TOKEN" not in str(e.value) and e.value.__cause__ is None and e.value.__suppress_context__


# ---- driver's own offers ----
def test_driver_offers_list(env, flow, H):
    req = flow.request(1)
    d = env.make_driver(5, "30A555BC")
    o = flow.offer(req["id"], d, 42_000)
    items = env.client.get("/api/driver/offers", headers=H(5)).json()["items"]
    assert len(items) == 1 and items[0]["id"] == o and items[0]["price"] == 42_000
    assert items[0]["from_text"] == "Qo'shrabot" and items[0]["trip_id"] is None
    env.client.post(f"/api/offers/{o}/accept", headers=H(1))
    assert env.client.get("/api/driver/offers", headers=H(5)).json()["items"][0]["trip_id"] is not None


def test_driver_offers_only_for_drivers_and_only_own(env, flow, H):
    req = flow.request(1)
    flow.offer(req["id"], env.make_driver(5, "30A555BC"), 42_000)
    res = env.client.get("/api/driver/offers", headers=H(1))
    assert res.status_code == 403 and res.json()["error"] == "not_a_driver"
    other = env.make_driver(6, "30A666BC")
    assert other and env.client.get("/api/driver/offers", headers=H(6)).json()["items"] == []
