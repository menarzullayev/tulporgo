"""Drivers group screening (GOAL.md §4 "join-request guard"). The closed drivers group is joined through an invite link
that requires approval; the bot approves active registered drivers and declines everyone else, then tells the person
privately how to register (Telegram lets the bot write to `user_chat_id` for a few minutes after a join request).
Requests for other chats are left alone. Blocked users never reach this handler (context middleware)."""
import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatJoinRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import DriverStatus
from tulporgo_core.models import Driver, User

from ..config import get_extra

log = logging.getLogger(__name__)
router = Router(name="joinguard")


@router.chat_join_request()
async def on_join_request(req: ChatJoinRequest, session: AsyncSession, settings: Settings, user: User, bot: Bot,
                          t) -> None:
    group_id = get_extra().drivers_group_id
    if not group_id or req.chat.id != group_id:
        return
    d = (await session.execute(select(Driver).where(Driver.user_id == user.id))).scalar_one_or_none()
    if d is not None and d.status == DriverStatus.ACTIVE:
        await req.approve()
        return
    await req.decline()
    try:
        await bot.send_message(req.user_chat_id, t("bot.join.declined",
                                                       link=f"https://t.me/{settings.bot_username}?start=driver"))
    except TelegramAPIError as e:                       # the person may have blocked the bot; declining is what matters
        log.info("join-request note not delivered: %s", type(e).__name__)
