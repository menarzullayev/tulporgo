"""Click "SHOP API" (Prepare / Complete) — https://docs.click.uz/click-api-request/ (section SHOP API).

Both requests are POSTs from Click carrying `sign_string` = MD5 over
    Prepare : click_trans_id + service_id + SECRET_KEY + merchant_trans_id + amount + action + sign_time
    Complete: click_trans_id + service_id + SECRET_KEY + merchant_trans_id + merchant_prepare_id + amount + action
              + sign_time
(all values concatenated exactly as received). `merchant_trans_id` is our Payment.id. Replies are JSON with
`error` / `error_note`; error codes below follow the Click spec.
"""
import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.errors import Conflict
from tulporgo_core.models import Payment

from .. import service
from .base import GatewayProvider

PAY_URL = "https://my.click.uz/services/pay"

OK = 0
SIGN_FAILED = -1
BAD_AMOUNT = -2
ACTION_NOT_FOUND = -3
ALREADY_PAID = -4
USER_NOT_FOUND = -5
TRANSACTION_NOT_FOUND = -6
UPDATE_FAILED = -7
BAD_REQUEST = -8
CANCELLED = -9

NOTES = {
    OK: "Success", SIGN_FAILED: "SIGN CHECK FAILED!", BAD_AMOUNT: "Incorrect parameter amount",
    ACTION_NOT_FOUND: "Action not found", ALREADY_PAID: "Already paid", USER_NOT_FOUND: "User does not exist",
    TRANSACTION_NOT_FOUND: "Transaction does not exist", UPDATE_FAILED: "Failed to update user",
    BAD_REQUEST: "Error in request from click", CANCELLED: "Transaction cancelled",
}
PREPARE_FIELDS = ("click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time",
                  "sign_string")
COMPLETE_FIELDS = PREPARE_FIELDS + ("merchant_prepare_id",)


def sign_string(params: dict, secret: str, *, complete: bool) -> str:
    parts = [params["click_trans_id"], params["service_id"], secret, params["merchant_trans_id"]]
    if complete:
        parts.append(params["merchant_prepare_id"])
    parts += [params["amount"], params["action"], params["sign_time"]]
    return hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()


def check_sign(params: dict, secret: str, *, complete: bool) -> bool:
    try:
        expected = sign_string(params, secret, complete=complete)
    except KeyError:
        return False
    return bool(secret) and hmac.compare_digest(expected, str(params.get("sign_string", "")).lower())


def build_pay_url(settings: Settings, payment: Payment, return_url: str | None = None) -> str:
    q = {"service_id": settings.click_service_id, "merchant_id": settings.click_merchant_id,
         "amount": f"{payment.amount}.00", "transaction_param": payment.id,
         "return_url": return_url or f"https://t.me/{settings.bot_username}"}
    return f"{PAY_URL}?{urlencode(q)}"


class ClickProvider(GatewayProvider):
    name = "click"

    def configured(self) -> bool:
        s = self.settings
        return bool(s.click_service_id and s.click_merchant_id and s.click_secret_key)

    async def start(self, payment: Payment) -> dict:
        return {"type": "url", "url": build_pay_url(self.settings, payment), "amount": payment.amount,
                "currency": "UZS", "payment_id": payment.id}

    async def verify(self, payload: dict) -> bool:
        complete = str(payload.get("action")) == "1"
        return check_sign(payload, self.settings.click_secret_key, complete=complete)


def reply(params: dict, code: int, **extra) -> dict:
    out = {"click_trans_id": params.get("click_trans_id"), "merchant_trans_id": params.get("merchant_trans_id"),
           **extra, "error": code, "error_note": NOTES[code]}
    return out


def _amount_ok(raw: str, payment: Payment) -> bool | None:
    try:
        return Decimal(str(raw)) == Decimal(payment.amount)
    except (InvalidOperation, ValueError):
        return None


async def _find(s: AsyncSession, merchant_trans_id: str) -> Payment | None:
    if not str(merchant_trans_id).isdigit():
        return None
    p = (await s.execute(select(Payment).where(Payment.id == int(merchant_trans_id)).with_for_update())
         ).scalar_one_or_none()
    return p if p is not None and p.provider == "click" else None


async def handle(s: AsyncSession, settings: Settings, params: dict, bus=None) -> dict:
    """Entry point for both endpoints; `action` selects Prepare (0) or Complete (1)."""
    params = {k: ("" if v is None else str(v)) for k, v in params.items()}
    action = params.get("action")
    if action not in ("0", "1"):
        return reply(params, ACTION_NOT_FOUND if action is not None and action != "" else BAD_REQUEST)
    complete = action == "1"
    if any(params.get(f, "") == "" for f in (COMPLETE_FIELDS if complete else PREPARE_FIELDS)):
        return reply(params, BAD_REQUEST)
    if not check_sign(params, settings.click_secret_key, complete=complete):
        return reply(params, SIGN_FAILED)
    if params["service_id"] != settings.click_service_id:
        return reply(params, BAD_REQUEST)
    return await (_complete if complete else _prepare)(s, settings, params, bus)


async def _prepare(s: AsyncSession, settings: Settings, params: dict, bus) -> dict:
    p = await _find(s, params["merchant_trans_id"])
    if p is None:
        return reply(params, USER_NOT_FOUND)
    ok = _amount_ok(params["amount"], p)
    if ok is None:
        return reply(params, BAD_REQUEST)
    if not ok:
        return reply(params, BAD_AMOUNT)
    if p.status == PaymentStatus.PAID:
        return reply(params, ALREADY_PAID)
    if p.status != PaymentStatus.PENDING:
        return reply(params, CANCELLED)
    p.external_id = params["click_trans_id"]
    p.payload = {**(p.payload or {}), "click": {"click_trans_id": params["click_trans_id"],
                                                 "click_paydoc_id": params.get("click_paydoc_id", ""),
                                                 "prepared": True}}
    return reply(params, OK, merchant_prepare_id=p.id)


async def _complete(s: AsyncSession, settings: Settings, params: dict, bus) -> dict:
    p = await _find(s, params["merchant_trans_id"])
    if p is None:
        return reply(params, USER_NOT_FOUND)
    click = (p.payload or {}).get("click") or {}
    if (not click.get("prepared") or params["merchant_prepare_id"] != str(p.id)
            or click.get("click_trans_id") != params["click_trans_id"]):
        return reply(params, TRANSACTION_NOT_FOUND)
    ok = _amount_ok(params["amount"], p)
    if ok is None:
        return reply(params, BAD_REQUEST)
    if not ok:
        return reply(params, BAD_AMOUNT)
    if p.status == PaymentStatus.PAID:                     # replayed callback: nothing changes
        return reply(params, ALREADY_PAID, merchant_confirm_id=p.id)
    if p.status != PaymentStatus.PENDING:
        return reply(params, CANCELLED)
    try:
        err = int(params.get("error") or 0)
    except ValueError:
        return reply(params, BAD_REQUEST)
    if err < 0:                                            # Click reports the payment failed: close ours
        p.status = PaymentStatus.CANCELLED
        return reply(params, CANCELLED, merchant_confirm_id=p.id)
    try:
        await service.confirm(s, p, bus=bus, external_id=params["click_trans_id"])
    except Conflict:
        return reply(params, UPDATE_FAILED)
    return reply(params, OK, merchant_confirm_id=p.id)
