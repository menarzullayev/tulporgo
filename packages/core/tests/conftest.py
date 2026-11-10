"""Core test fixtures. Runs on SQLite by default; set TULPORGO_TEST_DATABASE_URL (e.g. a PostgreSQL URL) to run the
same suite on another backend (CI does this for PostgreSQL)."""
import itertools
import os
from datetime import date, timedelta

import pytest
from sqlalchemy import text
from tulporgo_core.config import Settings
from tulporgo_core.db import Base, make_engine, make_sessionmaker, utcnow
from tulporgo_core.events import InMemoryBus
from tulporgo_core.models import Place
from tulporgo_core.services import drivers, users

_ids = itertools.count(1000)


@pytest.fixture
async def engine():
    url = os.environ.get("TULPORGO_TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    eng = make_engine(url)
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
        await c.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def s(engine):
    maker = make_sessionmaker(engine)
    async with maker() as session:
        yield session


@pytest.fixture
def settings():
    return Settings(database_url="sqlite+aiosqlite:///:memory:", free_period_until=None, trial_days=7)


@pytest.fixture
def free_settings():
    return Settings(database_url="sqlite+aiosqlite:///:memory:", free_period_until=date.today() + timedelta(days=30))


@pytest.fixture
def bus():
    return InMemoryBus()


@pytest.fixture
async def places(s):
    a = Place(kind="district", name_uz="Qo'shrabot", aliases=["koshrabad"], popularity=10)
    b = Place(kind="city", name_uz="Samarqand", name_ru="Самарканд", popularity=20)
    c = Place(kind="poi", name_uz="Qovunchi", popularity=5)
    s.add_all([a, b, c])
    await s.flush()
    return a, b, c


async def make_user(s, **kw):
    u = await users.get_or_create_user(s, next(_ids), username=kw.pop("username", None), first_name="Test")
    for k, v in kw.items():
        setattr(u, k, v)
    await s.flush()
    return u


async def make_driver(s, settings, plate=None, **kw):
    u = await make_user(s, phone="+998901234567")
    d = await drivers.register_driver(s, u, settings, car_make="Cobalt", car_color="oq",
                                      car_plate=plate or f"30A{next(_ids) % 1000:03d}BC", **kw)
    await s.flush()
    return d


@pytest.fixture
def now():
    return utcnow()


def is_postgres():
    return os.environ.get("TULPORGO_TEST_DATABASE_URL", "").startswith("postgresql")


__all__ = ["make_user", "make_driver", "text", "is_postgres"]
