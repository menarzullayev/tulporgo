# ruff: noqa: F401, F811  (fixtures are imported explicitly)
"""/elon buttons pressed on a message the bot cannot touch: CallbackQuery.message is None (inline mode) or
InaccessibleMessage (old message, no edit/answer/delete methods). Handlers must not raise."""
import pytest
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import CallbackQuery, Chat, InaccessibleMessage, Update
from test_userbot_bot import Harness, h
from userbot_fixtures import *  # noqa: F403 - pytest fixtures


async def press_without_message(bot: Harness, data: str, inaccessible: bool) -> None:
    bot.n += 1
    msg = InaccessibleMessage(chat=Chat(id=bot.tg.id, type="private"), message_id=5) if inaccessible else None
    cq = CallbackQuery(id=str(bot.n), from_user=bot.tg, chat_instance="x", data=data, message=msg)
    await bot.dp.feed_update(bot.bot, Update(update_id=bot.n, callback_query=cq))


@pytest.mark.parametrize("inaccessible", [False, True])
async def test_menu_is_sent_as_a_new_message_when_the_old_one_cannot_be_edited(h, inaccessible):
    bot, _ = h
    await press_without_message(bot, "ub:menu", inaccessible)                # used to raise AttributeError
    sent = [c for c in bot.session.calls if isinstance(c, SendMessage)]
    assert sent and sent[-1].chat_id == bot.tg.id
    assert any(isinstance(c, AnswerCallbackQuery) for c in bot.session.calls)


@pytest.mark.parametrize("inaccessible", [False, True])
async def test_close_on_an_inaccessible_message_only_answers_the_callback(h, inaccessible):
    bot, _ = h
    await press_without_message(bot, "ub:close", inaccessible)               # used to raise AttributeError
    assert any(isinstance(c, AnswerCallbackQuery) for c in bot.session.calls)
