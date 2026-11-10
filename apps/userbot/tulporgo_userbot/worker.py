"""Worker process: `python -m tulporgo_userbot`.

Loads the connected accounts every tick (new logins, pauses and "Hisobni uzish" take effect within TICK_SECONDS), runs
each account with its own Telethon session (device model "TulporGo (driver)"), listens for `UserbotStopped` /
`PaymentConfirmed` events and shuts down gracefully. Sessions are decrypted only in memory.
"""
import asyncio
import contextlib
import logging
import signal

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from tulporgo_core.config import Settings, get_settings
from tulporgo_core.db import make_engine, make_sessionmaker
from tulporgo_core.events import PaymentConfirmed, RedisBus, UserbotStopped

from .client import ClientFactory, make_telethon_factory
from .config import TICK_SECONDS
from .notifier import BotNotifier, Notifier
from .scheduler import Scheduler

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, scheduler: Scheduler, bus, tick_seconds: float = TICK_SECONDS) -> None:
        self.scheduler = scheduler
        self.bus = bus
        self.tick_seconds = tick_seconds
        self.stop = asyncio.Event()
        self.wake = asyncio.Event()
        bus.subscribe(UserbotStopped, self._on_stopped)
        bus.subscribe(PaymentConfirmed, self._on_plan_change)

    async def _on_stopped(self, event: UserbotStopped) -> None:
        await self.scheduler.forget(event.account_id)             # idempotent: forgetting twice is a no-op
        self.wake.set()

    async def _on_plan_change(self, _event: PaymentConfirmed) -> None:
        self.wake.set()                                           # plan limits are re-read at the next tick

    async def run(self) -> None:
        try:
            while not self.stop.is_set():
                try:
                    await self.scheduler.tick()
                except Exception:                                  # noqa: BLE001 - the loop must survive
                    log.exception("tick failed")
                self.wake.clear()
                waiters = [asyncio.ensure_future(self.stop.wait()), asyncio.ensure_future(self.wake.wait())]
                try:
                    await asyncio.wait(waiters, timeout=self.tick_seconds, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for w in waiters:
                        w.cancel()
        finally:
            await self.scheduler.close()


def build_worker(settings: Settings, maker, bus, factory: ClientFactory, notifier: Notifier) -> Worker:
    return Worker(Scheduler(maker, settings, bus, factory, notifier), bus)


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    maker = make_sessionmaker(make_engine(settings.database_url))
    if settings.redis_url:
        import redis.asyncio as redis
        bus = RedisBus(redis.from_url(settings.redis_url))
    else:
        from tulporgo_core.events import InMemoryBus
        bus = InMemoryBus()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    worker = build_worker(settings, maker, bus, make_telethon_factory(), BotNotifier(bot))
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):             # Windows: Ctrl+C raises KeyboardInterrupt instead
            loop.add_signal_handler(sig, worker.stop.set)
    listener = asyncio.create_task(bus.listen(worker.stop)) if isinstance(bus, RedisBus) else None
    try:
        await worker.run()
    finally:
        worker.stop.set()
        if listener:
            await listener
        await bot.session.close()
