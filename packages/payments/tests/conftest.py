"""Payment test fixtures: SQLite in memory, fake keys only (never real credentials, never the network)."""
from datetime import date, timedelta

import pytest
from pay_helpers import make_settings
from tulporgo_core.db import Base, make_engine, make_sessionmaker
from tulporgo_core.events import InMemoryBus


@pytest.fixture
async def engine():
    eng = make_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def maker(engine):
    return make_sessionmaker(engine)


@pytest.fixture
async def s(maker):
    async with maker() as session:
        yield session


@pytest.fixture
def cfg():
    return make_settings()


@pytest.fixture
def free_cfg():
    return make_settings(free_period_until=date.today() + timedelta(days=30))


@pytest.fixture
def bus():
    return InMemoryBus()


