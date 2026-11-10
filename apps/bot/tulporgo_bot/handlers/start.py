"""/start (with deep links), language picker, /til, /yordam, "ayol yo'lovchi" marker."""
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core import i18n
from tulporgo_core.config import Settings
from tulporgo_core.enums import Lang
from tulporgo_core.errors import Invalid
from tulporgo_core.models import Driver, User
from tulporgo_core.services import drivers, referral, rides

from ..config import get_extra
from . import commands, driver as driver_flow, order
from .cards import trip_status
from .common import PRIVATE, bind, btn, kb, lang_name, parse_cb, show

router = Router(name="start")
router.message.filter(F.chat.type == PRIVATE)


def start_keyboard(settings: Settings, t):
    rows = [[btn(f"🚕 {t('bot.btn.order')}", "ord:new", style="primary")]]
    if settings.miniapp_url:
        rows.append([btn(f"🗺 {t('bot.btn.miniapp')}", web_app=settings.miniapp_url)])
    rows.append([btn(f"🤝 {t('bot.btn.driver')}", "drv:reg")])
    return kb(*rows)


def lang_keyboard():
    codes = [Lang.UZ_NEW, Lang.UZ_LATN, Lang.UZ_CYRL, Lang.RU, Lang.EN]
    return kb(*[[btn(lang_name(c), f"lang:{c.value}")] for c in codes])


async def apply_referral(session: AsyncSession, user: User, payload: str | None) -> None:
    """`?start=ref_<CODE>`: remember the inviter. Existing drivers and self-invites are ignored (decision 52 pays
    only when a NEW driver is verified)."""
    code = referral.code_from_start(payload)
    if not code or await drivers.get_driver(session, user):
        return
    try:
        await referral.link(session, user, code)
    except Invalid:
        return


async def greet(msg: Message, user: User, settings: Settings, t, ref_note: bool = False) -> None:
    text = t("bot.start")                              # approved text (decision 40)
    if ref_note:
        text += "\n\n" + t("bot.ref.note", days=settings.referral_bonus_days)
    await show(msg, text, start_keyboard(settings, t))


async def run_start(msg: Message, payload: str | None, *, state: FSMContext, session: AsyncSession, user: User,
                    settings: Settings, bot: Bot, t) -> None:
    """The part of /start that needs the language: greeting or the deep link's target."""
    await state.clear()
    is_driver = await drivers.get_driver(session, user)
    await commands.sync_chat(bot, user.tg_id, i18n.lang_of(user.lang), bool(is_driver))
    p = payload or ""
    if p == "driver":
        return await driver_flow.begin(msg, state, session, user, settings, t)
    if p == "faq":
        return await send_help(msg, user, settings, t)
    if p in ("elon", "obuna"):
        return await show(msg, t("bot.hint.cmd", cmd=f"/{p}"))
    if p.startswith("trip_"):
        return await show_shared_trip(msg, session, p[5:], t)
    if p.startswith("g_"):
        if await order.start_from_guest(msg, state, session, user, settings, t, p):
            return None
    await greet(msg, user, settings, t, ref_note=bool(user.referred_by_id) and not is_driver)
    return None


@router.message(CommandStart())
async def cmd_start(msg: Message, command: CommandObject, state: FSMContext, session: AsyncSession, user: User,
                    settings: Settings, bot: Bot, t) -> None:
    await state.clear()
    await apply_referral(session, user, command.args)
    if user.lang is None:                              # first start: ask the language, remember the deep link
        await state.update_data(pending=command.args or "")
        await show(msg, i18n.t("bot.lang.pick", "uz_new") + "\n" + i18n.t("bot.lang.pick", "ru") + "\n"
                   + i18n.t("bot.lang.pick", "en"), lang_keyboard())
        return
    await run_start(msg, command.args, state=state, session=session, user=user, settings=settings, bot=bot, t=t)


@router.message(Command("til"))
async def cmd_lang(msg: Message, state: FSMContext, t) -> None:
    await state.clear()
    await show(msg, t("bot.lang.pick"), lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def pick_lang(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, settings: Settings,
                    bot: Bot) -> None:
    parts = parse_cb(cb.data, 2)
    if not parts or parts[1] not in {lg.value for lg in Lang}:
        await cb.answer()
        return
    user.lang = parts[1]
    t = bind(parts[1])
    data = await state.get_data()
    await cb.answer()
    await show(cb, t("bot.lang.saved"))
    is_driver = await drivers.get_driver(session, user)
    await commands.sync_chat(bot, user.tg_id, i18n.lang_of(parts[1]), bool(is_driver))
    if "pending" in data and isinstance(cb.message, Message):       # first start → continue with the deep link
        await run_start(cb.message, data["pending"] or None, state=state, session=session, user=user,
                        settings=settings, bot=bot, t=t)


async def show_shared_trip(msg: Message, session: AsyncSession, token: str, t) -> None:
    trip = await rides.trip_by_share_token(session, token)
    r = await rides.get_request(session, trip.request_id)
    d = await session.get(Driver, trip.driver_id)
    await show(msg, trip_status(trip, r, d, t))


# ---------- help, complaints entry, women marker ----------

def help_keyboard(user: User, settings: Settings, t):
    extra = get_extra()
    mark = "✅" if user.is_woman else "▫️"
    return kb([btn(f"📝 {t('bot.btn.complaint')}", "cm:0", style="danger")],
              [btn(f"{mark} {t('bot.btn.women')}", "wm:t")],
              [btn(f"💬 {t('bot.btn.qa_chat')}", url=f"https://t.me/{extra.chat_username}"),
               btn(f"📢 {t('bot.btn.channel')}", url=f"https://t.me/{settings.channel_username}")])


async def send_help(msg: Message | CallbackQuery, user: User, settings: Settings, t) -> None:
    await show(msg, t("bot.help"), help_keyboard(user, settings, t))


@router.message(Command("yordam"))
async def cmd_help(msg: Message, state: FSMContext, user: User, settings: Settings, t) -> None:
    await state.clear()
    await send_help(msg, user, settings, t)


@router.callback_query(F.data == "wm:t")
async def toggle_women(cb: CallbackQuery, user: User, settings: Settings, t) -> None:
    """Decision 13: "ayol yo'lovchi" marker — shown to drivers on that passenger's requests."""
    user.is_woman = not user.is_woman
    await cb.answer(t("bot.women.on" if user.is_woman else "bot.women.off"))
    await send_help(cb, user, settings, t)
