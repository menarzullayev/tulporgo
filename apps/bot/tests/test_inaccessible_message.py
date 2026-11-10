"""Telegram Optionals that used to crash handlers: CallbackQuery.message is None (inline mode) or InaccessibleMessage
(old messages), and Message.contact / from_user are Optional. Each guard has a negative test: no exception, and the
user still gets what they asked for (or a clear refusal)."""
import json
import time
from datetime import datetime

import pytest
from aiogram.types import Chat, Contact, Message
from bot_harness import env  # noqa: F401  (fixture)
from bot_harness import tx
from tulporgo_bot.handlers.driver import got_contact


async def press_without_message(env, uid, data, inaccessible):
    cq = {"id": str(next(env._upd)), "from": env._from(uid), "chat_instance": "ci", "data": data}
    if inaccessible:                                          # date == 0 is how Telegram marks an inaccessible message
        cq["message"] = {"message_id": 500, "date": 0, "chat": env._chat(uid)}
    await env.feed(callback_query=cq)


@pytest.mark.parametrize("inaccessible", [False, True])
async def test_export_still_delivers_the_file_without_an_accessible_message(env, inaccessible):
    await env.user(1)
    await press_without_message(env, 1, "pv:x", inaccessible)                # used to raise AttributeError
    docs = env.methods("SendDocument")
    assert docs and docs[-1].chat_id == 1
    assert json.loads(docs[-1].document.data.decode("utf-8"))["profile"]["telegram_id"] == 1


async def test_contact_without_sender_is_refused_not_crashed(env):
    msg = Message(message_id=1, date=datetime.fromtimestamp(time.time()), chat=Chat(id=7, type="private"),
                  contact=Contact(phone_number="+998901234567", first_name="Ali", user_id=7)).as_(env.bot)
    assert msg.from_user is None                                             # e.g. a channel post
    await got_contact(msg, state=None, session=None, user=None, t=lambda key, **kw: tx(key, **kw))
    assert env.last_text(7) == tx("bot.reg.contact_not_own")
