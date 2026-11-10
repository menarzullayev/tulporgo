"""Command menus per scope (decision 40): passengers /start /qatnovlarim /til /yordam; drivers also /elon /obuna."""
import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeChat, BotCommandScopeDefault
from tulporgo_core import i18n
from tulporgo_core.enums import Lang

from ..config import BotExtra

log = logging.getLogger(__name__)
PASSENGER = ("start", "qatnovlarim", "til", "yordam")
DRIVER = PASSENGER + ("elon", "obuna")
GROUP = ("taksi", "yordam")                 # group scope, ephemeral (Bot API 10.2); private lists above stay as approved


def commands_for(lang, driver: bool) -> list[BotCommand]:
    return [BotCommand(command=c, description=i18n.t(f"bot.cmd.{c}", lang)) for c in (DRIVER if driver else PASSENGER)]


def group_commands_for(lang) -> list[BotCommand]:
    """Commands only the sender and the bot see in a group (`is_ephemeral`); they point to the private chat."""
    return [BotCommand(command=c, description=i18n.t(f"bot.cmd.group.{c}", lang), is_ephemeral=True) for c in GROUP]


async def sync_chat(bot: Bot, tg_id: int, lang, driver: bool) -> None:
    """Per-chat menu in the user's language; a failure here must never break the conversation."""
    try:
        await bot.set_my_commands(commands_for(lang, driver), scope=BotCommandScopeChat(chat_id=tg_id))
    except Exception as e:                  # noqa: BLE001
        log.warning("setMyCommands for %s failed: %s", tg_id, e)


async def set_defaults(bot: Bot, extra: BotExtra | None = None) -> None:
    """Default menu for everyone, plus Russian and English variants by the client's language."""
    try:
        await bot.set_my_commands(commands_for(Lang.UZ_NEW, False), scope=BotCommandScopeDefault())
        for code, lang in (("ru", Lang.RU), ("en", Lang.EN)):
            await bot.set_my_commands(commands_for(lang, False), scope=BotCommandScopeDefault(), language_code=code)
    except Exception as e:                  # noqa: BLE001
        log.warning("setMyCommands (defaults) failed: %s", e)
    if extra is not None and extra.ephemeral_group:       # new group-scope commands only, behind the flag
        try:
            await bot.set_my_commands(group_commands_for(Lang.UZ_NEW), scope=BotCommandScopeAllGroupChats())
            for code, lang in (("ru", Lang.RU), ("en", Lang.EN)):
                await bot.set_my_commands(group_commands_for(lang), scope=BotCommandScopeAllGroupChats(),
                                          language_code=code)
        except Exception as e:              # noqa: BLE001
            log.warning("setMyCommands (group scope) failed: %s", e)
