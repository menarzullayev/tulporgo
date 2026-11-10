"""Inner middleware: domain errors become a short localized alert instead of a stack trace; the transaction of the
failed update is rolled back and its queued events are dropped, so a refused action never leaves half a change."""
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject
from tulporgo_core.errors import DomainError
from tulporgo_core.i18n import t as i18n_t

from .common import err_text

log = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        try:
            return await handler(event, data)
        except DomainError as e:
            log.info("refused: %s", e.code)
            await self._report(event, data, lambda t: err_text(e.code, t))
        except TelegramBadRequest as e:
            if "not modified" in str(e).lower():              # same card pressed twice: nothing to do
                return None
            log.exception("telegram rejected a request")
            await self._report(event, data, lambda t: t("common.error"))
        except Exception:                                      # noqa: BLE001
            log.exception("unhandled error in a handler")
            await self._report(event, data, lambda t: t("common.error"))
        return None

    @staticmethod
    async def _report(event: TelegramObject, data: dict[str, Any], text_of) -> None:
        if (session := data.get("session")) is not None:
            await session.rollback()
        if (bus := data.get("bus")) is not None and hasattr(bus, "discard"):
            bus.discard()
        text = text_of(data.get("t") or (lambda key, **kw: i18n_t(key, None, **kw)))
        try:
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer(text, show_alert=True)
                except TelegramAPIError:                       # already answered: fall back to a chat message
                    if isinstance(event.message, Message):
                        await event.message.answer(text)
            elif isinstance(event, Message):
                await event.answer(text)
        except TelegramAPIError as e:
            log.warning("could not report an error to the user: %s", e)
