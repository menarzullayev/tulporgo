"""Test harness for the bot: a fake Telegram session (no network, ever), a SQLite database and a tiny "client" that
feeds updates through the real dispatcher and records everything the bot sends."""
import itertools
import time
from datetime import datetime
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import TelegramMethod
from aiogram.types import Chat, ForumTopic, Message, SentGuestMessage
from aiogram.types import User as TgUser
from tulporgo_bot import delivery
from tulporgo_bot.delivery import strip_tags
from tulporgo_bot.handlers import setup
from tulporgo_bot.main import build_dispatcher, finish_dispatcher
from tulporgo_core import i18n
from tulporgo_core.config import Settings
from tulporgo_core.db import Base, make_engine, make_sessionmaker, session_scope
from tulporgo_core.events import InMemoryBus
from tulporgo_core.models import Place
from tulporgo_core.services import drivers, users

BOT_ID = 9_000_000


def tx(key: str, lang: str = "uz_new", **kw) -> str:
    """Expected text from the catalog (so tests do not depend on the new-alphabet spelling)."""
    return i18n.t(key, lang, **kw)


def som(n: int, lang: str = "uz_new") -> str:
    return i18n.t("common.price", lang, price=f"{n:,}".replace(",", " "))


class FakeSession(BaseSession):
    """Records every Bot API call; `errors[MethodClass]` = exception (or list of them, consumed one per call)."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []          # delivered
        self.failed: list[TelegramMethod] = []         # raised an error
        self.errors: dict[type, Any] = {}
        self._ids = itertools.count(1000)
        self._topics = itertools.count(7000)
        self.has_topics = True                         # what getMe reports (BotFather: topics in private chats)

    async def close(self) -> None:
        return None

    async def stream_content(self, *a, **kw):                      # pragma: no cover
        raise NotImplementedError
        yield b""

    async def make_request(self, bot, method, timeout=None):
        err = self.errors.get(type(method))
        if isinstance(err, list):
            err = err.pop(0) if err else None
        if err is not None:
            self.failed.append(method)                                 # refused by "Telegram": not delivered
            raise err
        self.calls.append(method)
        name = type(method).__name__
        if name.startswith("Send") and hasattr(method, "chat_id"):
            return Message(message_id=next(self._ids), date=datetime.now(), chat=Chat(id=method.chat_id, type="private"))
        if name == "GetMe":
            return TgUser(id=BOT_ID, is_bot=True, first_name="TulporGo", username="tulporgobot",
                          has_topics_enabled=self.has_topics)
        if name == "CreateForumTopic":
            return ForumTopic(message_thread_id=next(self._topics), name=method.name, icon_color=method.icon_color or 0)
        if name == "AnswerGuestQuery":
            return SentGuestMessage(inline_message_id="inline-1")
        return True


def markup_data(markup) -> list[str]:
    """All callback_data of an inline keyboard (reply keyboards have none)."""
    rows = getattr(markup, "inline_keyboard", None) or []
    return [b.callback_data for row in rows for b in row if b.callback_data]


def markup_buttons(markup):
    return [b for row in (getattr(markup, "inline_keyboard", None) or []) for b in row]


def body(method) -> str:
    """Visible text of a send/edit call (rich messages: all text of heading/table blocks)."""
    if hasattr(method, "text") and isinstance(method.text, str):
        return method.text
    if hasattr(method, "caption") and method.caption:
        return method.caption
    rm = getattr(method, "rich_message", None)
    if rm is not None:
        return repr(rm.blocks)
    return ""


class Env:
    def __init__(self, tmp_path, **settings_kw) -> None:
        self.url = f"sqlite+aiosqlite:///{(tmp_path / 'bot.db').as_posix()}"
        self.settings = Settings(database_url=self.url, bot_token="1:TEST", bot_username="tulporgobot",
                                 admin_ids=settings_kw.pop("admin_ids", []), **settings_kw)
        self.bus = InMemoryBus()
        self.fake = FakeSession()
        self.bot = Bot("1:TEST", session=self.fake, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self._upd = itertools.count(1)
        self._mid = itertools.count(1)

    async def start(self, probe=None):
        self.engine = make_engine(self.url)
        async with self.engine.begin() as c:
            await c.run_sync(Base.metadata.create_all)
        self.maker = make_sessionmaker(self.engine)
        self.dp = build_dispatcher(self.settings, self.maker, self.bus)
        if probe is not None:                                                  # e.g. a router of another workstream
            self.dp.include_router(probe)
        finish_dispatcher(self.dp)
        self.runtime = await setup(bot=self.bot, maker=self.maker, settings=self.settings, bus=self.bus, jobs=False)
        delivery.LIMITER.rate = 0.0                                            # setup() applied the real rate
        return self

    async def stop(self):
        await self.engine.dispose()

    # ---------- database helpers ----------
    async def seed_places(self):
        async with session_scope(self.maker) as s:
            reg = Place(kind="region", name_uz="Samarqand viloyati")
            s.add(reg)
            await s.flush()
            qosh = Place(kind="district", name_uz="Qo'shrabot", name_ru="Кошрабад", parent_id=reg.id, popularity=10,
                         aliases=["koshrabad"])
            sam = Place(kind="city", name_uz="Samarqand", name_ru="Самарканд", parent_id=reg.id, popularity=20)
            pas = Place(kind="district", name_uz="Pastdarg'om", parent_id=reg.id, popularity=5)
            s.add_all([qosh, sam, pas])
            await s.flush()
            for i in range(10):                                                # 10 mahallas → two pages of 8
                s.add(Place(kind="mahalla", name_uz=f"Mahalla{i:02d}", parent_id=qosh.id, popularity=10 - i))
            s.add(Place(kind="mahalla", name_uz="Qovunchi", parent_id=sam.id))
            await s.flush()
            self.qosh, self.sam, self.pas = qosh.id, sam.id, pas.id

    async def user(self, uid: int, lang: str = "uz_new", name: str = "Ali", username: str | None = None,
                   phone: str | None = None, admin: bool = False, woman: bool = False, blocked: bool = False):
        async with session_scope(self.maker) as s:
            u = await users.get_or_create_user(s, uid, username, name)
            u.lang, u.phone, u.is_admin, u.is_woman, u.is_blocked = lang, phone, admin, woman, blocked
        return uid

    async def driver(self, uid: int, plate: str = "30A123BC", lang: str = "uz_new", name: str = "Karim",
                     username: str | None = None, verified: bool = False, docs: bool = False):
        await self.user(uid, lang=lang, name=name, username=username, phone="+998903333333")
        async with session_scope(self.maker) as s:
            u = await users.get_or_create_user(s, uid)
            d = await drivers.register_driver(s, u, self.settings, car_make="Cobalt", car_color="oq", car_plate=plate)
            if docs or verified:
                d.license_file_id, d.techpass_file_id = "lic", "tp"
            if verified:
                d.verified = True
            return d.id

    async def db(self, fn):
        async with session_scope(self.maker) as s:
            return await fn(s)

    # ---------- feeding updates ----------
    def _from(self, uid: int, lang: str = "uz", name: str = "Ali", username: str | None = None) -> dict:
        d = {"id": uid, "is_bot": False, "first_name": name, "language_code": lang}
        if username:
            d["username"] = username
        return d

    def _chat(self, uid: int, kind: str = "private") -> dict:
        return {"id": uid if kind == "private" else -uid, "type": kind}

    async def feed(self, **update) -> None:
        await self.dp.feed_raw_update(self.bot, {"update_id": next(self._upd), **update})

    async def say(self, uid: int, text: str | None = None, *, chat: str = "private", **extra) -> None:
        msg = {"message_id": next(self._mid), "date": int(time.time()), "chat": self._chat(uid, chat),
               "from": self._from(uid, name=extra.pop("name", "Ali"), username=extra.pop("username", None))}
        if text is not None:
            msg["text"] = text
            if text.startswith("/"):
                cmd = text.split()[0]
                msg["entities"] = [{"type": "bot_command", "offset": 0, "length": len(cmd)}]
        msg.update(extra)
        await self.feed(message=msg)

    async def press(self, uid: int, data: str, name: str = "Ali") -> None:
        await self.feed(callback_query={
            "id": str(next(self._upd)), "from": self._from(uid, name=name), "chat_instance": "ci", "data": data,
            "message": {"message_id": 500, "date": int(time.time()), "chat": self._chat(uid),
                        "from": {"id": BOT_ID, "is_bot": True, "first_name": "TulporGo"}, "text": "card"}})

    async def contact(self, uid: int, phone: str = "+998901234567", owner: int | None = None) -> None:
        await self.say(uid, None, contact={"phone_number": phone, "first_name": "Ali", "user_id": owner or uid})

    async def photo(self, uid: int, file_id: str = "photo-1") -> None:
        await self.say(uid, None, photo=[{"file_id": file_id, "file_unique_id": file_id + "u", "width": 90, "height": 90}])

    async def guest(self, uid: int, text: str, query_id: str = "gq-1") -> None:
        await self.feed(guest_message={"message_id": next(self._mid), "date": int(time.time()),
                                       "chat": {"id": -1001, "type": "supergroup", "title": "Taksi"},
                                       "from": self._from(uid), "text": text, "guest_query_id": query_id})

    # ---------- reading what the bot sent ----------
    def sent(self, uid: int, kinds=("SendMessage", "SendRichMessage", "EditMessageText", "SendPhoto")) -> list:
        return [c for c in self.fake.calls if type(c).__name__ in kinds and getattr(c, "chat_id", None) == uid]

    def texts(self, uid: int, raw: bool = False) -> list[str]:
        """What the user reads (tags stripped); `raw=True` keeps the HTML (tg-emoji, tg-time...)."""
        return [body(c) if raw else strip_tags(body(c)) for c in self.sent(uid)]

    def said(self, uid: int, text: str) -> bool:
        """Did any message to `uid` contain `text`?"""
        return any(text in t for t in self.texts(uid))

    def last(self, uid: int):
        calls = self.sent(uid)
        assert calls, f"the bot sent nothing to {uid}"
        return calls[-1]

    def last_text(self, uid: int, raw: bool = False) -> str:
        return body(self.last(uid)) if raw else strip_tags(body(self.last(uid)))

    def buttons(self, uid: int) -> list[str]:
        """callback_data of the newest message to `uid` that has an inline keyboard."""
        for c in reversed(self.sent(uid)):
            data = markup_data(getattr(c, "reply_markup", None))
            if data:
                return data
        return []

    def all_buttons(self, uid: int):
        out = []
        for c in self.sent(uid):
            out += markup_buttons(getattr(c, "reply_markup", None))
        return out

    def alerts(self) -> list[str]:
        return [c.text for c in self.fake.calls if type(c).__name__ == "AnswerCallbackQuery" and c.show_alert]

    def methods(self, name: str) -> list:
        return [c for c in self.fake.calls if type(c).__name__ == name]

    def pick(self, uid: int, prefix: str) -> str:
        found = [d for d in self.buttons(uid) if d.startswith(prefix)]
        assert found, f"no button {prefix!r} for {uid}; have {self.buttons(uid)}"
        return found[0]


async def walk_to_confirm(env, uid=1, seats="st:2", note="yuk bor"):
    """buttons flow: Qo'shrabot (whole district) → Samarqand (whole city) → tomorrow 08:30 → seats → note."""
    await env.press(uid, "ord:new")
    await env.press(uid, f"pd:f:{env.qosh}")
    await env.press(uid, f"pk:f:{env.qosh}")
    await env.press(uid, f"pd:t:{env.sam}")
    await env.press(uid, f"pk:t:{env.sam}")
    await env.press(uid, "tm:d:1")
    await env.press(uid, "tm:h:1:8")
    await env.press(uid, "tm:m:1:8:30")
    await env.press(uid, seats)
    if note:
        await env.say(uid, note)
    else:
        await env.press(uid, "nt:skip")


async def new_request(env, uid: int, seats: int = 1, hint: int | None = None, **kw) -> int:
    """A request created through the service (fast); the event is published AFTER the commit like in production."""
    from sqlalchemy import select
    from tulporgo_core.events import RequestCreated
    from tulporgo_core.models import User
    from tulporgo_core.services import rides

    async def create(s):
        p = await s.scalar(select(User).where(User.tg_id == uid))
        r = await rides.create_request(s, p, env.settings, from_text="Qo'shrabot", to_text="Samarqand",
                                       from_place_id=env.qosh, to_place_id=env.sam, seats=seats, **kw)
        if hint:
            r.price_hint = hint
        return r.id
    rid = await env.db(create)
    await env.bus.publish(RequestCreated(rid))
    return rid


async def offer_by_ui(env, driver_uid: int, rid: int, amount: str) -> int:
    """The driver taps "Taklif berish" → "Boshqa narx" and types the price. Returns the offer id."""
    from sqlalchemy import select
    from tulporgo_core.models import Offer
    await env.press(driver_uid, f"ofp:{rid}")
    await env.press(driver_uid, f"ofc:{rid}")
    await env.say(driver_uid, amount)
    return await env.db(lambda s: s.scalar(select(Offer.id).where(Offer.request_id == rid).order_by(Offer.id.desc())))


# ---------- fixtures (imported by every test module: a `conftest.py` here would shadow the core tests' `conftest`) ----------

@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """No real sleeping and no rate limit in tests; nothing here touches the network."""
    async def no_sleep(_):
        return None
    monkeypatch.setattr(delivery, "sleep", no_sleep)
    monkeypatch.setattr(delivery.LIMITER, "rate", 0.0)
    delivery.LIMITER._next = 0.0
    # The flows below were written for the plain cards; the optional features (ON in production, decision 55) are
    # switched on per test in test_optional_features.py and in the defaults test there.
    for var in ("TULPORGO_TRIP_TOPICS", "TULPORGO_EPHEMERAL_GROUP", "TULPORGO_WIDGETS"):
        monkeypatch.setenv(var, "false")


@pytest.fixture
async def env(tmp_path):
    e = await Env(tmp_path).start()
    await e.seed_places()
    yield e
    await e.stop()


@pytest.fixture
async def free_env(tmp_path):
    from datetime import date, timedelta
    e = await Env(tmp_path, free_period_until=date.today() + timedelta(days=30)).start()
    await e.seed_places()
    yield e
    await e.stop()
