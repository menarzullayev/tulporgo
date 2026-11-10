"""P2P card transfer with manual admin review (decisions 11, 44).

Flow: driver sees the card + exact amount + unique reference -> uploads the receipt photo (PENDING ->
AWAITING_REVIEW) -> an admin approves (-> PAID via billing.mark_paid) or rejects (-> FAILED).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.errors import Conflict, Forbidden, Invalid
from tulporgo_core.models import Payment, User

from .. import service
from .base import GatewayProvider


def reference(payment: Payment) -> str:
    """Unique, human-typeable note for the bank transfer."""
    return f"TG{payment.id:06d}"


class P2PProvider(GatewayProvider):
    name = "p2p"

    def configured(self) -> bool:
        return bool(self.settings.p2p_card_number.strip())

    async def start(self, payment: Payment, *, recurring: bool = False, **texts: str) -> dict:
        return {"type": "p2p", "card": self.settings.p2p_card_number, "holder": self.settings.p2p_card_holder,
                "amount": payment.amount, "currency": "UZS", "reference": reference(payment),
                "payment_id": payment.id}

    async def verify(self, payload: dict) -> bool:
        """A receipt submission is acceptable when it names a payment and carries a file id."""
        return bool(payload.get("payment_id")) and bool(str(payload.get("file_id") or "").strip())


async def attach_receipt(s: AsyncSession, user: User, payment: Payment, file_id: str) -> Payment:
    if payment.provider != "p2p":
        raise Invalid("not_p2p")
    if payment.user_id != user.id:
        raise Forbidden("not_your_payment")
    if not file_id:
        raise Invalid("receipt_required")
    if payment.status == PaymentStatus.AWAITING_REVIEW:
        raise Conflict("already_submitted")
    if payment.status != PaymentStatus.PENDING:
        raise Conflict("payment_closed")
    payment.receipt_file_id = file_id
    payment.status = PaymentStatus.AWAITING_REVIEW
    return payment


async def approve(s: AsyncSession, admin: User, payment: Payment, bus=None) -> tuple[Payment, bool]:
    """Returns (payment, changed). Only admins; a second approval is a no-op (changed=False)."""
    if not admin.is_admin:
        raise Forbidden("admin_only")
    if payment.provider != "p2p":
        raise Invalid("not_p2p")
    if payment.status == PaymentStatus.PAID:
        return payment, False
    if payment.status != PaymentStatus.AWAITING_REVIEW:
        raise Conflict("not_reviewable")
    await service.confirm(s, payment, bus=bus, external_id=reference(payment), reviewer=admin)
    return payment, True


async def reject(s: AsyncSession, admin: User, payment: Payment) -> tuple[Payment, bool]:
    if not admin.is_admin:
        raise Forbidden("admin_only")
    if payment.provider != "p2p":
        raise Invalid("not_p2p")
    if payment.status == PaymentStatus.FAILED:
        return payment, False
    if payment.status == PaymentStatus.PAID:
        raise Conflict("already_paid")
    if payment.status != PaymentStatus.AWAITING_REVIEW:
        raise Conflict("not_reviewable")
    payment.status = PaymentStatus.FAILED
    payment.reviewed_by_id = admin.id
    return payment, True
