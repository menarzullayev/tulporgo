"""/elon UX through a real aiogram Dispatcher + the shared ContextMiddleware, with a recording Bot session (no network)."""
from datetime import timedelta

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, MessageEntity, Update
from aiogram.types import User as TgUser
from sqlalchemy import select
from tulporgo_bot.context import ContextMiddleware
from tulporgo_core.db import utcnow
from tulporgo_core.enums import Plan, UserbotStatus
from tulporgo_core.models import UserbotAccount, UserbotGroup
from tulporgo_userbot import runtime
from tulporgo_userbot.bot import router
from userbot_fixtures import *  # noqa: F403 - pytest fixtures
from userbot_helpers import SESSION_PLAIN, make_account, make_driver


class RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    async def close(self) -> None: ...

    async def stream_content(self, *a, **kw):
        if False:
            yield b""

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        self.calls.append(method)
        if isinstance(method, SendMessage | EditMessageText):
            return Message(message_id=len(self.calls), date=utcnow(), chat=Chat(id=1, type="private"), text=method.text)
        return True


class Harness:
    def __init__(self, maker, settings, bus, tg_id: int, lang: str = "en") -> None:
        self.session = RecordingSession()
        self.bot = Bot("1:TEST", session=self.session)
        self.dp = Dispatcher()
        mw = ContextMiddleware(maker, settings, bus)
        self.dp.message.outer_middleware(mw)
        self.dp.callback_query.outer_middleware(mw)
        router._parent_router = None            # a module-level Router can be attached to one Dispatcher at a time
        self.dp.include_router(router)
        self.tg = TgUser(id=tg_id, is_bot=False, first_name="Haydovchi", language_code=lang)
        self.n = 0

    def _msg(self, text: str, chat_type: str = "private") -> Message:
        self.n += 1
        ents = [MessageEntity(type="bot_command", offset=0, length=len(text.split()[0]))] if text.startswith("/") else None
        return Message(message_id=self.n, date=utcnow(), chat=Chat(id=self.tg.id, type=chat_type), text=text,
                       from_user=self.tg, entities=ents)

    async def say(self, text: str, chat_type: str = "private"):
        self.n += 1
        await self.dp.feed_update(self.bot, Update(update_id=self.n, message=self._msg(text, chat_type)))

    async def press(self, data: str):
        self.n += 1
        cq = CallbackQuery(id=str(self.n), from_user=self.tg, chat_instance="x", data=data, message=self._msg("menu"))
        await self.dp.feed_update(self.bot, Update(update_id=self.n, callback_query=cq))

    # what the user saw
    def texts(self) -> list[str]:
        return [c.text for c in self.session.calls if isinstance(c, SendMessage | EditMessageText)]

    def last(self) -> str:
        return self.texts()[-1]

    def last_markup(self):
        c = [c for c in self.session.calls if isinstance(c, SendMessage | EditMessageText)][-1]
        return c.reply_markup

    def buttons(self) -> list:
        m = self.last_markup()
        return [b for row in (m.inline_keyboard if m else []) for b in row]

    def alerts(self) -> list[str]:
        return [c.text for c in self.session.calls if isinstance(c, AnswerCallbackQuery) and c.show_alert]


@pytest.fixture
async def h(s, maker, settings, bus):
    d = await make_driver(s, settings)
    return Harness(maker, settings, bus, d.user.tg_id), d


async def account(maker) -> UserbotAccount | None:
    async with maker() as s2:
        return (await s2.execute(select(UserbotAccount))).scalars().first()


# ------------------------------------------------------------------ consent

async def test_elon_shows_risk_screen_and_nothing_else_before_consent(h, maker):
    bot, _ = h
    await bot.say("/elon")
    text = bot.last()
    assert "FloodWait" in text and "PEER_FLOOD" in text and "45" in text and "encrypted" in text
    datas = [b.callback_data for b in bot.buttons()]
    assert datas == ["ub:consent", "ub:close"]                              # no connect / groups before consent
    assert not any(b.web_app for b in bot.buttons())
    assert await account(maker) is None                                     # nothing created without consent


async def test_consent_button_records_consent_and_offers_mini_app_login(h, maker, settings):
    bot, _ = h
    await bot.say("/elon")
    await bot.press("ub:consent")
    assert (await account(maker)).consent_at is not None
    web = [b for b in bot.buttons() if b.web_app]
    assert len(web) == 1 and web[0].web_app.url.startswith(settings.miniapp_url)
    assert "never send them in a message" in bot.texts()[-2] or "Mini App" in bot.last() or "connected" in bot.last()


async def test_bot_never_asks_for_the_code_or_password(h, maker):
    bot, _ = h
    await bot.say("/elon")
    await bot.press("ub:consent")
    joined = "\n".join(bot.texts()).lower()
    assert "enter the code" not in joined and "send the code" not in joined
    await bot.say("12345")                                                  # a code typed into chat is ignored, not used
    assert (await account(maker)).session_encrypted is None


async def test_non_driver_gets_a_clear_refusal(s, maker, settings, bus):
    from tulporgo_core.services import users
    await users.get_or_create_user(s, 31337, username=None, first_name="Yo'lovchi")
    await s.commit()
    bot = Harness(maker, settings, bus, 31337)
    await bot.say("/elon")
    assert "drivers only" in bot.last()
    assert await account(maker) is None


async def test_elon_in_a_group_chat_is_ignored(h):
    bot, _ = h
    await bot.say("/elon", chat_type="supergroup")
    assert bot.texts() == []                                                # the risk screen is private only


# ------------------------------------------------------------------ menu / status

async def test_connected_menu_shows_status_and_actions(s, h, maker, settings):
    bot, d = h
    await make_account(s, settings, d, groups=2)
    await bot.say("/elon")
    assert "running" in bot.last() and "45 min" in bot.last()
    assert {b.callback_data for b in bot.buttons() if b.callback_data} >= {"ub:groups:0", "ub:int", "ub:tpl", "ub:pause",
                                                                           "ub:logout"}
    assert next(b for b in bot.buttons() if b.callback_data == "ub:logout").style == "danger"


async def test_menu_texts_follow_the_language(s, maker, settings, bus):
    d = await make_driver(s, settings)
    bot = Harness(maker, settings, bus, d.user.tg_id, lang="ru")
    await bot.say("/elon")
    assert "Автообъявления: согласие" in bot.last()


# ------------------------------------------------------------------ groups

async def test_group_toggle_respects_the_plan_limit(s, maker, paid_settings, bus):
    d = await make_driver(s, paid_settings, plan=Plan.PRO)
    acc = await make_account(s, paid_settings, d, groups=16, enabled=False)
    async with maker() as s2:
        for g in (await s2.execute(select(UserbotGroup).where(UserbotGroup.account_id == acc.id))).scalars().all()[:15]:
            g.enabled = True
        await s2.commit()
    bot = Harness(maker, paid_settings, bus, d.user.tg_id)
    async with maker() as s2:
        sixteenth = (await s2.execute(select(UserbotGroup).where(UserbotGroup.enabled.is_(False)))).scalars().one()
    await bot.press(f"ub:g:{sixteenth.id}:1")
    assert bot.alerts() == ["You reached your plan's group limit."]
    async with maker() as s2:
        assert (await s2.get(UserbotGroup, sixteenth.id)).enabled is False


async def test_group_toggle_and_pagination(s, h, maker, settings):
    bot, d = h
    acc = await make_account(s, settings, d, groups=10, enabled=False)
    await bot.press("ub:groups:0")
    assert "0 / unlimited" in bot.last() and len([b for b in bot.buttons() if b.callback_data.startswith("ub:g:")]) == 8
    assert any(b.callback_data == "ub:groups:1" for b in bot.buttons())
    async with maker() as s2:
        gid = (await s2.execute(select(UserbotGroup).where(UserbotGroup.account_id == acc.id))).scalars().first().id
    await bot.press(f"ub:g:{gid}:0")
    assert "1 / unlimited" in bot.last() and bot.buttons()[0].text.startswith("✅")
    await bot.press(f"ub:g:{gid}:0")
    assert "0 / unlimited" in bot.last()


async def test_other_drivers_group_cannot_be_toggled(s, h, maker, settings, bus):
    bot, d = h
    await make_account(s, settings, d, groups=1)
    other = await make_driver(s, settings)
    other_acc = await make_account(s, settings, other, groups=1, enabled=False)
    async with maker() as s2:
        foreign = (await s2.execute(select(UserbotGroup).where(UserbotGroup.account_id == other_acc.id))).scalars().one()
    await bot.press(f"ub:g:{foreign.id}:0")
    assert bot.alerts() and "generic" not in bot.alerts()[0]
    async with maker() as s2:
        assert (await s2.get(UserbotGroup, foreign.id)).enabled is False


async def test_sync_button_refreshes_the_list(s, h, maker, settings, factory):
    bot, d = h
    await make_account(s, settings, d, groups=0)
    await bot.press("ub:sync")
    assert "List refreshed: 3 groups" in bot.last()


# ------------------------------------------------------------------ interval (decision 48)

async def test_interval_below_safe_default_needs_the_warning_screen(s, h, maker, settings):
    bot, d = h
    await make_account(s, settings, d)
    await bot.press("ub:int")
    datas = [b.callback_data for b in bot.buttons()]
    assert "ub:i:45" in datas and "ub:ir:20" in datas and "ub:i:20" not in datas
    # a hand-made callback that skips the warning is refused
    await bot.press("ub:i:20")
    assert bot.alerts() == ["You must acknowledge the risk to go below the safe threshold."]
    assert (await account(maker)).min_interval_minutes == 45 and (await account(maker)).risk_acknowledged is False
    # the proper path: warning, then explicit acknowledgement
    await bot.press("ub:ir:20")
    assert "below the safe threshold" in bot.last() and bot.buttons()[0].callback_data == "ub:ia:20"
    await bot.press("ub:ia:20")
    acc = await account(maker)
    assert acc.min_interval_minutes == 20 and acc.risk_acknowledged is True


async def test_safe_interval_change_needs_no_warning(s, h, maker, settings):
    bot, d = h
    await make_account(s, settings, d)
    await bot.press("ub:i:90")
    assert (await account(maker)).min_interval_minutes == 90 and bot.alerts() == []


async def test_interval_floor_even_with_acknowledgement(s, h, maker, settings):
    bot, d = h
    await make_account(s, settings, d)
    await bot.press("ub:ia:1")
    assert bot.alerts() and (await account(maker)).min_interval_minutes == 45


# ------------------------------------------------------------------ template

async def test_template_dialog_saves_and_previews(s, h, maker, settings):
    bot, d = h
    await make_account(s, settings, d, with_template=False)
    await bot.press("ub:tpl")
    assert "No post text yet" in bot.last()
    await bot.press("ub:tpl_edit")
    for step in ("Samarqand", "Toshkent", "08:00", "3", "120000"):
        await bot.say(step)
    assert "Post text saved" in bot.last() and "Samarqand → Toshkent" in bot.last() and "@tulporgobot" in bot.last()
    acc = await account(maker)
    assert '"Samarqand"' in acc.post_template and '"seats": 3' in acc.post_template


@pytest.mark.parametrize("bad_step,value", [(0, "@spam_bot"), (1, "https://x.example"), (2, "t.me/join"), (3, "12")])
async def test_template_dialog_rejects_links_and_bad_values(s, h, maker, settings, bad_step, value):
    bot, d = h
    await make_account(s, settings, d, with_template=False)
    await bot.press("ub:tpl_edit")
    good = ["Samarqand", "Toshkent", "08:00", "3"]
    for i in range(bad_step):
        await bot.say(good[i])
    await bot.say(value)
    assert "not allowed" in bot.last()
    await bot.say("-")                                                      # still waiting for the same step: not saved
    assert (await account(maker)).post_template is None


async def test_elon_command_cancels_a_running_dialog(s, h, maker, settings):
    bot, d = h
    await make_account(s, settings, d, with_template=False)
    await bot.press("ub:tpl_edit")
    await bot.say("Samarqand")
    await bot.say("/elon")
    await bot.say("Toshkent")                                               # no longer part of any dialog
    assert (await account(maker)).post_template is None


# ------------------------------------------------------------------ pause / resume / logout

async def test_pause_resume_buttons(s, h, maker, settings):
    bot, d = h
    await make_account(s, settings, d)
    await bot.press("ub:pause")
    assert (await account(maker)).status == UserbotStatus.PAUSED and "paused" in bot.last().lower()
    assert any(b.callback_data == "ub:resume" and b.style == "success" for b in bot.buttons())
    await bot.press("ub:resume")
    assert (await account(maker)).status == UserbotStatus.CONNECTED


async def test_resume_button_cannot_end_a_flood_wait(s, h, maker, settings):
    bot, d = h
    acc = await make_account(s, settings, d)
    async with maker() as s2:
        a = await s2.get(UserbotAccount, acc.id)
        a.status, a.flood_until = UserbotStatus.FLOOD_WAIT, utcnow() + timedelta(hours=1)
        await s2.commit()
    await bot.press("ub:resume")
    assert bot.alerts() and (await account(maker)).status == UserbotStatus.FLOOD_WAIT


async def test_logout_needs_confirmation_then_deletes_the_session(s, h, maker, settings, factory):
    bot, d = h
    await make_account(s, settings, d, groups=2)
    await bot.press("ub:logout")
    assert "deletes our copy" in bot.last()
    assert (await account(maker)).session_encrypted is not None            # asking alone changes nothing
    await bot.press("ub:logout_yes")
    acc = await account(maker)
    assert acc.session_encrypted is None and acc.status == UserbotStatus.NEEDS_LOGIN and acc.consent_at is None
    assert factory.logged_out_sessions == [SESSION_PLAIN] and "session deleted" in bot.last()
    async with maker() as s2:
        assert (await s2.execute(select(UserbotGroup))).first() is None


async def test_logout_without_telegram_credentials_still_deletes(s, h, maker, settings, monkeypatch):
    monkeypatch.delenv("TULPORGO_TELEGRAM_API_ID", raising=False)
    runtime.set_factory(None)
    bot, d = h
    await make_account(s, settings, d)
    await bot.press("ub:logout_yes")
    assert (await account(maker)).session_encrypted is None
