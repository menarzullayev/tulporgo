"""Telegram Login = OpenID Connect (core.telegram.org/widgets/login): authorization code + PKCE (S256).

Pure helpers plus `OidcClient` (token exchange and cached JWKS over httpx). Tests inject an httpx transport, so no
network is needed.
"""
import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

ISSUER = "https://oauth.telegram.org"
AUTH_URL = f"{ISSUER}/auth"
TOKEN_URL = f"{ISSUER}/token"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
ALGORITHMS = ("RS256", "ES256", "EdDSA", "ES256K")        # never "none" and never HMAC (the key would be public)
SCOPE = "openid profile"
# decision 65: the user may let the bot write to them after a site login, so trip notices reach people who never
# opened @tulporgobot. Telegram adds no claim for it; a refused message is still just a 403 in delivery.
BOT_ACCESS = "telegram:bot_access"
# decision 66: the user's Telegram-verified phone number (claim `phone_number`), asked with the user's consent
PHONE = "phone"
JWKS_TTL = 3600
JWKS_MIN_REFETCH = 60


class OidcError(Exception):
    """Login failed; `code` is a stable machine-readable reason."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def scope(bot_access: bool, phone: bool = False) -> str:
    return " ".join([SCOPE, *([PHONE] if phone else []), *([BOT_ACCESS] if bot_access else [])])


def verified_phone(claims: dict[str, Any]) -> str | None:
    """The phone number from the id_token, or None when it is absent or Telegram says it is not verified."""
    phone = claims.get("phone_number")
    if not isinstance(phone, str) or not phone.strip() or claims.get("phone_number_verified") is False:
        return None
    return phone


def authorization_url(client_id: str, redirect_uri: str, state: str, nonce: str, verifier: str,
                      scopes: str = SCOPE) -> str:
    q = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": scopes,
         "state": state, "nonce": nonce, "code_challenge": pkce_challenge(verifier), "code_challenge_method": "S256"}
    return f"{AUTH_URL}?{urlencode(q)}"


def verify_id_token(token: str, jwks: dict[str, Any], client_id: str, nonce: str) -> dict[str, Any]:
    """Check signature, iss, aud, exp and nonce. Raises OidcError."""
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg not in ALGORITHMS:
            raise OidcError("bad_alg")
        kid = header.get("kid")
        keys = [k for k in jwks.get("keys", []) if kid is None or k.get("kid") == kid]
        if not keys:
            raise OidcError("unknown_key")
        key = jwt.PyJWK(keys[0]).key
        claims = jwt.decode(token, key, algorithms=[alg], audience=client_id, issuer=ISSUER,
                            options={"require": ["exp", "iss", "aud", "sub"]})
    except OidcError:
        raise
    except jwt.ExpiredSignatureError as e:
        raise OidcError("expired") from e
    except jwt.InvalidAudienceError as e:
        raise OidcError("bad_audience") from e
    except jwt.InvalidIssuerError as e:
        raise OidcError("bad_issuer") from e
    except (jwt.PyJWTError, ValueError, TypeError) as e:
        raise OidcError("bad_token") from e
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OidcError("bad_nonce")
    return claims


class OidcClient:
    """Talks to oauth.telegram.org. One instance per process (JWKS cache); replaceable in tests via a transport."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 10.0) -> None:
        self._transport, self._timeout = transport, timeout
        self._jwks: dict[str, Any] | None = None
        self._fetched = 0.0

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=self._timeout)

    async def exchange_code(self, code: str, verifier: str, redirect_uri: str, client_id: str, client_secret: str) -> str:
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                "client_id": client_id, "code_verifier": verifier}
        try:
            async with self._http() as c:
                res = await c.post(TOKEN_URL, data=data, auth=(client_id, client_secret))
            body = res.json()
        except (httpx.HTTPError, ValueError) as e:
            raise OidcError("token_unreachable") from e
        token = body.get("id_token") if isinstance(body, dict) else None
        if res.status_code != 200 or not isinstance(token, str):
            raise OidcError("token_rejected")
        return token

    async def jwks(self, refresh: bool = False) -> dict[str, Any]:
        age = time.monotonic() - self._fetched
        if self._jwks is not None and age < JWKS_TTL and not (refresh and age > JWKS_MIN_REFETCH):
            return self._jwks
        try:
            async with self._http() as c:
                res = await c.get(JWKS_URL)
            res.raise_for_status()
            data = res.json()
        except (httpx.HTTPError, ValueError) as e:
            raise OidcError("jwks_unreachable") from e
        if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
            raise OidcError("jwks_unreachable")
        self._jwks, self._fetched = data, time.monotonic()
        return data

    async def verified_claims(self, id_token: str, client_id: str, nonce: str) -> dict[str, Any]:
        try:
            return verify_id_token(id_token, await self.jwks(), client_id, nonce)
        except OidcError as e:
            if e.code != "unknown_key":
                raise
        return verify_id_token(id_token, await self.jwks(refresh=True), client_id, nonce)   # key rotation
