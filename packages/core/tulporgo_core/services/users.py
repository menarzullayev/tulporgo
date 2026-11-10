import re
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import utcnow
from ..errors import Forbidden, Invalid
from ..models import User

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"     # no 0/O/1/I


async def get_or_create_user(s: AsyncSession, tg_id: int, username: str | None = None,
                             first_name: str | None = None, lang: str | None = None) -> User:
    u = (await s.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
    if u is None:
        u = User(tg_id=tg_id, username=username, first_name=first_name, lang=lang)
        s.add(u)
        await s.flush()
    else:
        u.username, u.first_name = username or u.username, first_name or u.first_name
        if lang and not u.lang:
            u.lang = lang
    u.last_seen_at = utcnow()
    return u


def normalize_phone(phone: str) -> str:
    """'+998 90 123-45-67' / '901234567' → '+998901234567'. Uzbek mobile numbers only."""
    d = re.sub(r"\D", "", phone or "")
    if len(d) == 9:
        d = "998" + d
    if not re.fullmatch(r"998\d{9}", d):
        raise Invalid("bad_phone", "Uzbek phone number expected")
    return "+" + d


async def set_phone(s: AsyncSession, user: User, phone: str) -> User:
    user.phone = normalize_phone(phone)
    return user


async def ensure_referral_code(s: AsyncSession, user: User) -> str:
    while not user.referral_code:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not (await s.execute(select(User.id).where(User.referral_code == code))).first():
            user.referral_code = code
    return user.referral_code


async def set_blocked(s: AsyncSession, admin: User, user: User, blocked: bool) -> User:
    if not admin.is_admin:
        raise Forbidden("admin_only")
    if user.id == admin.id:
        raise Invalid("cannot_block_self")
    user.is_blocked = blocked
    return user
