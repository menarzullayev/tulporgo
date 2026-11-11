"""Bot side of the group feed (decision 73): re-consent for the new clause, the passenger-search screen, card buttons
and linking the driver's own channel. Real Dispatcher + ContextMiddleware, recording Bot session, no network."""
from datetime import timedelta

from aiogram.methods import DeleteMessage
from aiogram.types import Chat, ChatMemberAdministrator, ChatMemberLeft, ChatMemberUpdated, Update
from aiogram.types import User as TgUser
from sqlalchemy import select
from test_userbot_bot import Harness
from tulporgo_bot.context import ContextMiddleware
from tulporgo_core.db import utcnow
from tulporgo_core.models import Driver, DriverFilter, FeedCard
from userbot_fixtures import *  # noqa: F403
from userbot_helpers import make_account, make_driver

BOT = TgUser(id=1, is_bot=True, first_name="TulporGo")


async def setup(s, maker, settings, bus, *, consent_version=2):
    d = await make_driver(s, settings)
    acc = await make_account(s, settings, d)
    acc.consent_version = consent_version
    f = DriverFilter(driver_id=d.id, name="Kechki", routes=[])
    s.add(f)
    await s.commit()
    h = Harness(maker, settings, bus, d.user.tg_id, lang="uz")
    h.dp.my_chat_member.outer_middleware(ContextMiddleware(maker, settings, bus))
    return d, f, h


async def test_old_consent_shows_the_risk_screen_again(s, maker, settings, bus, factory):
    _, _, h = await setup(s, maker, settings, bus, consent_version=1)
    await h.say("/elon")
    assert "kuzatişi mumkin" in h.last()                     # the new clause is shown before the menu
    await h.press("ub:consent")
    await h.say("/elon")
    assert any(b.callback_data == "fd:menu" for b in h.buttons())


async def test_feed_screen_toggle_filter_and_pause_all(s, maker, settings, bus, factory):
    d, f, h = await setup(s, maker, settings, bus)
    await h.press("fd:menu")
    assert "Yölovçi qidiriş" in h.last() and any(b.callback_data == f"fd:f:{f.id}" for b in h.buttons())
    await h.press(f"fd:f:{f.id}")
    await h.press("fd:pauseall")
    async with maker() as s2:
        assert (await s2.get(DriverFilter, f.id)).enabled is False
        assert (await s2.get(Driver, d.id)).feed_paused is True


async def test_cannot_toggle_someone_elses_filter(s, maker, settings, bus, factory):
    _, other, _ = await setup(s, maker, settings, bus)
    _, _, h = await setup(s, maker, settings, bus)
    await h.press(f"fd:f:{other.id}")                         # negative
    async with maker() as s2:
        assert (await s2.get(DriverFilter, other.id)).enabled is True


async def test_taken_deletes_only_the_owners_card(s, maker, settings, bus, factory):
    d, _, h = await setup(s, maker, settings, bus)
    card = FeedCard(driver_id=d.id, chat_id=d.user.tg_id, message_id=h.n + 2, delete_at=utcnow() + timedelta(hours=2))
    s.add(card)
    await s.commit()
    await h.press("feed:taken")
    assert any(isinstance(c, DeleteMessage) for c in h.session.calls)
    async with maker() as s2:
        assert (await s2.execute(select(FeedCard))).scalars().all() == []


async def test_taken_by_a_stranger_is_refused(s, maker, settings, bus, factory):
    owner, _, _ = await setup(s, maker, settings, bus)
    _, _, h = await setup(s, maker, settings, bus)
    s.add(FeedCard(driver_id=owner.id, chat_id=h.tg.id, message_id=h.n + 2, delete_at=utcnow() + timedelta(hours=2)))
    await s.commit()
    await h.press("feed:taken")                                # negative: a channel member who is not the owner
    assert not any(isinstance(c, DeleteMessage) for c in h.session.calls)
    async with maker() as s2:
        assert len((await s2.execute(select(FeedCard))).scalars().all()) == 1


def _membership(h, status_new):
    admin = ChatMemberAdministrator(user=BOT, can_be_edited=False, is_anonymous=False, can_manage_chat=True,
                                    can_delete_messages=True, can_manage_video_chats=False, can_restrict_members=False,
                                    can_promote_members=False, can_change_info=False, can_invite_users=False,
                                    can_post_stories=False, can_edit_stories=False, can_delete_stories=False,
                                    can_post_messages=True, can_send_welcome_messages=False)
    left = ChatMemberLeft(user=BOT)
    new, old = (admin, left) if status_new == "administrator" else (left, admin)
    h.n += 1
    return Update(update_id=h.n, my_chat_member=ChatMemberUpdated(
        chat=Chat(id=-1007777, type="channel", title="Mening kanalim"), from_user=h.tg, date=utcnow(),
        old_chat_member=old, new_chat_member=new))


async def test_making_the_bot_admin_links_the_channel(s, maker, settings, bus, factory):
    d, _, h = await setup(s, maker, settings, bus)
    await h.dp.feed_update(h.bot, _membership(h, "administrator"))
    async with maker() as s2:
        assert (await s2.get(Driver, d.id)).delivery_chat_id == -1007777
    assert any("şu yerga keladi" in t for t in h.texts())
    await h.dp.feed_update(h.bot, _membership(h, "left"))     # removing the bot unlinks it
    async with maker() as s2:
        assert (await s2.get(Driver, d.id)).delivery_chat_id is None


async def test_non_driver_adding_the_bot_changes_nothing(s, maker, settings, bus, factory):
    d, _, _ = await setup(s, maker, settings, bus)
    from test_userbot_bot import Harness as H
    stranger = H(maker, settings, bus, 999_999_001, lang="uz")
    stranger.dp.my_chat_member.outer_middleware(ContextMiddleware(maker, settings, bus))
    await stranger.dp.feed_update(stranger.bot, _membership(stranger, "administrator"))    # negative
    async with maker() as s2:
        assert (await s2.get(Driver, d.id)).delivery_chat_id is None
