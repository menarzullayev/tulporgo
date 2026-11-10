"""W1 — passenger, driver and admin flows of the TulporGo bot.

Integration points (see docs/goals/README.md):
    router   — included by `tulporgo_bot.main.build_dispatcher` together with the payments / userbot routers
    fallback — free text and stale buttons; included LAST so other workstreams' handlers win
    setup()  — called once at start-up: event subscribers, command menus, background jobs
"""
import asyncio
import logging
from dataclasses import dataclass, field

from aiogram import Router

from . import admin, driver, errors, guest, joinguard, mytrips, offers, order, picker, privacy, start, trips
from .notify import Notifier

log = logging.getLogger(__name__)

router = Router(name="bot")
router.message.middleware(errors.ErrorMiddleware())
router.callback_query.middleware(errors.ErrorMiddleware())
for sub in (start.router, picker.router, order.router, guest.router, offers.router, trips.router, driver.router,
            admin.router, mytrips.router, privacy.router, joinguard.router):
    router.include_router(sub)

fallback = order.fallback
fallback.message.middleware(errors.ErrorMiddleware())
fallback.callback_query.middleware(errors.ErrorMiddleware())


@dataclass
class Runtime:
    notifier: Notifier
    tasks: list[asyncio.Task] = field(default_factory=list)

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


async def setup(bot, maker, settings, bus, jobs: bool = True) -> Runtime:
    """Subscribe the notifier to the event bus, publish the command menus, start the background jobs."""
    from .. import delivery, jobs as job_mod
    from ..config import get_extra
    from . import commands

    extra = get_extra()
    delivery.LIMITER.rate = extra.rate_per_second
    notifier = Notifier(bot, maker, settings, extra)
    notifier.subscribe(bus)
    runtime = Runtime(notifier)
    await commands.set_defaults(bot)
    if jobs:
        runtime.tasks = [
            asyncio.create_task(job_mod.every(extra.expire_every_seconds, lambda: job_mod.expire_once(bot, maker, bus),
                                              "expire")),
            asyncio.create_task(job_mod.weekly_loop(bot, maker, settings, extra.report_weekday, extra.report_hour)),
            asyncio.create_task(job_mod.every(extra.tags_every_seconds, notifier.tags.sync, "member-tags")),
        ]
    return runtime
