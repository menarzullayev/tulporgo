"""Outgoing messages: rate limit (~30 msg/s), retry on 429, plain-text fallbacks for old clients.

Every send to a user other than the one who is chatting with the bot goes through here (notifications, cards)."""
import asyncio
import logging
import re
import time

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage, SendRichMessage
from aiogram.types import InlineKeyboardMarkup, InputRichMessage, Message
from tulporgo_core import emoji

log = logging.getLogger(__name__)
TAGS = re.compile(r"<[^>]+>")
sleep = asyncio.sleep                      # replaced in tests


class Limiter:
    def __init__(self, rate: float = 25.0) -> None:
        self.rate, self._next, self._lock = rate, 0.0, asyncio.Lock()

    async def wait(self) -> None:
        if self.rate <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + 1.0 / self.rate
        if delay > 0:
            await sleep(delay)


LIMITER = Limiter()


def strip_tags(html: str) -> str:
    """Plain-text fallback: drop tags (links keep their text), unescape the entities we emit."""
    return TAGS.sub("", html).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


async def call(bot: Bot, method, retries: int = 3):
    """Run a method under the rate limit; honour 429 `retry_after`. Returns None if the user blocked the bot."""
    for attempt in range(retries):
        await LIMITER.wait()
        try:
            return await bot(method)
        except TelegramRetryAfter as e:
            if attempt == retries - 1:
                raise
            await sleep(e.retry_after)
        except TelegramForbiddenError:
            return None


async def send(bot: Bot, chat_id: int, html: str, markup: InlineKeyboardMarkup | None = None, **kw) -> Message | None:
    html = emoji.decorate(html)
    try:
        return await call(bot, SendMessage(chat_id=chat_id, text=html, parse_mode="HTML", reply_markup=markup, **kw))
    except TelegramBadRequest as e:
        if "parse" not in str(e).lower() and "entit" not in str(e).lower():
            raise
        log.warning("html rejected, resending as plain text: %s", e)
        return await call(bot, SendMessage(chat_id=chat_id, text=strip_tags(html), parse_mode=None,
                                           reply_markup=markup, **kw))


async def send_rich(bot: Bot, chat_id: int, blocks: list[dict], fallback_html: str,
                    markup: InlineKeyboardMarkup | None = None) -> Message | None:
    """Rich Message (Bot API 10.1+). Anything that goes wrong (old Bot API server, bad block) → the HTML fallback."""
    try:
        return await call(bot, SendRichMessage(chat_id=chat_id, rich_message=InputRichMessage(blocks=blocks),
                                               reply_markup=markup))
    except Exception as e:                  # noqa: BLE001 — 400/404 on old servers, validation of future fields, ...
        log.warning("rich message failed (%s) — sending the HTML fallback", e)
    return await send(bot, chat_id, fallback_html, markup)
