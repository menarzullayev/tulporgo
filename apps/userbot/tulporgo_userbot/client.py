"""Telethon boundary. Everything that touches the network lives behind `UserbotClient`, so tests use a fake client and
no real login ever happens. Telethon error classes are NOT wrapped: the scheduler and the login API catch them.

Safety: the real client is built with `flood_sleep_threshold=0`. By default Telethon silently sleeps and retries on
short FloodWaits (<= 60 s) — that would hide Telegram's limit from us. With 0 every FloodWaitError is raised, so the
scheduler records it and stops (decision 8: FloodWait is never bypassed).
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .config import APP_VERSION, DEVICE_MODEL, TelegramApiSettings
from .errors import NotConfigured


@dataclass(frozen=True)
class GroupInfo:
    chat_id: int
    title: str


@dataclass(frozen=True)
class GroupMessage:
    """A new text message in a group the account is in (decision 73). Handed over in memory only, never stored."""
    chat_id: int                        # marked id (-100…) as in UserbotGroup.chat_id
    message_id: int
    sender_id: int | None
    sender_username: str | None
    chat_username: str | None           # public groups: t.me/<username>/<id> links
    text: str
    sent_at: datetime | None = None     # when Telegram says it was posted (aware UTC) — for latency checks


GroupMessageHandler = Callable[[GroupMessage], Awaitable[None]]


@dataclass(frozen=True)
class GroupDeletion:
    """Messages deleted in a group (decision 75: the passenger found a taxi). Telegram names the chat only for
    supergroups; for basic groups `chat_id` is None and the ids are unique within the account's message box."""
    chat_id: int | None
    message_ids: tuple[int, ...]


GroupDeletionHandler = Callable[[GroupDeletion], Awaitable[None]]


class UserbotClient(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def is_authorized(self) -> bool: ...
    async def send_code(self, phone: str) -> str: ...                  # returns phone_code_hash
    async def sign_in_code(self, phone: str, code: str, code_hash: str) -> int: ...   # returns Telegram user id
    async def sign_in_password(self, password: str) -> int: ...
    def session_string(self) -> str: ...
    async def list_groups(self) -> list[GroupInfo]: ...
    async def send_message(self, chat_id: int, text: str) -> int: ...  # returns message id
    async def log_out(self) -> None: ...
    def on_group_message(self, handler: GroupMessageHandler) -> None: ...    # live reading; never sends anything
    def on_group_delete(self, handler: GroupDeletionHandler) -> None: ...    # decision 75


# session string (None = brand new, unauthorised session) -> client
ClientFactory = Callable[[str | None], UserbotClient]


def can_write(entity: Any) -> bool:
    """A group/supergroup where the account can post: not left/kicked/deactivated, not muted by default or personally
    restricted — unless the account is the creator or an admin."""
    if any(getattr(entity, flag, False) for flag in ("left", "kicked", "deactivated")):
        return False
    if getattr(entity, "creator", False) or getattr(entity, "admin_rights", None):
        return True
    for attr in ("banned_rights", "default_banned_rights"):
        rights = getattr(entity, attr, None)
        if rights is not None and getattr(rights, "send_messages", False):
            return False
    return True


class TelethonClient:
    def __init__(self, session: str | None, api_id: int, api_hash: str) -> None:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        self._client = TelegramClient(StringSession(session or ""), api_id, api_hash, device_model=DEVICE_MODEL,
                                      app_version=APP_VERSION, flood_sleep_threshold=0)

    async def connect(self) -> None:
        await self._client.connect()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def is_authorized(self) -> bool:
        return await self._client.is_user_authorized()

    async def send_code(self, phone: str) -> str:
        sent = await self._client.send_code_request(phone)
        return sent.phone_code_hash

    async def sign_in_code(self, phone: str, code: str, code_hash: str) -> int:
        me = await self._client.sign_in(phone, code, phone_code_hash=code_hash)
        return me.id

    async def sign_in_password(self, password: str) -> int:
        me = await self._client.sign_in(password=password)
        return me.id

    def session_string(self) -> str:
        return self._client.session.save()

    async def list_groups(self) -> list[GroupInfo]:
        groups = []
        async for d in self._client.iter_dialogs():
            if d.is_group and can_write(d.entity):
                groups.append(GroupInfo(chat_id=d.id, title=(d.name or "")[:256]))
        return groups

    async def send_message(self, chat_id: int, text: str) -> int:
        try:
            msg = await self._client.send_message(chat_id, text, link_preview=False, parse_mode=None)
        except ValueError:                                  # entity not in the in-memory cache after a restart
            await self._client.get_dialogs()                # prime the cache once; NOT a retry of a Telegram error
            msg = await self._client.send_message(chat_id, text, link_preview=False, parse_mode=None)
        return msg.id

    async def log_out(self) -> None:
        await self._client.log_out()                         # terminates the session on Telegram's side

    def on_group_message(self, handler: GroupMessageHandler) -> None:
        """New group messages from Telethon's update stream. Uses only the entities that come with the update (no
        extra requests), does not mark anything as read and never answers."""
        from telethon import events

        async def _on(event) -> None:
            if event.is_private or not event.raw_text or event.out:
                return
            sender, chat = event.sender, event.chat
            await handler(GroupMessage(event.chat_id, event.id, event.sender_id, getattr(sender, "username", None),
                                       getattr(chat, "username", None), event.raw_text, event.date))

        self._client.add_event_handler(_on, events.NewMessage(incoming=True))

    def on_group_delete(self, handler: GroupDeletionHandler) -> None:
        """Deletions from the same update stream; no extra requests."""
        from telethon import events

        async def _on(event) -> None:
            if event.deleted_ids:
                await handler(GroupDeletion(event.chat_id, tuple(event.deleted_ids)))

        self._client.add_event_handler(_on, events.MessageDeleted())


def make_telethon_factory(api: TelegramApiSettings | None = None) -> ClientFactory:
    api = api or TelegramApiSettings()
    if not api.configured:
        raise NotConfigured("telegram_api_missing", "TULPORGO_TELEGRAM_API_ID / _HASH are not set")

    def factory(session: str | None) -> UserbotClient:
        return TelethonClient(session, api.telegram_api_id, api.telegram_api_hash)
    return factory
