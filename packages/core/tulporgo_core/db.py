"""Database plumbing: one async engine per URL, a declarative Base with a stable naming convention, UTC helpers.

All timestamps are stored as naive UTC so the same schema works on PostgreSQL, SQLite and MySQL.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import MetaData
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def utcnow() -> datetime:
    """Naive UTC 'now' (see module docstring)."""
    return datetime.now(UTC).replace(tzinfo=None)


def make_engine(url: str, **kw) -> AsyncEngine:
    if url.startswith("sqlite"):
        kw.setdefault("connect_args", {"check_same_thread": False})
    return create_async_engine(url, **kw)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Commit on success, roll back on any error."""
    async with maker() as s:
        try:
            yield s
            await s.commit()
        except BaseException:
            await s.rollback()
            raise


def rowcount(result: object) -> int:
    """Rows matched by an UPDATE/DELETE. `AsyncSession.execute()` is typed as `Result`; DML returns a `CursorResult`."""
    return cast(CursorResult, result).rowcount
