"""Refresh the stored group list from Telegram (used by the Mini App API and the bot). A short-lived client is built
from the decrypted session, used once and disconnected — the session never leaves memory."""
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from telethon import errors as tg
from tulporgo_core.config import Settings
from tulporgo_core.db import utcnow
from tulporgo_core.enums import UserbotStatus
from tulporgo_core.models import UserbotAccount, UserbotGroup

from . import service
from .client import ClientFactory
from .crypto import decrypt_session
from .errors import Forbidden, TooMany

log = logging.getLogger(__name__)
DEAD = (tg.AuthKeyUnregisteredError, tg.UserDeactivatedError, tg.UserDeactivatedBanError, tg.SessionRevokedError,
        tg.SessionExpiredError, tg.AuthKeyDuplicatedError)


async def refresh_groups(s: AsyncSession, account: UserbotAccount, settings: Settings, factory: ClientFactory,
                         bus=None, now: datetime | None = None) -> list[UserbotGroup]:
    now = now or utcnow()
    if not account.session_encrypted or account.status in (UserbotStatus.NEEDS_LOGIN, UserbotStatus.STOPPED):
        raise Forbidden("not_connected")
    if account.flood_until and account.flood_until > now:
        raise TooMany("flood_wait", "Telegram asked to wait")      # never bypassed, not even for a read
    client = factory(decrypt_session(settings, account.session_encrypted))
    try:
        await client.connect()
        found = await client.list_groups()
    except tg.FloodWaitError as e:
        account.flood_until = now + timedelta(seconds=int(e.seconds or 0))
        if account.status == UserbotStatus.CONNECTED:
            account.status = UserbotStatus.FLOOD_WAIT
        await s.commit()                                           # keep the flood state even though we raise
        raise TooMany("flood_wait", f"Telegram asked to wait {e.seconds} s") from None
    except DEAD as e:
        await service.stop_account(s, account, type(e).__name__.removesuffix("Error"), bus, drop_session=True)
        await s.commit()
        raise Forbidden("session_revoked", "Telegram ended this session; connect again") from None
    finally:
        try:
            await client.disconnect()
        except Exception:                                          # noqa: BLE001
            log.debug("disconnect after group sync failed")
    return await service.sync_groups(s, account, found)
