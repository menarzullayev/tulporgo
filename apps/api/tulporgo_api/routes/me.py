"""Profile endpoints: GET/PATCH /api/me, GET /api/plans."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import Lang
from tulporgo_core.errors import Invalid
from tulporgo_core.models import User
from tulporgo_core.services import billing, drivers
from tulporgo_core.services.users import ensure_referral_code

from ..deps import current_user, get_session, get_settings
from .common import driver_card, referral_link

router = APIRouter(tags=["me"])


class MePatch(BaseModel):
    lang: str | None = None
    is_woman: bool | None = None


async def me_view(s: AsyncSession, user: User, settings: Settings) -> dict:
    d = await drivers.get_driver(s, user)
    if d:
        await ensure_referral_code(s, user)                  # drivers always have a referral link (decision 52)
    return {
        "id": user.id, "first_name": user.first_name, "username": user.username, "lang": user.lang,
        "is_woman": user.is_woman, "phone_set": bool(user.phone), "is_admin": user.is_admin,
        "driver": driver_card(d, settings) if d else None,
        "free_period": billing.in_free_period(settings),
        "free_period_until": settings.free_period_until.isoformat() if settings.free_period_until else None,
        "referral_link": referral_link(settings, user) if d else None,
    }


@router.get("/me")
async def get_me(user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                 settings: Settings = Depends(get_settings)):
    return await me_view(s, user, settings)


@router.patch("/me")
async def patch_me(body: MePatch, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                   settings: Settings = Depends(get_settings)):
    if body.lang is not None:
        if body.lang not in {lg.value for lg in Lang}:
            raise Invalid("bad_lang")
        user.lang = body.lang
    if body.is_woman is not None:
        user.is_woman = body.is_woman
    return await me_view(s, user, settings)


@router.get("/plans")
async def plans(_: User = Depends(current_user), settings: Settings = Depends(get_settings)):
    """Plan list from core billing (decision 10) so prices live in one place."""
    return {
        "free_period": billing.in_free_period(settings),
        "free_period_until": settings.free_period_until.isoformat() if settings.free_period_until else None,
        "trial_days": settings.trial_days,
        "plans": [{"plan": p.plan.value, "price_uzs": p.price_uzs, "max_groups": p.max_groups,
                   "autopost": p.autopost, "priority": p.priority} for p in billing.PLANS.values()],
    }
