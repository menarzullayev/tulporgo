"""Encrypted server copy of driver documents (decision 57, personal-data localisation decision 43).

The licence and the tech passport are kept TWICE: as a Telegram file id in the private storage chat (as before) and
here, Fernet-encrypted, in our own database in Uzbekistan. Only the ciphertext is stored; the key is
`Settings.documents_encryption_key` (separate from the userbot key).

Development: with an empty key `store` does nothing and returns None. PRODUCTION DEPLOY MUST SET
`TULPORGO_DOCUMENTS_ENCRYPTION_KEY`, otherwise no server copy is made. A non-empty but malformed key is an error.

Document bytes and the key are never logged and never put into error messages.
"""
import hashlib
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import rowcount, utcnow
from ..errors import DomainError, Invalid, NotFound
from ..models import Driver, DriverDocument

Kind = Literal["license", "techpass"]
KINDS: tuple[str, ...] = ("license", "techpass")
MAX_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp", "application/pdf")


class DocumentTooLarge(DomainError):
    status = 413


class DocumentsNotConfigured(DomainError):
    status = 500


class DocumentUnreadable(DomainError):
    status = 500


def enabled(settings: Settings) -> bool:
    """True when a server copy is configured (a key is set)."""
    return bool(settings.documents_encryption_key)


def sniff(data: bytes) -> str | None:
    """Content type from the file's magic bytes; the declared type is never trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _fernet(settings: Settings) -> Fernet:
    try:
        return Fernet(settings.documents_encryption_key.encode())
    except (ValueError, TypeError) as e:
        raise DocumentsNotConfigured("documents_key_invalid", "documents_encryption_key is not a Fernet key") from e


async def store(s: AsyncSession, driver: Driver, kind: str, content: bytes, content_type: str,
                settings: Settings) -> DriverDocument | None:
    """Encrypt and keep `content` as the driver's `kind` document, replacing an earlier one.
    Returns None (and does nothing) when no key is configured."""
    if not enabled(settings):
        return None
    if kind not in KINDS:
        raise Invalid("bad_document_kind")
    if not content:
        raise Invalid("bad_file_type")
    if len(content) > MAX_BYTES:
        raise DocumentTooLarge("file_too_large")
    real = sniff(content)
    if real is None or real not in ALLOWED_TYPES or content_type != real:
        raise Invalid("bad_file_type")
    token = _fernet(settings).encrypt(content)
    row = (await s.execute(select(DriverDocument).where(DriverDocument.driver_id == driver.id,
                                                        DriverDocument.kind == kind))).scalar_one_or_none()
    if row is None:
        row = DriverDocument(driver_id=driver.id, kind=kind, content_type=real, size=len(content),
                             sha256=hashlib.sha256(content).hexdigest(), data_encrypted=token)
        s.add(row)
    else:
        row.content_type, row.size, row.data_encrypted = real, len(content), token
        row.sha256 = hashlib.sha256(content).hexdigest()
        row.created_at = utcnow()
    await s.flush()
    return row


async def has_server_copy(s: AsyncSession, driver: Driver) -> bool:
    return bool(await s.scalar(select(func.count()).select_from(DriverDocument)
                               .where(DriverDocument.driver_id == driver.id)))


async def load(s: AsyncSession, driver: Driver, kind: str, settings: Settings) -> tuple[bytes, str]:
    """Decrypt a stored document -> (bytes, content type). Admin use only: the caller checks the role."""
    if not enabled(settings):
        raise DocumentsNotConfigured("documents_key_missing")
    row = (await s.execute(select(DriverDocument).where(DriverDocument.driver_id == driver.id,
                                                        DriverDocument.kind == kind))).scalar_one_or_none()
    if row is None:
        raise NotFound("document_not_found")
    try:
        data = _fernet(settings).decrypt(row.data_encrypted)
    except InvalidToken as e:
        raise DocumentUnreadable("document_unreadable") from e
    if hashlib.sha256(data).hexdigest() != row.sha256:
        raise DocumentUnreadable("document_unreadable")
    return data, row.content_type


async def delete_for_driver(s: AsyncSession, driver: Driver) -> int:
    """Remove every server copy of the driver's documents; returns the number of rows."""
    res = await s.execute(delete(DriverDocument).where(DriverDocument.driver_id == driver.id))
    return rowcount(res)
