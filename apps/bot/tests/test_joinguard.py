"""Drivers group join-request guard: active drivers in, everyone else out with a private note; other chats untouched."""
import time

import pytest
from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import tx
from sqlalchemy import select
from tulporgo_core.enums import DriverStatus
from tulporgo_core.models import Driver

GROUP = -1001234500000


@pytest.fixture(autouse=True)
def drivers_group(monkeypatch):
    monkeypatch.setenv("TULPORGO_DRIVERS_GROUP_ID", str(GROUP))


async def join(env, uid: int, chat_id: int = GROUP):
    await env.feed(chat_join_request={"chat": {"id": chat_id, "type": "supergroup", "title": "Haydovchilar"},
                                      "from": env._from(uid), "user_chat_id": uid, "date": int(time.time())})


def decided(env, kind: str) -> list[int]:
    return [m.user_id for m in env.methods(kind)]


async def test_active_driver_is_approved(env):
    await env.driver(5)
    await join(env, 5)
    assert decided(env, "ApproveChatJoinRequest") == [5]
    assert decided(env, "DeclineChatJoinRequest") == []


async def test_passenger_is_declined_and_told_how_to_register(env):
    await env.user(6)
    await join(env, 6)
    assert decided(env, "DeclineChatJoinRequest") == [6]
    assert decided(env, "ApproveChatJoinRequest") == []
    assert env.last_text(6) == tx("bot.join.declined", link="https://t.me/tulporgobot?start=driver")


async def test_suspended_driver_is_declined(env):
    did = await env.driver(7)

    async def suspend(s):
        (await s.get(Driver, did)).status = DriverStatus.SUSPENDED
    await env.db(suspend)
    await join(env, 7)
    assert decided(env, "DeclineChatJoinRequest") == [7]


async def test_blocked_user_is_never_approved(env):
    await env.driver(8)
    await env.db(lambda s: _block(s, 8))
    await join(env, 8)
    assert decided(env, "ApproveChatJoinRequest") == []


async def test_other_chats_are_left_alone(env):
    await env.user(9)
    await join(env, 9, chat_id=-1009999999999)
    assert decided(env, "ApproveChatJoinRequest") == [] and decided(env, "DeclineChatJoinRequest") == []


async def _block(s, tg):
    from tulporgo_core.models import User
    u = await s.scalar(select(User).where(User.tg_id == tg))
    u.is_blocked = True
