"""Background jobs started by `handlers.setup`: expire requests every minute, weekly KPI report to the owner
(Monday 09:00 Asia/Tashkent), member-tag sync in the drivers group."""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope, utcnow
from tulporgo_core.events import RequestClosed
from tulporgo_core.models import RideRequest, User
from tulporgo_core.services import kpi, rides
from tulporgo_core.text.alphabet import convert

from . import delivery
from .handlers.common import esc, local_to_utc, to_local, user_t

log = logging.getLogger(__name__)


def next_weekly_run(now: datetime, weekday: int = 0, hour: int = 9) -> datetime:
    """Next `weekday` (Mon=0) at `hour`:00 Tashkent time strictly after `now` (naive UTC in, naive UTC out)."""
    local = to_local(now)
    target = local.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=(weekday - local.weekday()) % 7)
    if target <= local:
        target += timedelta(days=7)
    return local_to_utc(target)


async def expire_once(bot: Bot, maker: async_sessionmaker[AsyncSession], bus, now: datetime | None = None) -> list[int]:
    """Close requests whose time is up; tell each passenger. Returns the expired request ids."""
    async with session_scope(maker) as s:
        ids = await rides.expire_requests(s, now)
        notes = []
        if ids:
            for r in (await s.execute(select(RideRequest).where(RideRequest.id.in_(ids)))).scalars():
                p = await s.get(User, r.passenger_id)
                notes.append((p.tg_id, user_t(p)("bot.order.expired", route=f"{r.from_text} → {r.to_text}")))
    for i in ids:                                         # committed: now announce
        await bus.publish(RequestClosed(i, "expired"))
    for tg_id, text in notes:
        await delivery.send(bot, tg_id, f"⌛ {esc(text)}")
    return ids


async def weekly_report(bot: Bot, maker: async_sessionmaker[AsyncSession], settings: Settings,
                        now: datetime | None = None) -> bool:
    """KPI report to the owner (decision 53). False when no owner chat is configured."""
    if not settings.owner_chat_id:
        log.warning("weekly KPI report skipped: TULPORGO_OWNER_CHAT_ID is not set")
        return False
    async with session_scope(maker) as s:
        text = kpi.report(await kpi.compute(s, now))
    await delivery.send(bot, settings.owner_chat_id, esc(convert(text, "uz_new")))   # owner reads the new alphabet (29)
    return True


async def every(seconds: float, fn: Callable[[], Awaitable], name: str) -> None:
    while True:
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except Exception:                                  # noqa: BLE001 — a job must survive its own errors
            log.exception("job %s failed", name)
        await asyncio.sleep(seconds)


async def weekly_loop(bot: Bot, maker, settings: Settings, weekday: int, hour: int) -> None:
    while True:
        wait = (next_weekly_run(utcnow(), weekday, hour) - utcnow()).total_seconds()
        while wait > 0:                                    # short sleeps: robust against clock changes
            await asyncio.sleep(min(wait, 3600))
            wait = (next_weekly_run(utcnow(), weekday, hour) - utcnow()).total_seconds() if wait > 3600 else 0
        try:
            await weekly_report(bot, maker, settings)
        except asyncio.CancelledError:
            raise
        except Exception:                                  # noqa: BLE001
            log.exception("weekly report failed")
        await asyncio.sleep(61)                            # never fire twice in the same minute
