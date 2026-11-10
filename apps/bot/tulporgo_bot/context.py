"""Shared handler context (contract for W1 bot, W2 userbot router, W4 payments router).

Every handler receives these keyword arguments from `ContextMiddleware`:
    session: AsyncSession   — one transaction per update, committed after the handler, rolled back on error
    settings: Settings
    bus: event bus (InMemoryBus | RedisBus) — events published by a handler are delivered AFTER the commit, so
         subscribers (which open their own sessions) always see the data
    user: tulporgo_core.models.User (created on first contact; last_seen updated)
    lang: tulporgo_core.enums.Lang  — the user's chosen language, else from Telegram's language_code
    t: callable(key, **kw) -> str   — i18n bound to `lang`
Blocked users (decision 13) get no handler at all.
"""
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope
from tulporgo_core.i18n import lang_of, t
from tulporgo_core.services.users import get_or_create_user


class DeferredBus:
    """Collects events during one update and publishes them only after the transaction committed."""

    def __init__(self, inner) -> None:
        self.inner, self.queue = inner, []

    async def publish(self, event) -> None:
        self.queue.append(event)

    def discard(self) -> None:
        self.queue.clear()

    async def flush(self) -> None:
        events, self.queue = self.queue, []
        for event in events:
            await self.inner.publish(event)


class ContextMiddleware(BaseMiddleware):
    def __init__(self, maker: async_sessionmaker[AsyncSession], settings: Settings, bus) -> None:
        self.maker, self.settings, self.bus = maker, settings, bus

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user = data.get("event_from_user")
        deferred = DeferredBus(self.bus)
        async with session_scope(self.maker) as session:
            data.update(session=session, settings=self.settings, bus=deferred)
            if tg_user is not None and not tg_user.is_bot:
                user = await get_or_create_user(session, tg_user.id, tg_user.username, tg_user.first_name)
                if user.is_blocked and user.tg_id not in self.settings.admin_ids:
                    return None
                if user.tg_id in self.settings.admin_ids:
                    user.is_admin = True
                lang = lang_of(user.lang or tg_user.language_code)
                data.update(user=user, lang=lang, t=partial(t, lang=lang))
            result = await handler(event, data)
        await deferred.flush()                       # committed — now the subscribers may read the new rows
        return result
