"""Login with Telegram for the site opened OUTSIDE Telegram (GOAL.md §4): OpenID Connect code flow with PKCE.

OFF unless `Settings.login_client_secret` is set: `/start` and `/callback` answer 404 and `/config` reports
`enabled: false`. On success the browser is redirected back into the Mini App with a web session token in the URL
fragment (never sent to a server); the Mini App then sends `Authorization: tgweb <token>` (see deps.current_user).
"""
import time
from dataclasses import dataclass
from typing import Annotated, Protocol
from urllib.parse import unquote, urlencode, urlsplit

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.errors import DomainError, Invalid, NotFound
from tulporgo_core.services.users import get_or_create_user

from .. import telegram_oidc as oidc
from .. import web_session
from ..deps import get_session, get_settings

router = APIRouter(prefix="/auth/telegram", tags=["auth"])

STATE_TTL = 600
MAX_PENDING = 10_000


@dataclass(frozen=True)
class LoginAttempt:
    verifier: str
    nonce: str
    return_to: str
    expires: float


class LoginStore(Protocol):
    """Pending logins keyed by `state`. The API runs as one process, so the default is in memory; swap this
    interface (e.g. for Redis) if it is ever scaled out."""

    def put(self, state: str, attempt: LoginAttempt) -> None: ...
    def pop(self, state: str) -> LoginAttempt | None: ...


class InMemoryLoginStore:
    def __init__(self, clock=time.monotonic) -> None:
        self._items: dict[str, LoginAttempt] = {}
        self._clock = clock

    def put(self, state: str, attempt: LoginAttempt) -> None:
        if len(self._items) >= MAX_PENDING:
            now = self._clock()
            self._items = {k: v for k, v in self._items.items() if v.expires > now}
            if len(self._items) >= MAX_PENDING:            # still full: drop the oldest, never grow without bound
                self._items.pop(next(iter(self._items)))
        self._items[state] = attempt

    def pop(self, state: str) -> LoginAttempt | None:      # single use: a replayed state finds nothing
        attempt = self._items.pop(state, None)
        return attempt if attempt and attempt.expires > self._clock() else None


def get_login_store(request: Request) -> LoginStore:
    if not hasattr(request.app.state, "login_store"):
        request.app.state.login_store = InMemoryLoginStore()
    return request.app.state.login_store


def get_oidc_client(request: Request) -> oidc.OidcClient:
    if not hasattr(request.app.state, "oidc_client"):
        request.app.state.oidc_client = oidc.OidcClient()
    return request.app.state.oidc_client


def client_id(settings: Settings) -> str:
    return settings.bot_token.partition(":")[0]


def enabled(settings: Settings) -> bool:
    return bool(settings.login_client_secret and client_id(settings).isdigit())


def require_enabled(settings: Settings = Depends(get_settings)) -> Settings:
    if not enabled(settings):
        raise NotFound("login_disabled")
    return settings


def app_origin(settings: Settings) -> str:
    u = urlsplit(settings.miniapp_url)
    return f"{u.scheme}://{u.netloc}"


def redirect_uri(settings: Settings) -> str:
    return f"{app_origin(settings)}/api/auth/telegram/callback"


def safe_return_to(value: str | None, settings: Settings) -> str:
    """A relative path inside the Mini App (e.g. `/app/#/profile`); anything else is refused (no open redirect)."""
    prefix = urlsplit(settings.miniapp_url).path.rstrip("/") or "/app"
    if value is None or value == "":
        return prefix + "/"
    if len(value) > 512 or any(ord(c) < 32 or c in "\\\x7f" for c in value) or not value.startswith("/") \
            or value.startswith("//"):
        raise Invalid("bad_return_to")
    u = urlsplit(value)
    path = unquote(u.path)
    if u.scheme or u.netloc or "\\" in path or not (path == prefix or path.startswith(prefix + "/")) \
            or ".." in path.split("/") or path.startswith("//"):
        raise Invalid("bad_return_to")
    return value


def back_to_app(return_to: str, **fragment: str) -> RedirectResponse:
    """Redirect into the Mini App; `return_to`'s own `#/route` travels as `route`, the Mini App uses hash routing."""
    u = urlsplit(return_to)
    frag = dict(fragment)
    if u.fragment:
        frag["route"] = u.fragment
    target = u.path + (f"?{u.query}" if u.query else "") + "#" + urlencode(frag)
    return RedirectResponse(target, status_code=302, headers={"Cache-Control": "no-store"})


class LoginConfig(BaseModel):
    enabled: bool
    client_id: str | None = None


@router.get("/config", response_model=LoginConfig)
async def login_config(settings: Settings = Depends(get_settings)) -> LoginConfig:
    on = enabled(settings)
    return LoginConfig(enabled=on, client_id=client_id(settings) if on else None)


@router.get("/start", status_code=302, response_class=RedirectResponse, responses={302: {"description": "To Telegram"}})
async def login_start(return_to: Annotated[str | None, Query(max_length=512)] = None,
                      settings: Settings = Depends(require_enabled),
                      store: LoginStore = Depends(get_login_store)) -> RedirectResponse:
    target = safe_return_to(return_to, settings)
    state, nonce, verifier = oidc.new_secret(), oidc.new_secret(), oidc.new_secret()
    store.put(state, LoginAttempt(verifier, nonce, target, time.monotonic() + STATE_TTL))
    url = oidc.authorization_url(client_id(settings), redirect_uri(settings), state, nonce, verifier,
                                 oidc.scope(settings.login_bot_access))
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


@router.get("/callback", status_code=302, response_class=RedirectResponse, responses={302: {"description": "To the app"}})
async def login_callback(code: Annotated[str | None, Query(max_length=2048)] = None,
                         state: Annotated[str | None, Query(max_length=256)] = None,
                         error: Annotated[str | None, Query(max_length=128)] = None,
                         settings: Settings = Depends(require_enabled),
                         store: LoginStore = Depends(get_login_store),
                         client: oidc.OidcClient = Depends(get_oidc_client),
                         s: AsyncSession = Depends(get_session)) -> RedirectResponse:
    attempt = store.pop(state) if state else None
    if attempt is None:                                    # unknown, expired or replayed: nowhere safe to redirect
        raise DomainError("bad_state")
    if error or not code:
        return back_to_app(attempt.return_to, login_error="denied")
    cid = client_id(settings)
    try:
        id_token = await client.exchange_code(code, attempt.verifier, redirect_uri(settings), cid,
                                              settings.login_client_secret)
        claims = await client.verified_claims(id_token, cid, attempt.nonce)
        tg_id = int(claims["id"])
    except oidc.OidcError as e:
        return back_to_app(attempt.return_to, login_error=e.code)
    except (KeyError, ValueError, TypeError):
        return back_to_app(attempt.return_to, login_error="bad_token")
    await get_or_create_user(s, tg_id, claims.get("preferred_username"), claims.get("name"))
    token = web_session.issue(tg_id, settings.bot_token, settings.web_session_hours)
    return back_to_app(attempt.return_to, tgweb=token)
