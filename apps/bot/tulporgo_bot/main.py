"""Bot entry point: `python -m tulporgo_bot`. This process is the ONLY consumer of bot updates (GOAL.md §2)."""
import asyncio
import importlib
import logging

from aiogram import Bot, Dispatcher
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


def build_dispatcher(settings: Settings, maker, bus) -> Dispatcher:
    dp = Dispatcher()
    mw = ContextMiddleware(maker, settings, bus)
    for observer in (dp.message, dp.callback_query, dp.inline_query, dp.pre_checkout_query, dp.my_chat_member,
                     dp.chat_join_request):
        observer.outer_middleware(mw)
    for spec in OPTIONAL_ROUTERS:
        mod_name, attr = spec.split(":")
        try:
            dp.include_router(getattr(importlib.import_module(mod_name), attr))
        except ModuleNotFoundError as e:
            if e.name and mod_name.startswith(e.name):
                log.info("router %s not available yet", spec)
            else:
                raise
    return dp


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    maker = make_sessionmaker(make_engine(settings.database_url))
    bus = make_bus(settings)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(settings, maker, bus)
    setup = getattr(importlib.import_module("tulporgo_bot.handlers"), "setup", None)
    if setup:                                            # W1 wires event subscribers / schedulers here
        await setup(bot=bot, maker=maker, settings=settings, bus=bus)
    listener = asyncio.create_task(bus.listen()) if isinstance(bus, RedisBus) else None
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if listener:
            listener.cancel()


if __name__ == "__main__":
    asyncio.run(run())
