"""Guest Mode (Bot API 10.0, decision 47d): the bot is mentioned in any group; it sees only that message and answers
with `answerGuestQuery`: the parsed route plus a deep link to finish the order privately."""
import logging
import re

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, Message
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core import emoji
from tulporgo_core.config import Settings
from tulporgo_core.db import utcnow
from tulporgo_core.parser import ParsedRoute, parse
from tulporgo_core.places import PlaceIndex

from .common import btn, deep_link, esc, kb, time_html, unix

log = logging.getLogger(__name__)
router = Router(name="guest")


def guest_payload(parsed: ParsedRoute) -> str:
    """`g_<from>_<to>_<seats>_<depart minutes>` — only when both ends are known places; else plain `order`."""
    if not (parsed.from_place and parsed.to_place) or parsed.from_place.id == parsed.to_place.id:
        return "order"
    minutes = unix(parsed.depart_at) // 60 if parsed.depart_at else 0
    return f"g_{parsed.from_place.id}_{parsed.to_place.id}_{parsed.seats}_{minutes}"


def strip_mention(text: str, bot_username: str) -> str:
    return re.sub(rf"@{re.escape(bot_username)}\b", " ", text or "", flags=re.I).strip()


@router.guest_message()
async def on_guest(msg: Message, bot: Bot, session: AsyncSession, settings: Settings, t) -> None:
    if not msg.guest_query_id:
        return
    parsed = parse(strip_mention(msg.text or msg.caption or "", settings.bot_username),
                   await PlaceIndex.load(session), utcnow())
    if parsed is None:
        text = t("bot.guest.not_understood")
        link = deep_link(settings, "order")
    else:
        a = parsed.from_place.name if parsed.from_place else parsed.from_text
        b = parsed.to_place.name if parsed.to_place else parsed.to_text
        lines = [f"<b>{t('bot.guest.title')}</b>", f"📍 {esc(a)} → {esc(b)}", f"🕐 {time_html(parsed.depart_at, t)}",
                 f"👥 {t('bot.seats_n', n=parsed.seats)}", "", t("bot.guest.finish")]
        text = "\n".join(lines)
        link = deep_link(settings, guest_payload(parsed))
    result = InlineQueryResultArticle(
        id="order", title=t("bot.guest.title"),
        input_message_content=InputTextMessageContent(message_text=emoji.decorate(text), parse_mode="HTML"),
        reply_markup=kb([btn(f"🚕 {t('bot.guest.button')}", url=link, style="primary")]))
    try:
        await bot.answer_guest_query(guest_query_id=msg.guest_query_id, result=result)
    except TelegramAPIError as e:                         # query expired / bot not enabled for guests: nothing to do
        log.warning("answerGuestQuery failed: %s", e)


