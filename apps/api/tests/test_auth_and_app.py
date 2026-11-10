import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from tulporgo_api.deps import validate_init_data
from tulporgo_api.main import create_app
from tulporgo_core.config import Settings

TOKEN = "123456:TEST"


def sign(fields: dict, token: str = TOKEN) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()})


def fields(age: int = 0):
    return {"auth_date": str(int(time.time()) - age), "query_id": "AAE", "user": json.dumps({"id": 42, "first_name": "Ali"})}


def test_valid_init_data():
    d = validate_init_data(sign(fields()), TOKEN)
    assert d["user"]["id"] == 42


@pytest.mark.parametrize("bad", ["tampered", "other_token", "expired", "no_hash"])
def test_invalid_init_data_rejected(bad):
    # negative: every forgery path must fail
    data = sign(fields(age=25 * 3600 if bad == "expired" else 0), "999:OTHER" if bad == "other_token" else TOKEN)
    if bad == "tampered":
        data = data.replace("Ali", "Bob")
    if bad == "no_hash":
        data = urlencode(fields())
    with pytest.raises(ValueError):
        validate_init_data(data, TOKEN)


def test_health_and_auth_required(tmp_path):
    app = create_app(Settings(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'a.db').as_posix()}", bot_token=TOKEN))
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"ok": True}
