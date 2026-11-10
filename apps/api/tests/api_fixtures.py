"""API test fixtures: a FastAPI app on a temporary SQLite file, signed Mini App initData, a fake Telegram uploader.
No network and no real bot token are used anywhere."""
import asyncio
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from datetime import date, timedelta
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from tulporgo_api.main import create_app
from tulporgo_api.routes.driver import get_uploader
from tulporgo_core.config import Settings
from tulporgo_core.db import Base, make_engine, make_sessionmaker
from tulporgo_core.events import InMemoryBus
from tulporgo_core.models import Place
from tulporgo_core.services import drivers, users

TOKEN = "123456:TEST-TOKEN-NOT-REAL"
STORAGE_CHAT = -1001234567890


def sign_init_data(user_id: int, first_name: str = "Ali", username: str | None = None, token: str = TOKEN,
                   age: int = 0, lang: str = "uz") -> str:
    user = {"id": user_id, "first_name": first_name, "language_code": lang}
    if username:
        user["username"] = username
    fields = {"auth_date": str(int(time.time()) - age), "query_id": "AAE-test", "user": json.dumps(user)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


def auth(user_id: int, **kw) -> dict:
    return {"Authorization": f"tma {sign_init_data(user_id, **kw)}"}


class FakeUploader:
    """Stands in for the Bot API: records uploads and returns deterministic file ids."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.fail = False

    async def send_document(self, chat_id, filename, content, content_type, caption=""):
        if self.fail:
            from tulporgo_api.telegram_api import UploadFailed
            raise UploadFailed("upload_failed")
        self.calls.append({"chat_id": chat_id, "filename": filename, "size": len(content),
                           "content_type": content_type, "caption": caption})
        return f"FILE-ID-{len(self.calls)}"


class Env:
    """Bundle handed to tests: HTTP client, in-memory bus, uploader and DB helpers."""

    def __init__(self, client: TestClient, bus: InMemoryBus, uploader: FakeUploader, url: str, settings: Settings):
        self.client, self.bus, self.uploader, self.url, self.settings = client, bus, uploader, url, settings

    def db(self, fn: Callable):
        """Run `async fn(session)` against the test database (own engine, committed) and return its result."""
        async def run():
            eng = make_engine(self.url)
            try:
                async with make_sessionmaker(eng)() as s:
                    result = await fn(s)
                    await s.commit()
                    return result
            finally:
                await eng.dispose()
        return asyncio.run(run())

    def make_user(self, tg_id: int, **attrs) -> int:
        async def go(s):
            u = await users.get_or_create_user(s, tg_id, attrs.pop("username", None), attrs.pop("first_name", "Test"))
            for k, v in attrs.items():
                setattr(u, k, v)
            return u.id
        return self.db(go)

    def make_driver(self, tg_id: int, plate: str, first_name: str = "Bobur", **attrs) -> int:
        async def go(s):
            u = await users.get_or_create_user(s, tg_id, None, first_name)
            u.phone = "+998901234567"
            d = await drivers.register_driver(s, u, self.settings, car_make="Cobalt", car_color="oq", car_plate=plate)
            for k, v in attrs.items():
                setattr(d, k, v)
            return d.id
        return self.db(go)


@pytest.fixture
def env(tmp_path):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'api.db').as_posix()}"
    settings = Settings(database_url=url, bot_token=TOKEN, storage_chat_id=STORAGE_CHAT,
                        free_period_until=date.today() + timedelta(days=30), trial_days=7)

    async def setup():
        eng = make_engine(url)
        async with eng.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        async with make_sessionmaker(eng)() as s:
            country = Place(kind="country", name_uz="O'zbekiston")
            s.add(country)
            await s.flush()
            region = Place(kind="region", name_uz="Samarqand viloyati", parent_id=country.id)
            s.add(region)
            await s.flush()
            s.add_all([
                Place(kind="district", name_uz="Qo'shrabot", parent_id=region.id, aliases=["koshrabad"], popularity=90,
                      lat=39.8, lon=66.6),
                Place(kind="city", name_uz="Samarqand shahri", name_ru="Самарканд", parent_id=region.id,
                      aliases=["Samarqand"], popularity=100, lat=39.65, lon=66.96),
                Place(kind="mahalla", name_uz="Oqtepa", parent_id=region.id),
            ])
            await s.commit()
        await eng.dispose()

    asyncio.run(setup())
    bus, uploader = InMemoryBus(), FakeUploader()
    engine = make_engine(url)
    app = create_app(settings, maker=make_sessionmaker(engine), bus=bus)
    app.dependency_overrides[get_uploader] = lambda: uploader
    with TestClient(app) as client:
        yield Env(client, bus, uploader, url, settings)
        # close pooled aiosqlite connections on the client's own loop; otherwise their worker threads call back into
        # a closed loop after the test ("Event loop is closed", seen as an error annotation in CI)
        client.portal.call(engine.dispose)


class Flow:
    """Scenario helpers on top of Env: build requests, offers and trips through the real API/services."""

    def __init__(self, env: Env):
        self.env = env

    def request(self, tg_id: int, **over) -> dict:
        body = {"from_place_id": 3, "to_place_id": 4, "seats": 1, **over}
        res = self.env.client.post("/api/requests", json=body, headers=auth(tg_id))
        assert res.status_code == 201, res.text
        return res.json()

    def offer(self, request_id: int, driver_id: int, price: int = 50_000) -> int:
        from tulporgo_core.models import Driver
        from tulporgo_core.services import rides

        async def go(s):
            r = await rides.get_request(s, request_id)
            d = await s.get(Driver, driver_id)
            return (await rides.send_offer(s, d, r, self.env.settings, price)).id
        return self.env.db(go)

    def trip(self, passenger_tg: int = 1, driver_tg: int = 2, plate: str = "30A123BC", price: int = 50_000) -> dict:
        """Passenger requests, driver offers, passenger accepts. Returns ids and the trip as the passenger sees it."""
        req = self.request(passenger_tg)
        driver_id = self.env.make_driver(driver_tg, plate)
        offer_id = self.offer(req["id"], driver_id, price)
        res = self.env.client.post(f"/api/offers/{offer_id}/accept", headers=auth(passenger_tg))
        assert res.status_code == 200, res.text
        return {"request": req, "driver_id": driver_id, "offer_id": offer_id, "trip": res.json(),
                "passenger_tg": passenger_tg, "driver_tg": driver_tg}


@pytest.fixture
def flow(env):
    return Flow(env)


@pytest.fixture
def H():
    """`H(tg_id)` -> Authorization header with signed initData (tests must not import conftest by name)."""
    return auth


@pytest.fixture
def sign():
    return sign_init_data
