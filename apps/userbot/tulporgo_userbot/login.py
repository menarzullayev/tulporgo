"""Phone login state machine for the Mini App form: phone -> code -> (2FA password).

The code and the password pass through memory only: they are handed straight to Telethon and are never stored, put in
exceptions or logged. The half-open Telethon client of a pending login lives in this process's memory (one API
process / sticky routing is assumed; a restart simply asks the driver to start the login again).
"""
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from telethon import errors as tg

from .client import ClientFactory, UserbotClient
from .config import LOGIN_START_COOLDOWN_SECONDS, LOGIN_TTL_SECONDS, MAX_LOGIN_ATTEMPTS
from .errors import Forbidden, Invalid, NotFound, TooMany

log = logging.getLogger(__name__)


@dataclass
class _Pending:
    client: UserbotClient
    phone: str
    code_hash: str
    started: float
    attempts: int = 0
    password_needed: bool = False


@dataclass(frozen=True)
class LoginResult:
    status: str                       # "ok" | "password_required"
    session: str | None = field(default=None, repr=False)     # StringSession — handed to finish_login() only
    tg_user_id: int | None = None


class LoginRegistry:
    def __init__(self, factory: ClientFactory, clock: Callable[[], float] = time.monotonic) -> None:
        self._factory = factory
        self._clock = clock
        self._pending: dict[int, _Pending] = {}
        self._last_start: dict[int, float] = {}

    async def _drop(self, key: int) -> None:
        p = self._pending.pop(key, None)
        if p is not None:
            try:
                await p.client.disconnect()
            except Exception:                                    # noqa: BLE001
                log.debug("disconnect of a dropped login failed")

    def _get(self, key: int) -> _Pending:
        p = self._pending.get(key)
        if p is None or self._clock() - p.started > LOGIN_TTL_SECONDS:
            self._pending.pop(key, None)
            raise NotFound("no_pending_login", "start the login again")
        return p

    async def start(self, key: int, phone: str) -> None:
        now = self._clock()
        last = self._last_start.get(key)
        if last is not None and now - last < LOGIN_START_COOLDOWN_SECONDS:
            raise TooMany("login_cooldown", "wait a minute before asking for a new code")
        self._last_start[key] = now
        await self._drop(key)
        client = self._factory(None)
        await client.connect()
        try:
            code_hash = await client.send_code(phone)
        except tg.FloodWaitError as e:                           # never retried; the driver is told to wait
            await client.disconnect()
            raise TooMany("flood_wait", f"Telegram asked to wait {e.seconds} s") from None
        except tg.PhoneNumberInvalidError:
            await client.disconnect()
            raise Invalid("bad_phone") from None
        except tg.PhoneNumberBannedError:
            await client.disconnect()
            raise Forbidden("phone_banned") from None
        except Exception:
            await client.disconnect()
            raise
        self._pending[key] = _Pending(client, phone, code_hash, now)

    def _count_failure(self, key: int, p: _Pending) -> None:
        p.attempts += 1
        if p.attempts >= MAX_LOGIN_ATTEMPTS:
            self._pending.pop(key, None)
            raise TooMany("too_many_attempts", "login cancelled; start again")

    async def _finish(self, key: int, p: _Pending, tg_id: int) -> LoginResult:
        res = LoginResult("ok", p.client.session_string(), tg_id)
        await self._drop(key)                                    # the worker opens its own client from the session
        return res

    async def submit_code(self, key: int, code: str) -> LoginResult:
        p = self._get(key)
        digits = "".join(ch for ch in (code or "") if ch.isdigit())
        if not 4 <= len(digits) <= 8:
            raise Invalid("bad_code")
        try:
            tg_id = await p.client.sign_in_code(p.phone, digits, p.code_hash)
        except tg.SessionPasswordNeededError:
            p.password_needed = True
            return LoginResult("password_required")
        except tg.PhoneCodeInvalidError:
            self._count_failure(key, p)
            raise Invalid("bad_code") from None
        except tg.PhoneCodeExpiredError:
            await self._drop(key)
            raise Invalid("code_expired", "start the login again") from None
        except tg.FloodWaitError as e:
            await self._drop(key)
            raise TooMany("flood_wait", f"Telegram asked to wait {e.seconds} s") from None
        return await self._finish(key, p, tg_id)

    async def submit_password(self, key: int, password: str) -> LoginResult:
        p = self._get(key)
        if not p.password_needed:
            raise Forbidden("password_not_requested")
        if not password:
            raise Invalid("bad_password")
        try:
            tg_id = await p.client.sign_in_password(password)
        except tg.PasswordHashInvalidError:
            self._count_failure(key, p)
            raise Invalid("bad_password") from None
        except tg.FloodWaitError as e:
            await self._drop(key)
            raise TooMany("flood_wait", f"Telegram asked to wait {e.seconds} s") from None
        return await self._finish(key, p, tg_id)

    async def cancel(self, key: int) -> None:
        await self._drop(key)

    def pending(self, key: int) -> bool:
        p = self._pending.get(key)
        return p is not None and self._clock() - p.started <= LOGIN_TTL_SECONDS
