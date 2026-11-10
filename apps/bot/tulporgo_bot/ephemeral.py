"""Ephemeral messages (Bot API 10.2): in a group only the receiving user (and the bot) sees them, so group commands and
stale group buttons do not clutter the chat. Delivery is not guaranteed and a reply to an ephemeral message must be sent
within 15 seconds — every helper here reports `False` instead of raising, and the caller decides what the fallback is
(for TulporGo: exactly what the bot did before the feature — a callback alert, or silence)."""
import logging
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.methods import SendMessage
from aiogram.types import EphemeralMessageParameters, InlineKeyboardMarkup, ReplyParameters
from tulporgo_core import emoji

from . import delivery

log = logging.getLogger(__name__)
REPLY_WINDOW_SECONDS = 15


def is_group(chat_type: str) -> bool:
    return chat_type in ("group", "supergroup")


def window_open(sent_at: datetime | None, now: datetime | None = None) -> bool:
    if sent_at is None:
        return True
    now = now or datetime.now(UTC)
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)
    return (now - sent_at).total_seconds() <= REPLY_WINDOW_SECONDS


async def reply(bot: Bot, chat_id: int, user_id: int, html: str, markup: InlineKeyboardMarkup | None = None, *,
                to_ephemeral_id: int | None = None, sent_at: datetime | None = None,
                callback_query_id: str | None = None) -> bool:
    """Send an ephemeral message to `user_id` in a group. `to_ephemeral_id` = the incoming ephemeral message
    (`Message.ephemeral_message_id`) this answers; once `sent_at` is more than 15 s old nothing is sent."""
    if chat_id >= 0:                                        # ephemeral messages exist for groups and supergroups only
        return False
    if to_ephemeral_id is not None and not window_open(sent_at):
        delivery.warn_once("ephemeral-late", "ephemeral reply window (15 s) passed — not answering")
        return False
    try:
        sent = await delivery.call(bot, SendMessage(
            chat_id=chat_id, text=emoji.decorate(html), parse_mode="HTML", reply_markup=markup,
            ephemeral_message_parameters=EphemeralMessageParameters(receiver_user_id=user_id,
                                                                    callback_query_id=callback_query_id),
            reply_parameters=(ReplyParameters(ephemeral_message_id=to_ephemeral_id)
                              if to_ephemeral_id is not None else None)))
    except TelegramAPIError as e:                           # old server, not enabled, user offline, window missed...
        delivery.warn_once("ephemeral", "ephemeral message failed (%s)", e)
        return False
    return sent is not None
