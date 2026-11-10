"""Encrypted server copy of driver documents (decision 57): at rest, replace, validation, no key, privacy."""
import hashlib
from datetime import datetime, timedelta

import pytest
from conftest import make_driver
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from tulporgo_core.config import Settings
from tulporgo_core.errors import Invalid, NotFound
from tulporgo_core.models import DriverDocument
from tulporgo_core.services import documents, privacy
from tulporgo_core.services.documents import DocumentsNotConfigured, DocumentTooLarge, DocumentUnreadable

JPEG = b"\xff\xd8\xff\xe0" + b"SECRET-LICENCE-PIXELS" * 8
PNG = b"\x89PNG\r\n\x1a\n" + b"SECRET-TECHPASS-PIXELS" * 8
PDF = b"%PDF-1.7\n" + b"x" * 40


@pytest.fixture
def keyed():
    return Settings(database_url="sqlite+aiosqlite:///:memory:", documents_encryption_key=Fernet.generate_key().decode())


async def rows(s):
    return list((await s.execute(select(DriverDocument))).scalars())


async def test_stored_encrypted_and_round_trips(s, keyed):
    d = await make_driver(s, keyed)
    row = await documents.store(s, d, "license", JPEG, "image/jpeg", keyed)
    assert row is not None and row.size == len(JPEG) and row.sha256 == hashlib.sha256(JPEG).hexdigest()
    await s.commit()
    raw = (await rows(s))[0].data_encrypted
    assert raw != JPEG and b"SECRET-LICENCE" not in raw                  # ciphertext only at rest
    assert Fernet(keyed.documents_encryption_key.encode()).decrypt(raw) == JPEG
    assert await documents.load(s, d, "license", keyed) == (JPEG, "image/jpeg")


async def test_reupload_replaces_the_row(s, keyed):
    d = await make_driver(s, keyed)
    await documents.store(s, d, "license", JPEG, "image/jpeg", keyed)
    await documents.store(s, d, "license", PNG, "image/png", keyed)
    await documents.store(s, d, "techpass", PDF, "application/pdf", keyed)
    assert len(await rows(s)) == 2                                         # unique (driver, kind)
    data, ctype = await documents.load(s, d, "license", keyed)
    assert data == PNG and ctype == "image/png"
    assert (await rows(s))[0].sha256 == hashlib.sha256(PNG).hexdigest()


async def test_wrong_magic_bytes_refused(s, keyed):
    d = await make_driver(s, keyed)
    with pytest.raises(Invalid):
        await documents.store(s, d, "license", b"MZ\x90\x00 not an image", "image/jpeg", keyed)     # exe claims jpeg
    with pytest.raises(Invalid):
        await documents.store(s, d, "license", PNG, "image/jpeg", keyed)                           # type mismatch
    with pytest.raises(Invalid):
        await documents.store(s, d, "license", b"GIF89a" + b"\x00" * 20, "image/gif", keyed)       # not allowed
    with pytest.raises(Invalid):
        await documents.store(s, d, "selfie", JPEG, "image/jpeg", keyed)                           # unknown kind
    assert await rows(s) == []


async def test_too_large_refused_and_limit_is_inclusive(s, keyed):
    d = await make_driver(s, keyed)
    ok = JPEG + b"\x00" * (documents.MAX_BYTES - len(JPEG))
    assert await documents.store(s, d, "license", ok, "image/jpeg", keyed) is not None
    with pytest.raises(DocumentTooLarge):
        await documents.store(s, d, "techpass", ok + b"\x00", "image/jpeg", keyed)
    assert len(await rows(s)) == 1


async def test_no_key_stores_nothing(s, settings):
    d = await make_driver(s, settings)
    assert await documents.store(s, d, "license", JPEG, "image/jpeg", settings) is None
    assert await rows(s) == [] and documents.enabled(settings) is False
    with pytest.raises(DocumentsNotConfigured):
        await documents.load(s, d, "license", settings)


async def test_malformed_key_is_an_error_not_a_silent_skip(s):
    bad = Settings(database_url="sqlite+aiosqlite:///:memory:", documents_encryption_key="not-a-fernet-key")
    d = await make_driver(s, bad)
    with pytest.raises(DocumentsNotConfigured) as e:
        await documents.store(s, d, "license", JPEG, "image/jpeg", bad)
    assert "not-a-fernet-key" not in str(e.value)                          # the key never appears in errors


async def test_load_missing_and_wrong_key(s, keyed):
    d = await make_driver(s, keyed)
    with pytest.raises(NotFound):
        await documents.load(s, d, "license", keyed)
    await documents.store(s, d, "license", JPEG, "image/jpeg", keyed)
    other = Settings(database_url="sqlite+aiosqlite:///:memory:", documents_encryption_key=Fernet.generate_key().decode())
    with pytest.raises(DocumentUnreadable):
        await documents.load(s, d, "license", other)


async def test_privacy_delete_removes_rows_and_export_has_flag_but_no_bytes(s, keyed):
    d = await make_driver(s, keyed)
    other = await make_driver(s, keyed)
    for dr in (d, other):
        await documents.store(s, dr, "license", JPEG, "image/jpeg", keyed)
        await documents.store(s, dr, "techpass", PNG, "image/png", keyed)
    d.license_file_id = d.techpass_file_id = "FID"
    exported = await privacy.export_user_data(s, d.user)
    assert exported["driver"]["documents_on_server"] is True
    blob = repr(exported)
    assert "SECRET" not in blob and "gAAAA" not in blob and keyed.documents_encryption_key not in blob
    assert (await privacy.export_user_data(s, (await make_driver(s, keyed)).user))["driver"]["documents_on_server"] is False

    await privacy.delete_user_data(s, d.user)
    left = await rows(s)
    assert [r.driver_id for r in left] == [other.id, other.id]               # only the other driver's rows remain
    assert await s.scalar(select(func.count()).select_from(DriverDocument).where(DriverDocument.driver_id == d.id)) == 0
    assert (await privacy.export_user_data(s, other.user))["driver"]["documents_on_server"] is True


# ---- decision 63: a rejected copy is kept 7 days, then purged ----------------------------------------------------

T0 = datetime(2026, 11, 11, 12, 0)


async def test_rejected_copy_is_kept_seven_days_then_purged(s, keyed):
    d = await make_driver(s, keyed)
    await documents.store(s, d, "license", JPEG, "image/jpeg", keyed)
    await documents.store(s, d, "techpass", PNG, "image/png", keyed)
    assert await documents.mark_rejected(s, d, keyed, now=T0) == 2
    assert {r.delete_after for r in await rows(s)} == {T0 + timedelta(days=7)}
    # negative: one minute before the end nothing goes, and the copy can still be read for a second look
    assert await documents.purge_rejected(s, now=T0 + timedelta(days=7, minutes=-1)) == 0
    assert await documents.load(s, d, "license", keyed) == (JPEG, "image/jpeg")
    assert await documents.purge_rejected(s, now=T0 + timedelta(days=7)) == 2
    assert await rows(s) == []


async def test_keep_days_comes_from_the_settings(s, keyed):
    d = await make_driver(s, keyed)
    await documents.store(s, d, "license", JPEG, "image/jpeg", keyed)
    await documents.mark_rejected(s, d, keyed.model_copy(update={"rejected_documents_keep_days": 2}), now=T0)
    assert (await rows(s))[0].delete_after == T0 + timedelta(days=2)


async def test_a_new_upload_clears_the_rejection(s, keyed):
    d = await make_driver(s, keyed)
    await documents.store(s, d, "license", JPEG, "image/jpeg", keyed)
    await documents.store(s, d, "techpass", PNG, "image/png", keyed)
    await documents.mark_rejected(s, d, keyed, now=T0)
    await documents.store(s, d, "license", JPEG, "image/jpeg", keyed)       # the driver sends a clearer licence
    assert await documents.purge_rejected(s, now=T0 + timedelta(days=30)) == 1   # only the old tech passport goes
    assert [r.kind for r in await rows(s)] == ["license"]


async def test_purge_never_touches_documents_that_were_not_rejected(s, keyed):
    d, other = await make_driver(s, keyed), await make_driver(s, keyed)
    for dr in (d, other):
        await documents.store(s, dr, "license", JPEG, "image/jpeg", keyed)
    await documents.mark_rejected(s, d, keyed, now=T0)
    assert await documents.purge_rejected(s, now=T0 + timedelta(days=365)) == 1
    assert [r.driver_id for r in await rows(s)] == [other.id]                 # the unmarked driver's copy stays
