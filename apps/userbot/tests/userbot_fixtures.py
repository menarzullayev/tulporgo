"""Userbot test fixtures: SQLite file DB, fake Telethon factory (NO network, NO real login).

Deliberately NOT a conftest.py: packages/core/tests does `from conftest import ...`, which resolves to whichever
conftest.py was imported first, so a second conftest.py anywhere in the suite would break it. Test modules import
these fixtures with `from userbot_fixtures import *`."""
from datetime import date, timedelta

import pytest
from cryptography.fernet import Fernet
from tulporgo_core.config import Settings
from tulporgo_core.db import Base, make_engine, make_sessionmaker
from tulporgo_core.events import InMemoryBus
from tulporgo_userbot import runtime
from userbot_helpers import FakeFactory, FakeNotifier


@pytest.fixture
def key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
async def engine(tmp_path):
    eng = make_engine(f"sqlite+aiosqlite:///{(tmp_path / 'ub.db').as_posix()}")
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
def settings(key):
    """Free period: everyone is Business (decision 44)."""
    return Settings(database_url="sqlite+aiosqlite:///:memory:", bot_token="123456:TEST", bot_username="tulporgobot",
                    free_period_until=date.today() + timedelta(days=30), userbot_encryption_key=key,
                    admin_ids=[])


@pytest.fixture
def paid_settings(settings):
    return settings.model_copy(update={"free_period_until": None})


@pytest.fixture
def bus():
    return InMemoryBus()


@pytest.fixture
def factory():
    f = FakeFactory()
    runtime.set_factory(f)
    yield f
    runtime.set_factory(None)


@pytest.fixture
def notifier():
    return FakeNotifier()


__all__ = ["key", "engine", "maker", "s", "settings", "paid_settings", "bus", "factory", "notifier"]
