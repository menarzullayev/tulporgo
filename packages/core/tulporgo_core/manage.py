"""Operations CLI used by Docker and the deploy scripts.

    python -m tulporgo_core.manage migrate        # alembic upgrade head
    python -m tulporgo_core.manage seed-places    # load regions, districts, mahallas (idempotent)
    python -m tulporgo_core.manage check          # exit 0 only if the DB answers and is at the head revision

The database URL comes from TULPORGO_DATABASE_URL (Settings) unless --url is given.
"""
import argparse
import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select

from . import places
from .config import get_settings
from .db import make_engine, make_sessionmaker, session_scope
from .models import Place

CORE = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    c = Config(str(CORE / "alembic.ini"))
    c.set_main_option("script_location", str(CORE / "migrations"))
    c.attributes["url"] = url
    return c


def migrate(url: str) -> None:
    command.upgrade(alembic_config(url), "head")


async def seed_places(url: str) -> int:
    engine = make_engine(url)
    try:
        async with session_scope(make_sessionmaker(engine)) as s:
            await places.seed(s)
            return await s.scalar(select(func.count()).select_from(Place)) or 0
    finally:
        await engine.dispose()


async def current_revision(url: str) -> str | None:
    engine = make_engine(url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(lambda c: MigrationContext.configure(c).get_current_revision())
    finally:
        await engine.dispose()


def head_revision(url: str) -> str | None:
    return ScriptDirectory.from_config(alembic_config(url)).get_current_head()


def check(url: str) -> tuple[bool, str]:
    try:
        current = asyncio.run(current_revision(url))
    except Exception as e:  # noqa: BLE001 — any connection error means "not healthy"
        return False, f"database unreachable: {type(e).__name__}"
    head = head_revision(url)
    if current != head:
        return False, f"revision {current} != head {head}"
    return True, f"ok, revision {head}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tulporgo_core.manage")
    p.add_argument("command", choices=["migrate", "seed-places", "check"])
    p.add_argument("--url", help="database URL (default: TULPORGO_DATABASE_URL)")
    a = p.parse_args(argv)
    url = a.url or get_settings().database_url
    if a.command == "migrate":
        migrate(url)
        print("migrate: at head")
        return 0
    if a.command == "seed-places":
        print(f"seed-places: {asyncio.run(seed_places(url))} places")
        return 0
    ok, msg = check(url)
    print(f"check: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
