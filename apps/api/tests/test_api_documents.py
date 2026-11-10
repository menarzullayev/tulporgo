"""Driver documents also kept encrypted on our server (decision 57): API upload path."""
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from test_api_driver import JPEG, PNG, files, register
from tulporgo_core.models import Driver, DriverDocument
from tulporgo_core.services import documents

pytest_plugins = ["api_fixtures"]


@pytest.fixture
def keyed(env):
    env.settings.documents_encryption_key = Fernet.generate_key().decode()
    return env


def doc_rows(env):
    async def go(s):
        return [(r.driver_id, r.kind, r.sha256, bytes(r.data_encrypted)) for r in (await s.execute(
            select(DriverDocument).order_by(DriverDocument.kind))).scalars()]
    return env.db(go)


def file_ids(env, driver_id):
    async def go(s):
        d = await s.get(Driver, driver_id)
        return d.license_file_id, d.techpass_file_id
    return env.db(go)


def test_both_copies_are_stored_and_ciphertext_at_rest(keyed, H):
    driver_id = register(keyed, H).json()["driver"]["id"]
    res = keyed.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=PNG))
    assert res.status_code == 200
    assert file_ids(keyed, driver_id) == ("FILE-ID-1", "FILE-ID-2")                 # Telegram copy as before
    rows = doc_rows(keyed)
    assert [(r[0], r[1]) for r in rows] == [(driver_id, "license"), (driver_id, "techpass")]
    assert all(r[3] not in (JPEG, PNG) for r in rows)                                # not plaintext
    f = Fernet(keyed.settings.documents_encryption_key.encode())
    assert [f.decrypt(r[3]) for r in rows] == [JPEG, PNG]


def test_reupload_replaces_the_server_copy(keyed, H):
    register(keyed, H)
    keyed.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=JPEG))
    keyed.client.post("/api/driver/documents", headers=H(7), files=files(license=PNG, techpass=PNG))
    rows = doc_rows(keyed)
    assert len(rows) == 2
    f = Fernet(keyed.settings.documents_encryption_key.encode())
    assert [f.decrypt(r[3]) for r in rows] == [PNG, PNG]


def test_no_key_means_no_server_copy_but_upload_still_works(env, H):
    register(env, H)
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=PNG))
    assert res.status_code == 200
    assert doc_rows(env) == []


def test_server_copy_failure_fails_the_request_and_keeps_no_half_state(keyed, H, monkeypatch, caplog):
    driver_id = register(keyed, H).json()["driver"]["id"]

    async def boom(*a, **kw):
        raise documents.DocumentsNotConfigured("documents_key_invalid")
    monkeypatch.setattr(documents, "store", boom)
    res = keyed.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=PNG))
    assert res.status_code == 500 and res.json()["error"] == "documents_key_invalid"
    assert len(keyed.uploader.calls) == 2                                            # the Telegram copy may stay...
    assert file_ids(keyed, driver_id) == (None, None)                               # ...but nothing is submitted
    assert doc_rows(keyed) == []
    assert any("server copy" in r.message and str(driver_id) in r.message for r in caplog.records)
    assert JPEG.decode("latin1") not in caplog.text


def test_malformed_key_fails_the_request(env, H):
    env.settings.documents_encryption_key = "garbage"
    register(env, H)
    res = env.client.post("/api/driver/documents", headers=H(7), files=files(license=JPEG, techpass=PNG))
    assert res.status_code == 500 and res.json()["error"] == "documents_key_invalid"
    assert doc_rows(env) == []
