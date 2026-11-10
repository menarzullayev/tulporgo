# ruff: noqa: F401, F811  (fixtures are imported explicitly)
"""Buttons on messages the bot cannot edit. CallbackQuery.message is None for inline-mode callbacks and
InaccessibleMessage (no edit/answer methods) for old messages: payment handlers must not raise on either."""
import itertools

import pytest
from aiogram.methods import EditMessageCaption, EditMessageText, SendMessage
from aiogram.types import PhotoSize
from test_pay_bot import ADMIN, env, p2p_start
from tulporgo_core.enums import PaymentStatus

_n = itertools.count(10_000)


async def press_without_message(env, uid, data, inaccessible):
    cq = {"id": str(next(_n)), "from": {"id": uid, "is_bot": False, "first_name": "Ali", "language_code": "en"},
          "chat_instance": "ci", "data": data}
    if inaccessible:                                          # date == 0 is how Telegram marks an inaccessible message
        cq["message"] = {"message_id": 500, "date": 0, "chat": {"id": uid, "type": "private"}}
    await env.feed(callback_query=cq)


@pytest.mark.parametrize("data", ["pay:pl:pro", "pay:home", "pay:mo:pro:1", "pay:go:pro:1:click"])
async def test_checkout_screens_without_message_do_nothing(env, data):
    tg = await env.seed_driver()
    await press_without_message(env, tg, data, False)                         # must not raise
    assert not env.of(EditMessageText) and not env.of(SendMessage, tg)


@pytest.mark.parametrize("data", ["pay:pl:pro", "pay:home", "pay:mo:pro:1", "pay:go:pro:1:click"])
async def test_checkout_screens_on_inaccessible_message_arrive_as_a_new_message(env, data):
    tg = await env.seed_driver()
    await press_without_message(env, tg, data, True)                          # cannot edit, can answer
    assert not env.of(EditMessageText) and len(env.of(SendMessage, tg)) == 1


async def test_p2p_receipt_button_without_message_is_a_noop(env):
    tg = await p2p_start(env)
    (p,) = await env.payments()
    sent = len(env.of(SendMessage, tg))
    await press_without_message(env, tg, f"pay:rc:{p.id}", False)             # used to raise AttributeError
    assert len(env.of(SendMessage, tg)) == sent


async def test_p2p_receipt_button_on_inaccessible_message_still_asks_for_the_photo(env):
    tg = await p2p_start(env)
    (p,) = await env.payments()
    sent = len(env.of(SendMessage, tg))
    await press_without_message(env, tg, f"pay:rc:{p.id}", True)              # InaccessibleMessage can be answered
    assert len(env.of(SendMessage, tg)) == sent + 1


@pytest.mark.parametrize("inaccessible", [False, True])
async def test_admin_review_on_inaccessible_message_still_decides(env, inaccessible):
    tg = await p2p_start(env)
    await env.say(tg, photo=[PhotoSize(file_id="PH1", file_unique_id="u1", width=1, height=1)])
    (p,) = await env.payments()
    edits = len(env.of(EditMessageText))
    await press_without_message(env, ADMIN, f"pay:ok:{p.id}", inaccessible)
    assert (await env.payments())[0].status == PaymentStatus.PAID             # decision applied, only the edit skipped
    assert not env.of(EditMessageCaption) and len(env.of(EditMessageText)) == edits
