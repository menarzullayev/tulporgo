"""Group commands (Bot API 10.2 ephemeral commands, flag `TULPORGO_EPHEMERAL_GROUP`). In a group the bot has never
answered commands; with the flag on it answers the one user, ephemerally, with a button to continue in private chat.
If the ephemeral answer cannot be delivered (or the 15 s window passed) the group stays silent — as it always has."""
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from tulporgo_core.config import Settings

from .. import ephemeral
from ..config import get_extra
from .common import btn, deep_link, kb

router = Router(name="groupcmds")
router.message.filter(F.chat.type.in_({"group", "supergroup"}), lambda _msg: get_extra().ephemeral_group)

GROUP_COMMANDS = ("taksi", "yordam")                          # published for group chats (commands.group_commands_for)
PAYLOAD = {"yordam": "faq"}                                  # everything else opens the order flow


@router.message(Command("taksi", "yordam", "start", "qatnovlarim", "til", "elon", "obuna"))
async def group_command(msg: Message, bot: Bot, settings: Settings, t) -> None:
    if msg.from_user is None or not msg.text:
        return
    name = msg.text.split()[0][1:].split("@")[0].lower()
    markup = kb([btn(f"🚕 {t('bot.group.btn')}", url=deep_link(settings, PAYLOAD.get(name, "order")), style="primary")])
    await ephemeral.reply(bot, msg.chat.id, msg.from_user.id, t("bot.group.private_only"), markup,
                          to_ephemeral_id=msg.ephemeral_message_id, sent_at=msg.date)
