"""Referral (decision 52): personal link `?start=ref_<CODE>`; when the invited driver is VERIFIED both get +7 days
and the inviter gets the "Elchi" (ambassador) tag. Verification, not sign-up, triggers the bonus — fake sign-ups pay
nothing."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..errors import Invalid
from ..events import ReferralGranted
from ..models import Driver, ReferralBonus, User
from . import billing


def code_from_start(arg: str | None) -> str | None:
    if arg and arg.startswith("ref_") and 4 < len(arg) <= 20:
        return arg[4:].upper()
    return None


async def link(s: AsyncSession, user: User, code: str) -> User | None:
    """Remember who invited `user`. Ignored if already linked; self-invites are rejected."""
    if user.referred_by_id:
        return None
    inviter = (await s.execute(select(User).where(User.referral_code == code.upper()))).scalar_one_or_none()
    if inviter is None:
        return None
    if inviter.id == user.id:
        raise Invalid("self_referral")
    user.referred_by_id = inviter.id
    return inviter


async def grant_on_verification(s: AsyncSession, driver: Driver, settings: Settings, bus=None) -> ReferralBonus | None:
    user = await s.get(User, driver.user_id)
    if not user or not user.referred_by_id:
        return None
    if (await s.execute(select(ReferralBonus.id).where(ReferralBonus.referred_id == user.id))).first():
        return None                                        # once per invited driver
    inviter_driver = (await s.execute(select(Driver).where(Driver.user_id == user.referred_by_id))).scalar_one_or_none()
    days = settings.referral_bonus_days
    bonus = ReferralBonus(referrer_id=user.referred_by_id, referred_id=user.id, days=days)
    s.add(bonus)
    billing.extend(driver, days)
    if inviter_driver:
        billing.extend(inviter_driver, days)
        inviter_driver.ambassador = True
    await s.flush()
    if bus:
        await bus.publish(ReferralGranted(user.referred_by_id, user.id, days))
    return bonus
