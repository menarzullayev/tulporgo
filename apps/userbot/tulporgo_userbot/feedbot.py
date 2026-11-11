"""Bot side of the group feed (decision 73): the "Yo'lovchi qidirish" screen in /elon (filters on/off, pause all,
Mini App link), the card buttons ("Olindi", "Pauza") and linking the driver's own channel — the driver adds
@tulporgobot as an admin there and the bot remembers it (removing the bot unlinks it).
Included by `tulporgo_userbot.bot.router`; handlers get the shared context (session, settings, user, t)."""
import logging

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from sqlalchemy import delete, select
from tulporgo_core.models import Driver, DriverFilter, FeedCard

from . import service

log = logging.getLogger(__name__)
router = Router(name="userbot_feed")
ADMIN = ("administrator", "creator")


def _btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    if style:
        return InlineKeyboardButton(text=text, callback_data=data, style=style)
    return InlineKeyboardButton(text=text, callback_data=data)


async def _driver(session, user) -> Driver | None:
    if user is None:
        return None
    return (await session.execute(select(Driver).where(Driver.user_id == user.id))).scalar_one_or_none()


async def _screen(session, settings, driver: Driver, t) -> tuple[str, InlineKeyboardMarkup]:
    filters = (await session.execute(select(DriverFilter).where(DriverFilter.driver_id == driver.id)
                                     .order_by(DriverFilter.id))).scalars().all()
    channel = t("feed.channel.linked") if driver.delivery_chat_id else t("feed.channel.none", bot=settings.bot_username)
    state = t("feed.state.paused") if driver.feed_paused else t("feed.state.on")
    text = t("feed.menu", state=state, channel=channel, count=len(filters))
    rows = [[_btn(("✅ " if f.enabled else "▫️ ") + f.name[:30], f"fd:f:{f.id}")] for f in filters]
    rows.append([InlineKeyboardButton(text=t("feed.btn.edit"), style="primary",
                                      web_app=WebAppInfo(url=f"{settings.miniapp_url}?page=feed"))])
    rows.append([_btn(t("feed.btn.resume_all"), "fd:pauseall", "success") if driver.feed_paused
                 else _btn(t("feed.btn.pause_all"), "fd:pauseall")])
    rows.append([_btn(t("feed.btn.back"), "ub:menu")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _show(cq: CallbackQuery, session, settings, driver: Driver, t) -> None:
    text, markup = await _screen(session, settings, driver, t)
    if isinstance(cq.message, Message):
        try:
            await cq.message.edit_text(text, reply_markup=markup)
        except Exception:                                       # noqa: BLE001 - unchanged text or too old to edit
            await cq.message.answer(text, reply_markup=markup)
    await cq.answer()


@router.callback_query(F.data == "fd:menu")
async def cb_feed(cq: CallbackQuery, session, settings, user, t, **_):
    driver = await _driver(session, user)
    if driver is None:
        await cq.answer(t("feed.not_driver"), show_alert=True)
        return
    await _show(cq, session, settings, driver, t)


@router.callback_query(F.data.startswith("fd:f:"))
async def cb_toggle_filter(cq: CallbackQuery, session, settings, user, t, **_):
    driver = await _driver(session, user)
    fid = int((cq.data or "fd:f:0").split(":")[2])
    f = await session.get(DriverFilter, fid)
    if driver is None or f is None or f.driver_id != driver.id:          # never someone else's filter
        await cq.answer(t("feed.not_yours"), show_alert=True)
        return
    f.enabled = not f.enabled
    await session.flush()
    await _show(cq, session, settings, driver, t)


@router.callback_query(F.data == "fd:pauseall")
async def cb_pause_all(cq: CallbackQuery, session, settings, user, t, **_):
    driver = await _driver(session, user)
    if driver is None:
        await cq.answer(t("feed.not_driver"), show_alert=True)
        return
    driver.feed_paused = not driver.feed_paused
    await session.flush()
    await _show(cq, session, settings, driver, t)


# ---------------------------------------------------------------- buttons on a card

async def _card_owner(session, cq: CallbackQuery, user) -> tuple[Driver | None, FeedCard | None]:
    driver = await _driver(session, user)
    msg = cq.message
    if driver is None or msg is None:
        return driver, None
    card = (await session.execute(select(FeedCard).where(FeedCard.chat_id == msg.chat.id,
                                                         FeedCard.message_id == msg.message_id))).scalar_one_or_none()
    return driver, card


@router.callback_query(F.data == "feed:taken")
async def cb_taken(cq: CallbackQuery, session, user, t, **_):
    driver, card = await _card_owner(session, cq, user)
    if driver is None or card is None or card.driver_id != driver.id:     # a channel member who is not the owner
        await cq.answer(t("feed.not_yours"), show_alert=True)
        return
    await session.execute(delete(FeedCard).where(FeedCard.id == card.id))
    if isinstance(cq.message, Message):
        try:
            await cq.message.delete()
        except Exception:                                       # noqa: BLE001
            log.debug("card already gone")
    await cq.answer(t("feed.taken.ok"))


@router.callback_query(F.data == "feed:pause")
async def cb_card_pause(cq: CallbackQuery, session, user, t, **_):
    driver, card = await _card_owner(session, cq, user)
    if driver is None or card is None or card.driver_id != driver.id:
        await cq.answer(t("feed.not_yours"), show_alert=True)
        return
    driver.feed_paused = True
    await session.flush()
    await cq.answer(t("feed.paused.ok"), show_alert=True)


# ---------------------------------------------------------------- the driver's own channel

@router.my_chat_member(F.chat.type.in_({"channel", "group", "supergroup"}))
async def on_bot_membership(event: ChatMemberUpdated, session, settings, user, t, **_):
    """The driver made @tulporgobot an admin of his channel/group -> cards go there. Removed -> back to the bot chat."""
    driver = await _driver(session, user)
    if driver is None:
        return
    status = event.new_chat_member.status
    if status in ADMIN:
        driver.delivery_chat_id = event.chat.id
        await session.flush()
        try:
            if event.bot is not None:
                await event.bot.send_message(event.chat.id, t("feed.channel.ok"))
        except Exception:                                       # noqa: BLE001 - e.g. no right to post in a group
            log.info("could not confirm the delivery chat %s", event.chat.id)
    elif driver.delivery_chat_id == event.chat.id:
        driver.delivery_chat_id = None
        await session.flush()


__all__ = ["router", "service"]
