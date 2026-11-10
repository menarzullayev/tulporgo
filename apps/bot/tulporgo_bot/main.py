"""Bot entry point: `python -m tulporgo_bot`. This process is the ONLY consumer of bot updates (GOAL.md §2)."""
import asyncio
import importlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from tulporgo_core.config import Settings, get_settings
from tulporgo_core.db import make_engine, make_sessionmaker
from tulporgo_core.events import InMemoryBus, RedisBus

from .context import ContextMiddleware

log = logging.getLogger(__name__)
# Routers owned by other workstreams; included when present so the bot runs at every stage of the build.
OPTIONAL_ROUTERS = ["tulporgo_bot.handlers:router", "tulporgo_payments.bot:router", "tulporgo_userbot.bot:router"]


def make_bus(settings: Settings):
    if settings.redis_url:
        import redis.asyncio as redis
        return RedisBus(redis.from_url(settings.redis_url))
    return InMemoryBus()


def detached(router):
    """The routers are module-level singletons; letting a new dispatcher adopt one that an earlier dispatcher still
    holds makes `build_dispatcher` callable more than once (tests, reloads)."""
    router._parent_router = None
    return router


def make_storage(settings: Settings):
    """FSM state survives restarts when Redis is configured; otherwise in memory (development, tests)."""
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage
        return RedisStorage.from_url(settings.redis_url)
    return MemoryStorage()


def build_dispatcher(settings: Settings, maker, bus, storage=None) -> Dispatcher:
    dp = Dispatcher(storage=storage or MemoryStorage())
    mw = ContextMiddleware(maker, settings, bus)
    for observer in (dp.message, dp.callback_query, dp.inline_query, dp.pre_checkout_query, dp.my_chat_member,
                     dp.chat_join_request, dp.guest_message):
        observer.outer_middleware(mw)
    for spec in OPTIONAL_ROUTERS:
        mod_name, attr = spec.split(":")
        try:
            dp.include_router(detached(getattr(importlib.import_module(mod_name), attr)))
        except ModuleNotFoundError as e:
            if e.name and mod_name.startswith(e.name):
                log.info("router %s not available yet", spec)
            else:
                raise
    return dp


# Background jobs owned by other workstreams: (module, function). Each returns a handle with `.cancel()`.
OPTIONAL_JOBS = [("tulporgo_payments.jobs", "setup_jobs")]   # W4: expiry reminders, paid notices, Stars subscriptions


def start_optional_jobs(bot, maker, settings: Settings, bus) -> list:
    handles = []
    for mod_name, attr in OPTIONAL_JOBS:
        try:
            setup_jobs = getattr(importlib.import_module(mod_name), attr)
        except ModuleNotFoundError as e:
            if e.name and mod_name.startswith(e.name):
                log.info("jobs %s.%s not available", mod_name, attr)
                continue
            raise
        handles.append(setup_jobs(bot, maker, settings, bus))
    return handles


def finish_dispatcher(dp: Dispatcher) -> Dispatcher:
    """Free-text orders and the stale-button catch-all must come after every other handler, so they are attached last
    (after any router a test or another workstream adds on top of build_dispatcher)."""
    from tulporgo_bot.handlers import fallback
    dp.include_router(detached(fallback))
    return dp


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    maker = make_sessionmaker(make_engine(settings.database_url))
    bus = make_bus(settings)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = finish_dispatcher(build_dispatcher(settings, maker, bus, make_storage(settings)))
    setup = getattr(importlib.import_module("tulporgo_bot.handlers"), "setup", None)
    runtime = None
    if setup:                                            # W1 wires event subscribers / schedulers here
        runtime = await setup(bot=bot, maker=maker, settings=settings, bus=bus)
    extra_jobs = start_optional_jobs(bot, maker, settings, bus)
    listener = asyncio.create_task(bus.listen()) if isinstance(bus, RedisBus) else None
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if listener:
            listener.cancel()
        for handle in extra_jobs:
            handle.cancel()
        if runtime is not None:
            await runtime.stop()


if __name__ == "__main__":
    asyncio.run(run())
