"""Payme "Merchant API" (JSON-RPC 2.0 over HTTPS POST) — https://developer.help.paycom.uz (Merchant API protocol).

* Auth: header `Authorization: Basic base64("Paycom:" + KEY)`; wrong/missing -> error -32504.
* Amounts are in tiyin (1 so'm = 100 tiyin); times are Unix milliseconds.
* Transaction states: 1 created, 2 performed, -1 cancelled before perform, -2 cancelled after perform (refund).
* A created transaction must be performed within 12 hours, otherwise it is cancelled with reason 4 (-31008).
* Our order is the Payment; the account field is `payment_id`. Transaction state is kept in Payment.payload["payme"].
Errors: -32300 bad HTTP method, -32700 parse, -32600 invalid request, -32601 unknown method, -32504 no
privileges, -31001 wrong amount, -31003 transaction not found, -31008 cannot perform, -31050..-31099 account
errors (-31050 order not found, -31099 order busy/closed).
"""
import base64
import hmac
import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.errors import Conflict
from tulporgo_core.models import Payment

from .. import service
from .base import GatewayProvider

CHECKOUT = "https://checkout.paycom.uz"
CHECKOUT_TEST = "https://test.paycom.uz"
TIMEOUT_MS = 12 * 3600 * 1000
ACCOUNT_FIELD = "payment_id"

CREATED, PERFORMED, CANCELLED_BEFORE, CANCELLED_AFTER = 1, 2, -1, -2
REASON_TIMEOUT = 4

MESSAGES = {
    -32504: {"ru": "Недостаточно привилегий для выполнения метода", "uz": "Metodni bajarish uchun huquq yetarli emas",
             "en": "Insufficient privileges"},
    -32700: {"ru": "Ошибка разбора JSON", "uz": "JSON xato", "en": "Parse error"},
    -32600: {"ru": "Неверный запрос", "uz": "Noto'g'ri so'rov", "en": "Invalid request"},
    -32601: {"ru": "Метод не найден", "uz": "Metod topilmadi", "en": "Method not found"},
    -31001: {"ru": "Неверная сумма", "uz": "Noto'g'ri summa", "en": "Wrong amount"},
    -31003: {"ru": "Транзакция не найдена", "uz": "Tranzaksiya topilmadi", "en": "Transaction not found"},
    -31008: {"ru": "Невозможно выполнить операцию", "uz": "Operatsiyani bajarib bo'lmaydi",
             "en": "Unable to perform operation"},
    -31050: {"ru": "Заказ не найден", "uz": "Buyurtma topilmadi", "en": "Order not found"},
    -31099: {"ru": "Заказ недоступен для оплаты", "uz": "Buyurtma to'lov uchun mavjud emas",
             "en": "Order is not available for payment"},
}


class PaymeError(Exception):
    def __init__(self, code: int, data: Any = None) -> None:
        super().__init__(code)
        self.code, self.data = code, data


def build_checkout_url(settings: Settings, payment: Payment, return_url: str | None = None, lang: str = "uz") -> str:
    """https://checkout.paycom.uz/<base64 of "m=...;ac.payment_id=...;a=<tiyin>;l=...;c=<return>">"""
    parts = [f"m={settings.payme_merchant_id}", f"ac.{ACCOUNT_FIELD}={payment.id}", f"a={payment.amount * 100}",
             f"l={lang}", f"c={return_url or f'https://t.me/{settings.bot_username}'}"]
    token = base64.b64encode(";".join(parts).encode()).decode()
    return f"{CHECKOUT_TEST if settings.payme_test_mode else CHECKOUT}/{token}"


def check_auth(header: str | None, key: str) -> bool:
    if not key or not header:
        return False
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        login, _, password = base64.b64decode(token.strip(), validate=True).decode().partition(":")
    except (ValueError, UnicodeDecodeError):
        return False
    return hmac.compare_digest(login.encode(), b"Paycom") & hmac.compare_digest(password.encode(), key.encode())


class PaymeProvider(GatewayProvider):
    name = "payme"

    def configured(self) -> bool:
        return bool(self.settings.payme_merchant_id and self.settings.payme_key)

    async def start(self, payment: Payment, *, recurring: bool = False, **texts: str) -> dict:
        return {"type": "url", "url": build_checkout_url(self.settings, payment), "amount": payment.amount,
                "amount_tiyin": payment.amount * 100, "currency": "UZS", "payment_id": payment.id}

    async def verify(self, payload: dict) -> bool:
        return check_auth(payload.get("authorization"), self.settings.payme_key)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _pm(p: Payment) -> dict:
    return (p.payload or {}).get("payme") or {}


def _save(p: Payment, pm: dict) -> None:
    p.payload = {**(p.payload or {}), "payme": pm}


def _tx_view(p: Payment) -> dict:
    pm = _pm(p)
    return {"create_time": pm.get("create_time", 0), "perform_time": pm.get("perform_time", 0),
            "cancel_time": pm.get("cancel_time", 0), "transaction": str(p.id), "state": pm["state"],
            "reason": pm.get("reason")}


async def _order(s: AsyncSession, params: dict) -> Payment:
    account = params.get("account")
    raw = str((account.get(ACCOUNT_FIELD) if isinstance(account, dict) else None) or "")
    if not raw.isdigit():
        raise PaymeError(-31050, ACCOUNT_FIELD)
    p = (await s.execute(select(Payment).where(Payment.id == int(raw)).with_for_update())).scalar_one_or_none()
    if p is None or p.provider != "payme":
        raise PaymeError(-31050, ACCOUNT_FIELD)
    return p


def _check_order(p: Payment, params: dict) -> None:
    amount = params.get("amount")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount != p.amount * 100:
        raise PaymeError(-31001, "amount")
    if p.status != PaymentStatus.PENDING or _pm(p).get("state") == CREATED:
        raise PaymeError(-31099, ACCOUNT_FIELD)


async def _tx(s: AsyncSession, params: dict) -> Payment:
    tid = params.get("id")
    if not isinstance(tid, str) or not tid:
        raise PaymeError(-32600)
    p = (await s.execute(select(Payment).where(Payment.provider == "payme", Payment.external_id == tid)
                         .with_for_update())).scalar_one_or_none()
    if p is None:
        raise PaymeError(-31003)
    return p


def _expire_if_stale(p: Payment, now_ms: int) -> bool:
    pm = _pm(p)
    if pm.get("state") == CREATED and now_ms - pm["create_time"] > TIMEOUT_MS:
        _save(p, {**pm, "state": CANCELLED_BEFORE, "cancel_time": now_ms, "reason": REASON_TIMEOUT})
        p.status = PaymentStatus.CANCELLED
        return True
    return False


async def check_perform(s, settings, params, bus, now_ms):
    _check_order(await _order(s, params), params)
    return {"allow": True}


async def create_transaction(s, settings, params, bus, now_ms):
    tid, ptime = params.get("id"), params.get("time")
    if not isinstance(tid, str) or not tid or not isinstance(ptime, int):
        raise PaymeError(-32600)
    existing = (await s.execute(select(Payment).where(Payment.provider == "payme", Payment.external_id == tid)
                                .with_for_update())).scalar_one_or_none()
    if existing is not None:
        pm = _pm(existing)
        if pm.get("state") != CREATED:
            raise PaymeError(-31008)
        if _expire_if_stale(existing, now_ms):
            raise PaymeError(-31008)
        return {"create_time": pm["create_time"], "transaction": str(existing.id), "state": CREATED}
    p = await _order(s, params)
    _check_order(p, params)
    p.external_id = tid
    _save(p, {"id": tid, "time": ptime, "create_time": now_ms, "state": CREATED, "reason": None})
    return {"create_time": now_ms, "transaction": str(p.id), "state": CREATED}


async def perform_transaction(s, settings, params, bus, now_ms):
    p = await _tx(s, params)
    pm = _pm(p)
    if pm["state"] == PERFORMED:
        return {"transaction": str(p.id), "perform_time": pm["perform_time"], "state": PERFORMED}
    if pm["state"] != CREATED or _expire_if_stale(p, now_ms):
        raise PaymeError(-31008)
    try:
        await service.confirm(s, p, bus=bus, external_id=pm["id"])
    except Conflict as e:
        raise PaymeError(-31008) from e
    _save(p, {**pm, "state": PERFORMED, "perform_time": now_ms})
    return {"transaction": str(p.id), "perform_time": now_ms, "state": PERFORMED}


async def cancel_transaction(s, settings, params, bus, now_ms):
    p = await _tx(s, params)
    pm = _pm(p)
    reason = params.get("reason")
    if pm["state"] in (CANCELLED_BEFORE, CANCELLED_AFTER):
        return {"transaction": str(p.id), "cancel_time": pm["cancel_time"], "state": pm["state"]}
    if pm["state"] == CREATED:
        _save(p, {**pm, "state": CANCELLED_BEFORE, "cancel_time": now_ms, "reason": reason})
        p.status = PaymentStatus.CANCELLED
        return {"transaction": str(p.id), "cancel_time": now_ms, "state": CANCELLED_BEFORE}
    await service.revert_paid(s, p)                        # performed -> refund: take the subscription days back
    _save(p, {**pm, "state": CANCELLED_AFTER, "cancel_time": now_ms, "reason": reason})
    return {"transaction": str(p.id), "cancel_time": now_ms, "state": CANCELLED_AFTER}


async def check_transaction(s, settings, params, bus, now_ms):
    return _tx_view(await _tx(s, params))


async def get_statement(s, settings, params, bus, now_ms):
    lo, hi = params.get("from"), params.get("to")
    if not isinstance(lo, int) or not isinstance(hi, int):
        raise PaymeError(-32600)
    rows = (await s.execute(select(Payment).where(Payment.provider == "payme", Payment.external_id.is_not(None))
                            .order_by(Payment.id))).scalars().all()
    out = []
    for p in rows:
        pm = _pm(p)
        if pm and lo <= pm["time"] <= hi:
            out.append({"id": pm["id"], "time": pm["time"], "amount": p.amount * 100,
                        "account": {ACCOUNT_FIELD: str(p.id)}, **_tx_view(p)})
    return {"transactions": out}


METHODS = {"CheckPerformTransaction": check_perform, "CreateTransaction": create_transaction,
           "PerformTransaction": perform_transaction, "CancelTransaction": cancel_transaction,
           "CheckTransaction": check_transaction, "GetStatement": get_statement}


def _error(code: int, rpc_id: Any, data: Any = None) -> dict:
    err: dict = {"code": code, "message": MESSAGES.get(code, MESSAGES[-31008])}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "error": err, "id": rpc_id}


async def handle(s: AsyncSession, settings: Settings, body: bytes | str | dict, authorization: str | None,
                 bus=None, now_ms: int | None = None) -> dict:
    """Process one JSON-RPC call. Always returns a JSON-RPC envelope (HTTP 200), errors included."""
    rpc_id = None
    try:
        data = json.loads(body) if isinstance(body, (bytes, str)) else body
        if isinstance(data, dict):
            rpc_id = data.get("id")
    except ValueError:
        data = None
    if not check_auth(authorization, settings.payme_key):
        return _error(-32504, rpc_id)
    if data is None:
        return _error(-32700, None)
    if not isinstance(data, dict) or not isinstance(data.get("method"), str):
        return _error(-32600, rpc_id)
    fn = METHODS.get(data["method"])
    if fn is None:
        return _error(-32601, rpc_id, data["method"])
    params = data.get("params")
    if not isinstance(params, dict):
        return _error(-32600, rpc_id)
    try:
        return {"jsonrpc": "2.0", "result": await fn(s, settings, params, bus, now_ms or _now_ms()), "id": rpc_id}
    except PaymeError as e:
        return _error(e.code, rpc_id, e.data)
