"""Alembic environment (async). The URL comes from TULPORGO_DATABASE_URL (Settings), never from alembic.ini."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from tulporgo_core import models  # noqa: F401  (registers tables on Base.metadata)
from tulporgo_core.config import get_settings
from tulporgo_core.db import Base, make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata


def url() -> str:
    return config.attributes.get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # render_as_batch: SQLite needs table rebuilds for ALTERs; harmless on PostgreSQL/MySQL
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True,
                      compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = make_engine(url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is not None:                     # called from code with an existing sync connection
        do_run_migrations(connectable)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
