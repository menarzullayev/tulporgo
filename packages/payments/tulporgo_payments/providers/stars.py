"""Telegram Stars (currency XTR): one-off invoices and recurring 30-day subscriptions.

Spec: https://core.telegram.org/bots/payments-stars (sendInvoice / createInvoiceLink with provider_token "" and
currency XTR; subscription_period must be 2592000 and the price per period <= 10000 Stars).
Our invoice payload is `pay:<payment_id>`; renewals of a subscription arrive as `successful_payment` with
`is_recurring` and the same payload and create a fresh Payment row each period.
"""
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.db import utcnow
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.errors import Conflict, Forbidden, Invalid
from tulporgo_core.models import Payment, User
from tulporgo_core.services import billing

from .. import service
from .base import GatewayProvider, TgCall

log = logging.getLogger(__name__)
SUBSCRIPTION_PERIOD = 2_592_000           # 30 days — the only value Telegram accepts
MAX_SUBSCRIPTION_STARS = 10_000
PAYLOAD_RE = re.compile(r"^pay:(\d+)$")


def make_payload(payment: Payment) -> str:
    return f"pay:{payment.id}"


def parse_payload(payload: str | None) -> int | None:
    m = PAYLOAD_RE.match(payload or "")
    return int(m.group(1)) if m else None


def http_tg_call(token: str) -> TgCall:
    """Raw Bot API call over HTTP (used by the API process, which has no aiogram Bot)."""
    async def call(method: str, params: dict) -> Any:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/{method}", json=params)
        data = r.json()
        if not data.get("ok"):
            raise Invalid("telegram_error", str(data.get("description", "")))
        return data["result"]
    return call


class StarsProvider(GatewayProvider):
    name = "stars"

    def configured(self) -> bool:
        return self.settings.stars_rate_uzs > 0

    def invoice_params(self, payment: Payment, *, title: str = "TulporGo", description: str = "Subscription",
                       label: str = "Subscription", recurring: bool = False) -> dict:
        """Parameters shared by sendInvoice / createInvoiceLink. The amount is the stored Payment amount."""
        if payment.currency != "XTR":
            raise Invalid("not_stars_payment")
        params: dict = {"title": title, "description": description, "payload": make_payload(payment),
                        "currency": "XTR", "prices": [{"label": label, "amount": payment.amount}],
                        "provider_token": ""}
        if recurring:
            if payment.months != 1:
                raise Invalid("recurring_one_month_only")
            if payment.amount > MAX_SUBSCRIPTION_STARS:
                raise Invalid("subscription_too_expensive")
            params["subscription_period"] = SUBSCRIPTION_PERIOD
        return params

    async def start(self, payment: Payment, *, recurring: bool = False, **texts: str) -> dict:
        params = self.invoice_params(payment, recurring=recurring, **texts)
        link = None
        if self.tg_call is not None:
            link = await self.tg_call("createInvoiceLink", params)
        return {"type": "stars", "invoice": params, "invoice_link": link, "stars": payment.amount,
                "recurring": recurring, "payment_id": payment.id}

    async def verify(self, payload: dict) -> bool:
        """Structural check of a pre_checkout / successful_payment payload (DB checks live in the functions below)."""
        return payload.get("currency") == "XTR" and parse_payload(payload.get("invoice_payload")) is not None


def expected_amount(plan, months: int, settings) -> int:
    """Stars the plan costs (decision-10 price converted at settings.stars_rate_uzs)."""
    return billing.stars_amount(billing.price_of(plan, months), settings)


async def validate_pre_checkout(s: AsyncSession, user: User, invoice_payload: str, currency: str,
                                total_amount: int) -> str | None:
    """None = approve; otherwise a short reason code for the refusal. Must be answered within 10 seconds."""
    pid = parse_payload(invoice_payload)
    if pid is None:
        return "bad_payload"
    p = await service.get_payment(s, pid) if await _exists(s, pid) else None
    if p is None:
        return "unknown_payment"
    if p.provider != "stars" or p.currency != "XTR":
        return "wrong_provider"
    if p.user_id != user.id:
        return "wrong_user"
    if p.status != PaymentStatus.PENDING:
        return "not_pending"
    if currency != "XTR" or total_amount != p.amount:
        return "amount_mismatch"
    return None


async def _exists(s: AsyncSession, pid: int) -> bool:
    return (await s.execute(select(Payment.id).where(Payment.id == pid))).first() is not None


async def process_successful_payment(s: AsyncSession, user: User, *, invoice_payload: str, currency: str,
                                     total_amount: int, charge_id: str, is_recurring: bool = False,
                                     is_first_recurring: bool = False, expires_at: int | None = None,
                                     bus=None) -> tuple[Payment, bool]:
    """Returns (payment, newly_paid). Replays of the same charge are no-ops; amount/user mismatches raise."""
    pid = parse_payload(invoice_payload)
    if pid is None:
        raise Invalid("bad_payload")
    if not charge_id:
        raise Invalid("charge_id_required")
    seen = (await s.execute(select(Payment).where(Payment.external_id == charge_id,
                                                  Payment.provider == "stars"))).scalars().first()
    if seen is not None:                                   # replayed update: nothing changes
        return seen, False
    origin = await service.get_payment(s, pid, lock=True)
    if origin.provider != "stars" or origin.currency != "XTR":
        raise Invalid("wrong_provider")
    if origin.user_id != user.id:
        raise Forbidden("wrong_user")
    if currency != "XTR" or total_amount != origin.amount:
        raise Invalid("amount_mismatch", f"expected {origin.amount} XTR, got {total_amount} {currency}")
    meta = {"charge_id": charge_id, "is_recurring": is_recurring, "expires_at": expires_at}
    if origin.status == PaymentStatus.PAID:
        if not (is_recurring and not is_first_recurring):
            return origin, False                           # already paid with another charge: do not extend twice
        renewal = Payment(user_id=origin.user_id, provider="stars", plan=origin.plan, months=origin.months,
                          amount=origin.amount, currency="XTR", payload={"stars": meta, "origin_id": origin.id})
        s.add(renewal)
        await s.flush()
        await service.confirm(s, renewal, bus=bus, external_id=charge_id)
        return renewal, True
    if origin.status != PaymentStatus.PENDING:
        raise Conflict("payment_closed")
    origin.payload = {**(origin.payload or {}), "stars": meta}
    await service.confirm(s, origin, bus=bus, external_id=charge_id)
    return origin, True


async def record_subscription_state(s: AsyncSession, invoice_payload: str, state: str) -> Payment | None:
    """BotSubscriptionUpdated (Bot API 10.2): remember canceled / active / failed on the originating payment."""
    pid = parse_payload(invoice_payload)
    if pid is None or not await _exists(s, pid):
        return None
    p = await service.get_payment(s, pid)
    if p.provider != "stars" or state not in ("canceled", "active", "failed"):
        return None
    p.payload = {**(p.payload or {}), "stars_subscription": state}
    return p



RefundCall = Callable[[int, str], Awaitable[Any]]


async def refund(s: AsyncSession, admin: User, payment: Payment, refund_call: RefundCall) -> tuple[Payment, bool]:
    """Admin refund of a paid Stars payment via refundStarPayment(user_id, telegram_payment_charge_id).
    Returns (payment, changed); a second refund is a no-op. The subscription is shortened by the paid period but
    never below now. Telegram is called first: if it fails nothing changes."""
    if not admin.is_admin:
        raise Forbidden("admin_only")
    if payment.provider != "stars" or payment.currency != "XTR":
        raise Invalid("not_stars_payment")
    if payment.status == PaymentStatus.REFUNDED:
        return payment, False
    if payment.status != PaymentStatus.PAID or not payment.external_id:
        raise Conflict("not_refundable")
    owner = await s.get(User, payment.user_id)
    if owner is None:
        raise Invalid("user_not_found")
    await refund_call(owner.tg_id, payment.external_id)
    await service.revert_paid(s, payment, floor=utcnow())
    payment.payload = {**(payment.payload or {}), "refunded_by": admin.id}
    return payment, True
