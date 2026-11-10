"""Command menus per scope (decision 40): passengers /start /qatnovlarim /til /yordam; drivers also /elon /obuna."""
import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from tulporgo_core import i18n
from tulporgo_core.enums import Lang

log = logging.getLogger(__name__)
PASSENGER = ("start", "qatnovlarim", "til", "yordam")
DRIVER = PASSENGER + ("elon", "obuna")


def commands_for(lang, driver: bool) -> list[BotCommand]:
    return [BotCommand(command=c, description=i18n.t(f"bot.cmd.{c}", lang)) for c in (DRIVER if driver else PASSENGER)]


async def sync_chat(bot: Bot, tg_id: int, lang, driver: bool) -> None:
    """Per-chat menu in the user's language; a failure here must never break the conversation."""
    try:
        await bot.set_my_commands(commands_for(lang, driver), scope=BotCommandScopeChat(chat_id=tg_id))
    except Exception as e:                  # noqa: BLE001
        log.warning("setMyCommands for %s failed: %s", tg_id, e)


async def set_defaults(bot: Bot) -> None:
    """Default menu for everyone, plus Russian and English variants by the client's language."""
    try:
        await bot.set_my_commands(commands_for(Lang.UZ_NEW, False), scope=BotCommandScopeDefault())
        for code, lang in (("ru", Lang.RU), ("en", Lang.EN)):
            await bot.set_my_commands(commands_for(lang, False), scope=BotCommandScopeDefault(), language_code=code)
    except Exception as e:                  # noqa: BLE001
        log.warning("setMyCommands (defaults) failed: %s", e)
