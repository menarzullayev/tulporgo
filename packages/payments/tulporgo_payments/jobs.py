"""Background hooks run inside the bot process: expiry reminders and payment-confirmed notifications.

The bot calls `setup_jobs(bot, maker, settings)` once at start-up (optionally `bus=` to also notify drivers about
payments confirmed in other processes, e.g. Click/Payme callbacks handled by the API). The handle it returns can be
used with or without `await`.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope, utcnow
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.events import PaymentConfirmed
from tulporgo_core.i18n import lang_of, t
from tulporgo_core.models import Driver, Payment
from tulporgo_core.services import billing

log = logging.getLogger(__name__)
REMIND_BEFORE = timedelta(days=3)
CHECK_EVERY = 3600                       # seconds
_SENT: set[tuple[int, str]] = set()      # (driver_id, subscription_until) already reminded in this process


class JobsHandle:
    def __init__(self, tasks: list[asyncio.Task]) -> None:
        self.tasks = tasks

    def cancel(self) -> None:
        for task in self.tasks:
            task.cancel()

    def __await__(self):
        async def _done():
            return self
        return _done().__await__()


async def run_reminders(bot, maker, settings: Settings, now: datetime | None = None,
                        sent: set[tuple[int, str]] | None = None) -> int:
    """Message drivers whose paid/trial period ends within 3 days. Never during the free period (nothing to renew).
    Dedupe is per (driver, expiry) in memory: a restart can repeat a reminder once, never spam it."""
    from . import bot as botmod
    now = now or utcnow()
    sent = _SENT if sent is None else sent
    if billing.in_free_period(settings, now.date()):
        return 0
    count = 0
    async with session_scope(maker) as s:
        drivers = (await s.execute(select(Driver).where(Driver.subscription_until > now,
                                                        Driver.subscription_until <= now + REMIND_BEFORE))
                   ).scalars().all()
        for d in drivers:
            key = (d.id, d.subscription_until.isoformat())
            if key in sent:
                continue
            lg = lang_of(d.user.lang)
            markup = botmod.kb([[botmod.btn(t("pay.btn.renew", lg), data="pay:home", style="primary")]])
            if await botmod._send(bot, d.user.tg_id, t("pay.reminder", lg, date=botmod.fmt_date(d.subscription_until)),
                                  markup):
                sent.add(key)
                count += 1
    return count


def setup_jobs(bot, maker, settings: Settings, bus=None) -> JobsHandle:
    from . import bot as botmod
    botmod.STATE["maker"] = maker
    tasks: list[asyncio.Task] = []

    if bus is not None:
        async def notify_when_committed(payment_id: int) -> None:
            # events are published before the publisher's transaction commits: wait until the payment is visible
            for delay in (0, 0.5, 1, 2, 4):
                await asyncio.sleep(delay)
                async with session_scope(maker) as s:
                    p = await s.get(Payment, payment_id)
                    if p is not None and p.status == PaymentStatus.PAID:
                        await botmod.notify_paid(bot, s, p, settings)
                        return

        async def on_paid(event: PaymentConfirmed) -> None:
            task = asyncio.get_running_loop().create_task(notify_when_committed(event.payment_id))
            botmod.PENDING.add(task)
            task.add_done_callback(botmod.PENDING.discard)
        bus.subscribe(PaymentConfirmed, on_paid)

    async def loop() -> None:
        while True:
            try:
                await run_reminders(bot, maker, settings)
            except Exception:
                log.exception("expiry reminder run failed")
            await asyncio.sleep(CHECK_EVERY)

    tasks.append(asyncio.get_running_loop().create_task(loop(), name="payments-reminders"))
    return JobsHandle(tasks)
