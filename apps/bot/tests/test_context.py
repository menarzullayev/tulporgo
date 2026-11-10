from datetime import datetime

from aiogram import Bot, Router
from aiogram.types import Chat, Message, Update
from aiogram.types import User as TgUser
from tulporgo_bot.main import build_dispatcher
from tulporgo_core.config import Settings
from tulporgo_core.db import Base, make_engine, make_sessionmaker
from tulporgo_core.events import InMemoryBus


async def test_middleware_injects_user_lang_and_t(tmp_path):
    eng = make_engine(f"sqlite+aiosqlite:///{(tmp_path / 'b.db').as_posix()}")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    maker = make_sessionmaker(eng)
    dp = build_dispatcher(Settings(bot_token="1:X", admin_ids=[7]), maker, InMemoryBus())
    seen = {}
    probe = Router()

    @probe.message()
    async def h(message, user, lang, t, session, settings, bus):
        seen.update(tg=user.tg_id, lang=lang, txt=t("common.yes"), admin=user.is_admin)
    dp.include_router(probe)
    msg = Message(message_id=1, date=datetime.now(), chat=Chat(id=7, type="private"), text="hi",
                  from_user=TgUser(id=7, is_bot=False, first_name="A", language_code="ru"))
    await dp.feed_update(Bot("1:X"), Update(update_id=1, message=msg))
    assert seen == {"tg": 7, "lang": "ru", "txt": "Да", "admin": True}
    await eng.dispose()
