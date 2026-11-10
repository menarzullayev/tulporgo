"""Provider-independent payment orchestration: checkout creation and idempotent confirmation.

All provider callbacks (Stars, Click, Payme, P2P approval) end in `confirm()`, which delegates to
`billing.mark_paid` — idempotent, so a replayed callback never extends a subscription twice.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import PaymentStatus, Plan
from tulporgo_core.errors import Conflict, Forbidden, Invalid, NotFound
from tulporgo_core.models import Driver, Payment, User
from tulporgo_core.services import billing
from tulporgo_core.services.drivers import get_driver


@dataclass
class Checkout:
    payment: Payment
    start: dict


def parse_plan(value: str | Plan) -> Plan:
    try:
        return Plan(value)
    except ValueError as e:
        raise Invalid("bad_plan") from e


async def driver_of_user(s: AsyncSession, user_id: int) -> Driver | None:
    return (await s.execute(select(Driver).where(Driver.user_id == user_id))).scalar_one_or_none()


async def start_checkout(s: AsyncSession, user: User, settings: Settings, provider: str, plan: str | Plan, months: int,
                         *, recurring: bool = False, tg_call=None) -> Checkout:
    """Create (or reuse) a pending Payment for `user` and ask the provider how to pay it.

    Refused while the free period runs (decision 44), for non-drivers, unknown/unconfigured providers and bad
    plan/months. The amount is computed here from decision-10 prices — nothing comes from the client."""
    if billing.in_free_period(settings):
        raise Conflict("free_period", "everything is free right now")
    if user.is_blocked:
        raise Forbidden("blocked")
    if await get_driver(s, user) is None:
        raise Forbidden("driver_required")
    from .providers import get_provider  # lazy: providers import this module
    plan_enum = parse_plan(plan)
    gateway = get_provider(provider, settings, tg_call=tg_call)
    if gateway is None or not gateway.configured():
        raise Invalid("provider_unavailable")
    currency = "XTR" if provider == "stars" else "UZS"
    billing.price_of(plan_enum, months)                    # validates months (1/3/6/12)
    payment = (await s.execute(
        select(Payment).where(Payment.user_id == user.id, Payment.provider == provider, Payment.plan == plan_enum,
                              Payment.months == months, Payment.status == PaymentStatus.PENDING,
                              Payment.currency == currency).order_by(Payment.id.desc()).limit(1)
    )).scalars().first()
    if payment is None:
        payment = await billing.create_payment(s, user, provider, plan_enum, months, currency=currency,
                                               settings=settings)
    start = await (gateway.start(payment, recurring=recurring) if provider == "stars" else gateway.start(payment))
    return Checkout(payment, start)


async def confirm(s: AsyncSession, payment: Payment, bus=None, external_id: str | None = None,
                  reviewer: User | None = None) -> Payment:
    """Idempotent confirmation: marks paid and extends the driver's subscription exactly once."""
    driver = await driver_of_user(s, payment.user_id)
    if driver is None:
        raise Conflict("driver_required")
    return await billing.mark_paid(s, payment, driver, bus=bus, external_id=external_id, reviewer=reviewer)


async def revert_paid(s: AsyncSession, payment: Payment, floor: datetime | None = None) -> None:
    """A confirmed payment was refunded (Payme cancel after perform, Stars refund): take its days back.
    `floor` (e.g. now) stops the subscription from being shortened below that moment."""
    driver = await driver_of_user(s, payment.user_id)
    if driver and driver.subscription_until:
        new = driver.subscription_until - timedelta(days=30 * payment.months)
        driver.subscription_until = max(new, floor) if floor else new
    payment.status = PaymentStatus.REFUNDED


async def get_payment(s: AsyncSession, payment_id: int, *, lock: bool = False) -> Payment:
    q = select(Payment).where(Payment.id == payment_id)
    if lock:
        q = q.with_for_update()
    p = (await s.execute(q)).scalar_one_or_none()
    if p is None:
        raise NotFound("payment_not_found")
    return p
