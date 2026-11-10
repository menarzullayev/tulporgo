"""Short-lived web session tokens for the site opened outside Telegram ("Login with Telegram").

Stateless: `base64url(json{sub, exp}) . base64url(HMAC-SHA256)`. The key is derived from the bot token with a fixed
label, so it differs from the Mini App initData key and a token cannot be used as anything else. Sent as
`Authorization: tgweb <token>`.
"""
import base64
import hashlib
import hmac
import json
import time

LABEL = b"tulporgo-web-session-v1"


class InvalidSession(ValueError):
    pass


def _key(bot_token: str) -> bytes:
    return hmac.new(bot_token.encode(), LABEL, hashlib.sha256).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(tg_id: int, bot_token: str, hours: int, now: float | None = None) -> str:
    exp = int((now or time.time()) + hours * 3600)
    payload = _b64(json.dumps({"sub": tg_id, "exp": exp}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_key(bot_token), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify(token: str, bot_token: str, now: float | None = None) -> int:
    """Return the Telegram user id or raise InvalidSession."""
    if not bot_token:
        raise InvalidSession("not configured")
    payload, sep, sig = token.partition(".")
    if not sep or not payload or not sig:
        raise InvalidSession("malformed")
    expected = _b64(hmac.new(_key(bot_token), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise InvalidSession("bad signature")
    try:
        data = json.loads(_unb64(payload))
        tg_id, exp = int(data["sub"]), int(data["exp"])
    except (ValueError, KeyError, TypeError) as e:
        raise InvalidSession("malformed") from e
    if (now or time.time()) >= exp:
        raise InvalidSession("expired")
    return tg_id
