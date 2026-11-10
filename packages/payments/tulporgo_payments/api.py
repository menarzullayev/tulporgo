"""FastAPI router mounted by apps/api at /api/payments: Mini App checkout + Click / Payme callbacks.

Callbacks authenticate by signature (Click) or Basic auth (Payme) and never trust client-sent amounts: the amount of
record is always the stored Payment, compared with what the provider reports."""
import json
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_api.deps import current_user, get_bus, get_session, get_settings
from tulporgo_core.config import Settings
from tulporgo_core.models import User
from tulporgo_core.services import billing

from . import service
from .providers import available_providers, click, payme
from .providers.stars import http_tg_call

router = APIRouter(prefix="/api/payments", tags=["payments"])


class CheckoutIn(BaseModel):
    plan: str
    months: int = 1
    provider: str
    recurring: bool = False


def get_tg_call(request: Request, settings: Settings = Depends(get_settings)):
    """Bot API caller for createInvoiceLink; tests set `app.state.tg_call` to a fake."""
    return getattr(request.app.state, "tg_call", None) or http_tg_call(settings.bot_token)


@router.get("/providers")
async def providers(settings: Settings = Depends(get_settings), user: User = Depends(current_user)):
    return {"free_period": billing.in_free_period(settings), "providers": available_providers(settings)}


@router.post("/checkout")
async def checkout(body: CheckoutIn, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                   settings: Settings = Depends(get_settings), tg_call=Depends(get_tg_call)):
    """Start a payment for the signed-in driver. 409 `free_period` while everything is free (decision 44)."""
    c = await service.start_checkout(s, user, settings, body.provider, body.plan, body.months,
                                     recurring=body.recurring, tg_call=tg_call)
    return {"payment_id": c.payment.id, "provider": c.payment.provider, "amount": c.payment.amount,
            "currency": c.payment.currency, "plan": c.payment.plan, "months": c.payment.months, "start": c.start}


async def _params(request: Request) -> dict:
    """Click posts application/x-www-form-urlencoded; JSON is accepted too (used by tests and some proxies)."""
    raw = await request.body()
    if "json" in request.headers.get("content-type", ""):
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
    return dict(parse_qsl(raw.decode("utf-8", "replace"), keep_blank_values=True))


@router.post("/click/prepare")
async def click_prepare(request: Request, s: AsyncSession = Depends(get_session),
                        settings: Settings = Depends(get_settings), bus=Depends(get_bus)):
    params = await _params(request)
    params["action"] = params.get("action", "0")
    if params["action"] != "0":                            # this endpoint only serves Prepare
        return JSONResponse(click.reply(params, click.ACTION_NOT_FOUND))
    return JSONResponse(await click.handle(s, settings, params, bus))


@router.post("/click/complete")
async def click_complete(request: Request, s: AsyncSession = Depends(get_session),
                         settings: Settings = Depends(get_settings), bus=Depends(get_bus)):
    params = await _params(request)
    params["action"] = params.get("action", "1")
    if params["action"] != "1":
        return JSONResponse(click.reply(params, click.ACTION_NOT_FOUND))
    return JSONResponse(await click.handle(s, settings, params, bus))


@router.post("/payme")
async def payme_rpc(request: Request, s: AsyncSession = Depends(get_session),
                    settings: Settings = Depends(get_settings), bus=Depends(get_bus),
                    authorization: str | None = Header(default=None)):
    return JSONResponse(await payme.handle(s, settings, await request.body(), authorization, bus))
