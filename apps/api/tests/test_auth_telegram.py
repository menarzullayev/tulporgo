"""Login with Telegram (OpenID Connect): no network. A generated RSA key + JWKS and a fake token endpoint
(httpx.MockTransport) stand in for oauth.telegram.org."""
import base64
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from api_fixtures import TOKEN, auth
from cryptography.hazmat.primitives.asymmetric import rsa
from tulporgo_api import telegram_oidc, web_session
from tulporgo_api.routes.auth_telegram import (
    InMemoryLoginStore,
    LoginAttempt,
    get_oidc_client,
    safe_return_to,
)
from tulporgo_core.config import Settings

pytest_plugins = ["api_fixtures"]  # shared fixtures (env)

CLIENT_ID = TOKEN.partition(":")[0]
SECRET = "client-secret-from-botfather"
KID = "test-key-1"


def make_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


KEY, OTHER_KEY = make_key(), make_key()


def jwks_of(key, kid=KID) -> dict:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return {"keys": [{**jwk, "kid": kid, "use": "sig", "alg": "RS256"}]}


class FakeTelegram:
    """The token and JWKS endpoints of oauth.telegram.org."""

    def __init__(self) -> None:
        self.id_token: str | None = None
        self.token_status = 200
        self.token_requests: list[httpx.Request] = []
        self.jwks_fetches = 0
        self.jwks = jwks_of(KEY)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url == telegram_oidc.TOKEN_URL:
            self.token_requests.append(request)
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "x", "token_type": "Bearer", "id_token": self.id_token})
        if request.url == telegram_oidc.JWKS_URL:
            self.jwks_fetches += 1
            return httpx.Response(200, json=self.jwks)
        return httpx.Response(404)


def sign_id_token(nonce_value: str, key=KEY, **over) -> str:
    claims = {"iss": telegram_oidc.ISSUER, "aud": CLIENT_ID, "sub": "sub-opaque", "id": 777001, "name": "Ali Valiyev",
              "preferred_username": "ali_v", "iat": int(time.time()), "exp": int(time.time()) + 600, "nonce": nonce_value}
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": KID})


class Login:
    """Drives /start -> (fake Telegram) -> /callback."""

    def __init__(self, env, tg: FakeTelegram) -> None:
        self.env, self.tg = env, tg
        self.client = env.client

    def start(self, **params):
        res = self.client.get("/api/auth/telegram/start", params=params, follow_redirects=False)
        if res.status_code != 302:
            return res, {}
        return res, {k: v[0] for k, v in parse_qs(urlsplit(res.headers["location"]).query).items()}

    def callback(self, **params):
        return self.client.get("/api/auth/telegram/callback", params=params, follow_redirects=False)

    def run(self, mint=sign_id_token, return_to=None, **callback_extra):
        """Full flow; `mint(nonce)` builds the id_token Telegram returns."""
        _, q = self.start(**({"return_to": return_to} if return_to else {}))
        self.tg.id_token = mint(q["nonce"])
        return self.callback(code="auth-code", state=q["state"], **callback_extra)


def fragment(res) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(res.headers["location"]).fragment).items()}


@pytest.fixture
def tg():
    return FakeTelegram()


@pytest.fixture
def login(env, tg):
    env.settings.login_client_secret = SECRET
    client = telegram_oidc.OidcClient(transport=httpx.MockTransport(tg.handler))
    env.client.app.dependency_overrides[get_oidc_client] = lambda: client
    return Login(env, tg)


# ---------- off by default ----------

def test_config_reports_disabled_without_a_secret(env):
    assert env.settings.login_client_secret == ""
    assert env.client.get("/api/auth/telegram/config").json() == {"enabled": False, "client_id": None}


def test_disabled_start_and_callback_are_404(env):
    assert env.client.get("/api/auth/telegram/start", follow_redirects=False).status_code == 404
    res = env.client.get("/api/auth/telegram/callback", params={"code": "c", "state": "s"}, follow_redirects=False)
    assert res.status_code == 404 and res.json()["error"] == "login_disabled"


def test_disabled_rejects_even_a_correctly_signed_tgweb_token(env):
    token = web_session.issue(5, TOKEN, 1)
    res = env.client.get("/api/me", headers={"Authorization": f"tgweb {token}"})
    assert res.status_code == 401


def test_config_when_enabled(login):
    assert login.client.get("/api/auth/telegram/config").json() == {"enabled": True, "client_id": CLIENT_ID}


# ---------- happy path ----------

def test_start_redirects_to_telegram_with_pkce_state_and_nonce(login):
    res, q = login.start()
    loc = urlsplit(res.headers["location"])
    assert f"{loc.scheme}://{loc.netloc}{loc.path}" == "https://oauth.telegram.org/auth"
    assert q["client_id"] == CLIENT_ID and q["response_type"] == "code"
    assert "openid" in q["scope"].split()
    assert q["redirect_uri"] == "https://tulporgo.uz/api/auth/telegram/callback"
    assert q["code_challenge_method"] == "S256" and q["state"] and q["nonce"] and q["code_challenge"]


def test_happy_path_logs_in_and_the_token_authenticates(login, tg, env):
    res, q = login.start(return_to="/app/#/profile")
    tg.id_token = sign_id_token(q["nonce"])
    res = login.callback(code="auth-code", state=q["state"])
    assert res.status_code == 302
    path = urlsplit(res.headers["location"]).path
    assert path == "/app/"
    frag = fragment(res)
    assert frag["route"] == "/profile" and "login_error" not in frag
    assert res.headers["cache-control"] == "no-store"

    # the code exchange: HTTP Basic client_id:secret, PKCE verifier matching the challenge, same redirect_uri
    req = tg.token_requests[0]
    assert req.headers["authorization"] == "Basic " + base64.b64encode(f"{CLIENT_ID}:{SECRET}".encode()).decode()
    form = parse_qs(req.content.decode())
    assert form["grant_type"] == ["authorization_code"] and form["code"] == ["auth-code"]
    assert telegram_oidc.pkce_challenge(form["code_verifier"][0]) == q["code_challenge"]
    assert form["redirect_uri"] == [q["redirect_uri"]]

    me = env.client.get("/api/me", headers={"Authorization": f"tgweb {frag['tgweb']}"})
    assert me.status_code == 200
    assert me.json()["first_name"] == "Ali Valiyev" and me.json()["username"] == "ali_v"


def test_default_return_to_is_the_app_root(login):
    res = login.run()
    assert urlsplit(res.headers["location"]).path == "/app/"
    assert "tgweb" in fragment(res)


def test_jwks_is_cached_between_logins(login, tg):
    login.run()
    login.run()
    assert tg.jwks_fetches == 1


# ---------- state ----------

def test_missing_unknown_and_replayed_state_are_refused(login, tg):
    assert login.callback(code="c").status_code == 400
    assert login.callback(code="c", state="never-issued").status_code == 400
    _, q = login.start()
    tg.id_token = sign_id_token(q["nonce"])
    assert login.callback(code="c", state=q["state"]).status_code == 302
    replay = login.callback(code="c", state=q["state"])
    assert replay.status_code == 400 and replay.json()["error"] == "bad_state"
    assert len(tg.token_requests) == 1                      # the replay never reached the token endpoint


def test_store_entries_expire_and_are_single_use():
    now = [0.0]
    store = InMemoryLoginStore(clock=lambda: now[0])
    store.put("s1", LoginAttempt("v", "n", "/app/", 600.0))
    store.put("s2", LoginAttempt("v", "n", "/app/", 600.0))
    assert store.pop("s1") is not None and store.pop("s1") is None
    now[0] = 601.0
    assert store.pop("s2") is None                          # negative: expired after the 10 minute TTL


def test_user_cancelling_at_telegram_returns_to_the_app_without_a_session(login):
    _, q = login.start()
    res = login.callback(error="access_denied", state=q["state"])
    assert fragment(res) == {"login_error": "denied"}


# ---------- id_token verification (negatives) ----------

@pytest.mark.parametrize(("case", "mint", "code"), [
    ("wrong_iss", lambda n: sign_id_token(n, iss="https://evil.example"), "bad_issuer"),
    ("wrong_aud", lambda n: sign_id_token(n, aud="999999"), "bad_audience"),
    ("expired", lambda n: sign_id_token(n, exp=int(time.time()) - 10), "expired"),
    ("bad_signature", lambda n: sign_id_token(n, key=OTHER_KEY), "bad_token"),
    ("wrong_nonce", lambda n: sign_id_token("some-other-nonce"), "bad_nonce"),
    ("missing_nonce", lambda n: sign_id_token(n, nonce=None), "bad_nonce"),
    ("alg_none", lambda n: jwt.encode({"iss": telegram_oidc.ISSUER, "aud": CLIENT_ID, "id": 1, "sub": "s", "nonce": n,
                                      "exp": int(time.time()) + 60}, None, algorithm="none"), "bad_alg"),
    ("alg_hs256", lambda n: jwt.encode({"iss": telegram_oidc.ISSUER, "aud": CLIENT_ID, "id": 1, "sub": "s", "nonce": n,
                                       "exp": int(time.time()) + 60}, "x" * 40, algorithm="HS256"), "bad_alg"),
    ("garbage", lambda n: "not.a.jwt", "bad_token"),
    ("no_id_claim", lambda n: sign_id_token(n, id=None), "bad_token"),
])
def test_bad_id_tokens_never_log_in(login, env, case, mint, code):
    res = login.run(mint=mint)
    assert res.status_code == 302
    assert fragment(res) == {"login_error": code}, case
    assert "tgweb" not in res.headers["location"]


def test_token_endpoint_rejection_is_reported(login, tg):
    tg.token_status = 400
    _, q = login.start()
    res = login.callback(code="c", state=q["state"])
    assert fragment(res) == {"login_error": "token_rejected"}


# ---------- return_to (open redirect) ----------

@pytest.mark.parametrize("bad", [
    "https://evil.example/app/", "//evil.example/app/", "/\\evil.example", "/other", "/apple", "/app/../evil",
    "/app/%2e%2e/evil", "javascript:alert(1)", "app/", "/app/\r\nSet-Cookie: x=1", "/app\\..\\evil",
])
def test_open_redirects_in_return_to_are_refused(login, bad):
    res, _ = login.start(return_to=bad)
    assert res.status_code == 422 and res.json()["error"] == "bad_return_to"


@pytest.mark.parametrize("good", ["/app", "/app/", "/app/#/trips", "/app/?page=userbot", "/app/#/trip/5"])
def test_return_to_inside_the_app_is_accepted(good):
    assert safe_return_to(good, Settings()) == good


def test_return_to_follows_the_configured_miniapp_url():
    s = Settings(miniapp_url="https://example.org/mini")
    assert safe_return_to("/mini/#/x", s) == "/mini/#/x"
    with pytest.raises(Exception, match="bad_return_to"):
        safe_return_to("/app/", s)


# ---------- web session token on the API ----------

def test_forged_expired_and_garbage_tgweb_tokens_are_401(login, env):
    good = web_session.issue(31, TOKEN, 1)
    h = lambda t: {"Authorization": f"tgweb {t}"}  # noqa: E731
    assert env.client.get("/api/me", headers=h(good)).status_code == 200
    forged = [
        web_session.issue(31, "999:OTHER-BOT-TOKEN", 1),                       # signed with another key
        good.split(".")[0] + "." + good.split(".")[1][:-2] + "AA",             # tampered signature
        web_session.issue(31, TOKEN, 1).split(".")[0].replace("A", "B", 1) + "." + good.split(".")[1],
        web_session.issue(31, TOKEN, 1, now=time.time() - 3 * 3600),           # expired an hour ago
        "garbage", "a.b", ".", "",
    ]
    for t in forged:
        assert env.client.get("/api/me", headers=h(t)).status_code == 401, t


def test_a_tgweb_token_for_a_blocked_user_is_403(login, env):
    env.make_user(40, is_blocked=True)
    token = web_session.issue(40, TOKEN, 1)
    assert env.client.get("/api/me", headers={"Authorization": f"tgweb {token}"}).status_code == 403


def test_a_tgweb_token_cannot_be_replayed_as_init_data_and_vice_versa(login, env):
    token = web_session.issue(31, TOKEN, 1)
    assert env.client.get("/api/me", headers={"Authorization": f"tma {token}"}).status_code == 401
    assert env.client.get("/api/me", headers={"Authorization": "tgweb " + auth(31)["Authorization"][4:]}).status_code == 401


def test_mini_app_init_data_auth_still_works(login, env):
    assert env.client.get("/api/me", headers=auth(31)).status_code == 200          # login enabled
    env.settings.login_client_secret = ""
    assert env.client.get("/api/me", headers=auth(31)).status_code == 200          # and disabled
    assert env.client.get("/api/me").status_code == 401


def test_session_token_roundtrip_and_expiry():
    t = web_session.issue(123, TOKEN, 72, now=1000.0)
    assert web_session.verify(t, TOKEN, now=1000.0 + 72 * 3600 - 1) == 123
    with pytest.raises(web_session.InvalidSession):
        web_session.verify(t, TOKEN, now=1000.0 + 72 * 3600)
