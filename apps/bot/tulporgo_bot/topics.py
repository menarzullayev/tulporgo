"""Trip topics in the bot's private chats (Bot API 9.3–9.4): one topic per party per trip, named from route and time.
Everything is best effort — any Telegram error means "use the main chat", exactly as before the feature existed."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.methods import CreateForumTopic
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tulporgo_core.db import session_scope
from tulporgo_core.models import Driver, RideRequest, Trip, User

from . import delivery
from .config import BotExtra
from .handlers.common import get_required, to_local, user_t

log = logging.getLogger(__name__)
ICON = {"passenger": 9367192, "driver": 16766590}          # green / yellow (colours Telegram allows)
_available: dict[int, bool] = {}                            # bot id → getMe().has_topics_enabled (cached once true)


def topic_name(r: RideRequest, t) -> str:
    when = to_local(r.depart_at).strftime("%H:%M") if r.depart_at else t("bot.when_now")
    return t("bot.topic.name", route=f"{r.from_text} → {r.to_text}", time=when)[:128]


def thread_of(trip: Trip, role: str, extra: BotExtra) -> int | None:
    """Stored topic of this party, only while the feature is on (flag off → never touch topics)."""
    if not extra.trip_topics:
        return None
    return trip.driver_topic_id if role == "driver" else trip.passenger_topic_id


async def topics_enabled(bot: Bot) -> bool:
    """getMe says whether topics are on for this bot's private chats (BotFather). A positive answer is cached."""
    if _available.get(bot.id):
        return True
    try:
        me = await bot.get_me()
    except TelegramAPIError as e:
        delivery.warn_once("topic-getme", "getMe failed (%s) — no trip topics", e)
        return False
    ok = bool(getattr(me, "has_topics_enabled", None))
    if ok:
        _available[bot.id] = True
    else:
        delivery.warn_once("topic-off", "topics are not enabled for this bot in BotFather — trip cards stay in the main chat")
    return ok


async def ensure_topic(bot: Bot, maker: async_sessionmaker[AsyncSession], extra: BotExtra, trip_id: int,
                       role: str) -> int | None:
    """Thread id of the party's topic for this trip: the stored one, or a freshly created (and stored) one."""
    if not extra.trip_topics:
        return None
    async with session_scope(maker) as s:
        trip = await s.get(Trip, trip_id)
        if trip is None:
            return None
        stored = thread_of(trip, role, extra)
        if stored:
            return stored
        r = await get_required(s, RideRequest, trip.request_id)
        d = await get_required(s, Driver, trip.driver_id)
        user = d.user if role == "driver" else await get_required(s, User, trip.passenger_id)
        chat_id, name = user.tg_id, topic_name(r, user_t(user))
    if not await topics_enabled(bot):
        return None
    try:
        topic = await delivery.call(bot, CreateForumTopic(chat_id=chat_id, name=name, icon_color=ICON[role]))
    except TelegramAPIError as e:
        delivery.warn_once("topic-create", "createForumTopic failed (%s) — trip cards stay in the main chat", e)
        return None
    if topic is None:                                       # the user blocked the bot
        return None
    async with session_scope(maker) as s:
        trip = await s.get(Trip, trip_id)
        if trip is not None:
            setattr(trip, "driver_topic_id" if role == "driver" else "passenger_topic_id", topic.message_thread_id)
    return topic.message_thread_id
