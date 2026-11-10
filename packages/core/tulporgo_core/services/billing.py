"""Plans, subscription state and the payment ledger (decisions 10, 44). Provider integrations (P2P, Stars, Click,
Payme, …) implement `PaymentProvider` in their own modules (workstream W4); this module stays provider-agnostic."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import utcnow
from ..enums import PaymentStatus, Plan
from ..errors import Conflict, Invalid
from ..events import PaymentConfirmed
from ..models import Driver, Payment, User


@dataclass(frozen=True)
class PlanInfo:
    plan: Plan
    price_uzs: int
    max_groups: int | None     # userbot groups; None = unlimited
    autopost: bool
    priority: bool


PLANS = {
    Plan.BASIC: PlanInfo(Plan.BASIC, 29_000, 0, False, False),
    Plan.PRO: PlanInfo(Plan.PRO, 59_000, 15, True, False),
    Plan.BUSINESS: PlanInfo(Plan.BUSINESS, 99_000, None, True, True),
}


def in_free_period(settings: Settings, today: date | None = None) -> bool:
    return bool(settings.free_period_until and (today or utcnow().date()) <= settings.free_period_until)


def subscription_active(driver: Driver, settings: Settings, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return in_free_period(settings, now.date()) or bool(driver.subscription_until and driver.subscription_until > now)


def effective_plan(driver: Driver, settings: Settings, now: datetime | None = None) -> PlanInfo | None:
    """During the free period everyone gets Business features (decision 44: everything free)."""
    if in_free_period(settings, (now or utcnow()).date()):
        return PLANS[Plan.BUSINESS]
    if subscription_active(driver, settings, now):
        return PLANS.get(Plan(driver.plan)) if driver.plan else PLANS[Plan.BASIC]
    return None


def extend(driver: Driver, days: int, now: datetime | None = None) -> datetime:
    now = now or utcnow()
    start = driver.subscription_until if driver.subscription_until and driver.subscription_until > now else now
    driver.subscription_until = start + timedelta(days=days)
    return driver.subscription_until


def price_of(plan: Plan, months: int) -> int:
    """Monthly price × months. No multi-month discount: decision 10 sets monthly prices only."""
    if months not in (1, 3, 6, 12):
        raise Invalid("bad_months")
    return PLANS[plan].price_uzs * months


def stars_amount(uzs: int, settings: Settings) -> int:
    return max(1, round(uzs / settings.stars_rate_uzs))


async def create_payment(s: AsyncSession, user: User, provider: str, plan: Plan, months: int = 1,
                         currency: str = "UZS", settings: Settings | None = None) -> Payment:
    amount = price_of(plan, months)
    if currency == "XTR":
        amount = stars_amount(amount, settings or Settings())
    p = Payment(user_id=user.id, provider=provider, plan=plan, months=months, amount=amount, currency=currency)
    s.add(p)
    await s.flush()
    return p


async def mark_paid(s: AsyncSession, payment: Payment, driver: Driver, bus=None, external_id: str | None = None,
                    reviewer: User | None = None) -> Payment:
    """Idempotent: a second confirmation of the same payment changes nothing."""
    if payment.status == PaymentStatus.PAID:
        return payment
    if payment.status in (PaymentStatus.CANCELLED, PaymentStatus.REFUNDED):
        raise Conflict("payment_closed")
    payment.status = PaymentStatus.PAID
    payment.paid_at = utcnow()
    payment.external_id = external_id or payment.external_id
    payment.reviewed_by_id = reviewer.id if reviewer else None
    driver.plan = payment.plan
    extend(driver, 30 * payment.months)
    if bus:
        await bus.publish(PaymentConfirmed(payment.id))
    return payment


class PaymentProvider(ABC):
    """W4 implements one subclass per provider. `start` returns what the bot/Mini App shows the user
    (a URL, a Stars invoice, or P2P card instructions); `verify` checks a provider callback."""

    name: str

    @abstractmethod
    async def start(self, payment: Payment) -> dict: ...

    @abstractmethod
    async def verify(self, payload: dict) -> bool: ...
