"""FastAPI dependencies (contract for W2/W3/W4 routers): settings, DB session, event bus, Telegram Mini App auth.

Auth: the Mini App sends `Authorization: tma <initData>`; we verify the HMAC exactly as documented in
core.telegram.org/bots/webapps ("Validating data received via the Mini App") and reject data older than 24 h.
Outside Telegram (Login with Telegram, off unless configured) the site sends `Authorization: tgweb <token>`, a short
HMAC-signed session issued by routes/auth_telegram.py (see web_session.py).
"""
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope
from tulporgo_core.models import User
from tulporgo_core.services.users import get_or_create_user

from . import web_session

MAX_AGE = 24 * 3600


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_bus(request: Request):
    return request.app.state.bus


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with session_scope(request.app.state.maker) as s:
        yield s


def validate_init_data(init_data: str, bot_token: str, now: float | None = None) -> dict:
    """Return the parsed fields (user decoded from JSON) or raise ValueError."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received = pairs.pop("hash", None)
    if not received:
        raise ValueError("no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise ValueError("bad hash")
    if (now or time.time()) - int(pairs.get("auth_date", "0")) > MAX_AGE:
        raise ValueError("expired")
    if "user" in pairs:
        pairs["user"] = json.loads(pairs["user"])
    return pairs


async def current_user(authorization: str = Header(default=""), settings: Settings = Depends(get_settings),
                       s: AsyncSession = Depends(get_session)) -> User:
    scheme, _, data = authorization.partition(" ")
    scheme = scheme.lower()
    if scheme == "tgweb" and data:
        if not settings.login_client_secret:           # Login with Telegram is off: no such sessions exist
            raise HTTPException(401, "web login is not enabled")
        try:
            tg_id = web_session.verify(data.strip(), settings.bot_token)
        except web_session.InvalidSession as e:
            raise HTTPException(401, f"invalid web session: {e}") from e
        user = await get_or_create_user(s, tg_id)
        if user.is_blocked:
            raise HTTPException(403, "blocked")
        return user
    if scheme != "tma" or not data:
        raise HTTPException(401, "missing Mini App auth")
    try:
        fields = validate_init_data(data, settings.bot_token)
    except ValueError as e:
        raise HTTPException(401, f"invalid Mini App auth: {e}") from e
    u = fields.get("user") or {}
    if not u.get("id"):
        raise HTTPException(401, "no user")
    user = await get_or_create_user(s, int(u["id"]), u.get("username"), u.get("first_name"), u.get("language_code"))
    if user.is_blocked:
        raise HTTPException(403, "blocked")
    return user
