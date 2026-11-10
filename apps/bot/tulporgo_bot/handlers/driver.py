"""Driver onboarding (decision 12): phone via the contact button → car (make, colour, plate, seats, photo) → home
district → `drivers.register_driver`; optional documents → admin review → "Tasdiqlangan" badge; referral link."""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core import i18n
from tulporgo_core.config import Settings
from tulporgo_core.db import utcnow
from tulporgo_core.errors import DomainError, Forbidden
from tulporgo_core.models import Driver, Place, User
from tulporgo_core.services import billing, documents, drivers, users

from . import admin, commands, picker
from .common import PRIVATE, btn, esc, int_arg, kb, parse_cb, rating_text, referral_link, say, show, to_local
from .states import Docs, Reg

log = logging.getLogger(__name__)
router = Router(name="driver")
router.message.filter(F.chat.type == PRIVATE)


def own_keyboard(settings: Settings, t, d: Driver | None = None):
    rows = []
    if d is not None and not d.verified:
        rows.append([btn(f"📄 {t('bot.btn.docs')}", "drv:doc")])
    if settings.miniapp_url:
        rows.append([btn(f"🗺 {t('bot.btn.miniapp')}", web_app=settings.miniapp_url)])
    return kb(*rows)


def subscription_line(d: Driver, settings: Settings, t) -> str:
    if billing.in_free_period(settings):
        return t("bot.drv.free_period")
    if d.subscription_until and d.subscription_until > utcnow():
        return t("bot.drv.until", date=to_local(d.subscription_until).strftime("%d.%m.%Y"))
    return t("bot.drv.expired")


async def panel_text(session: AsyncSession, user: User, d: Driver, settings: Settings, t) -> str:
    await users.ensure_referral_code(session, user)
    if d.verified:
        verified = f"✅ {t('bot.verified')}"
    elif d.license_file_id and d.techpass_file_id:
        verified = f"⏳ {t('bot.drv.docs_pending')}"
    else:
        verified = t("bot.drv.not_verified")
    return "\n".join([
        f"<b>{t('bot.drv.panel')}</b>", f"🚗 {esc(d.car_make)}, {esc(d.car_color)}, {esc(d.car_plate)}",
        f"👥 {t('bot.seats_n', n=d.seats)}", f"{rating_text(d, t)} · {verified}", subscription_line(d, settings, t), "",
        t("bot.ref.share", days=settings.referral_bonus_days), referral_link(settings, user)])


async def begin(event, state: FSMContext, session: AsyncSession, user: User, settings: Settings, t) -> None:
    """"Haydovchiman": a driver sees the panel, anyone else starts registration."""
    d = await drivers.get_driver(session, user)
    await state.clear()
    if d is not None:
        await show(event, await panel_text(session, user, d, settings, t), own_keyboard(settings, t, d))
        return
    if user.phone:
        await state.set_state(Reg.make)
        await say(event, t("bot.reg.make"), ReplyKeyboardRemove())
        return
    await state.set_state(Reg.phone)
    await say(event, t("bot.reg.phone"), ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"📱 {t('bot.btn.send_phone')}", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True))


@router.callback_query(F.data == "drv:reg")
async def reg_button(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, settings: Settings,
                     t) -> None:
    await cb.answer()
    await begin(cb, state, session, user, settings, t)


# ---------- registration steps ----------

@router.message(StateFilter(Reg.phone), F.contact)
async def got_contact(msg: Message, state: FSMContext, session: AsyncSession, user: User, t) -> None:
    contact = msg.contact
    if contact is None or msg.from_user is None or contact.user_id != msg.from_user.id:   # not own = not verified
        await show(msg, t("bot.reg.contact_not_own"))
        return
    await users.set_phone(session, user, contact.phone_number)
    await state.set_state(Reg.make)
    await say(msg, t("bot.reg.make"), ReplyKeyboardRemove())


@router.message(StateFilter(Reg.phone), ~F.text.startswith("/"))
async def phone_remind(msg: Message, t) -> None:
    if not (msg.text or "").startswith("/"):
        await show(msg, t("bot.reg.phone_only_button"))


def _short_text(msg: Message, lo: int = 2, hi: int = 64) -> str | None:
    text = (msg.text or "").strip()
    return text if lo <= len(text) <= hi and not text.startswith("/") else None


@router.message(StateFilter(Reg.make), F.text, ~F.text.startswith("/"))
async def got_make(msg: Message, state: FSMContext, t) -> None:
    if (make := _short_text(msg)) is None:
        await show(msg, t("bot.reg.bad_text"))
        return
    await state.update_data(make=make)
    await state.set_state(Reg.color)
    await show(msg, t("bot.reg.color"))


@router.message(StateFilter(Reg.color), F.text, ~F.text.startswith("/"))
async def got_color(msg: Message, state: FSMContext, t) -> None:
    if (color := _short_text(msg, hi=32)) is None:
        await show(msg, t("bot.reg.bad_text"))
        return
    await state.update_data(color=color)
    await state.set_state(Reg.plate)
    await show(msg, t("bot.reg.plate"))


@router.message(StateFilter(Reg.plate), F.text, ~F.text.startswith("/"))
async def got_plate(msg: Message, state: FSMContext, t) -> None:
    text = msg.text or ""
    if text.startswith("/"):
        return
    plate = drivers.normalize_plate(text)            # Invalid → "plate format" alert, state kept
    await state.update_data(plate=plate)
    await state.set_state(Reg.seats)
    await show(msg, t("bot.reg.seats"), kb([btn(str(n), f"ds:{n}") for n in (2, 3, 4)],
                                           [btn(str(n), f"ds:{n}") for n in (5, 6, 7)]))


async def _after_seats(event, state: FSMContext, n: int, t) -> None:
    await state.update_data(seats=n)
    await state.set_state(Reg.photo)
    await show(event, t("bot.reg.photo"))


@router.callback_query(StateFilter(Reg.seats), F.data.startswith("ds:"))
async def seats_button(cb: CallbackQuery, state: FSMContext, t) -> None:
    parts = parse_cb(cb.data, 2)
    n = int_arg(parts[1]) if parts else None
    await cb.answer()
    if n is not None and 1 <= n <= 8:
        await _after_seats(cb, state, n, t)


@router.message(StateFilter(Reg.seats), F.text, ~F.text.startswith("/"))
async def seats_typed(msg: Message, state: FSMContext, t) -> None:
    text = (msg.text or "").strip()
    if text.isdigit() and 1 <= int(text) <= 8:
        await _after_seats(msg, state, int(text), t)
    elif not text.startswith("/"):
        await show(msg, t("bot.seats.bad"))


@router.message(StateFilter(Reg.photo), F.photo)
async def got_photo(msg: Message, state: FSMContext, session: AsyncSession, t, lang) -> None:
    if not msg.photo:                                    # F.photo guarantees it; narrows the Optional
        return
    await state.update_data(photo=msg.photo[-1].file_id)
    await picker.ask_place(msg, state, session, t, lang, "h")


@router.message(StateFilter(Reg.photo), ~F.text.startswith("/"))
async def photo_remind(msg: Message, t) -> None:
    if not (msg.text or "").startswith("/"):
        await show(msg, t("bot.reg.photo_only"))


async def finish(event, state: FSMContext, *, place: Place | None, session: AsyncSession, user: User,
                 settings: Settings, bus, bot: Bot, t, lang, **_) -> None:
    data = await state.get_data()
    d = await drivers.register_driver(session, user, settings, car_make=data["make"], car_color=data["color"],
                                      car_plate=data["plate"], seats=data.get("seats", 4),
                                      car_photo_file_id=data.get("photo"), home_place_id=place.id if place else None,
                                      bus=bus)
    await state.clear()
    await commands.sync_chat(bot, user.tg_id, i18n.lang_of(lang), True)
    await say(event, f"🎉 {t('bot.reg.done')}", ReplyKeyboardRemove())
    await say(event, await panel_text(session, user, d, settings, t), own_keyboard(settings, t, d))


async def _finish_chosen(event, state, *, place, text, **ctx) -> None:
    await finish(event, state, place=place, **ctx)


picker.register_chooser("h", _finish_chosen)


@router.callback_query(StateFilter(Reg.home), F.data == "ph:skip")
async def skip_home(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, settings: Settings, bus,
                    bot: Bot, t, lang) -> None:
    await cb.answer()
    await finish(cb, state, place=None, session=session, user=user, settings=settings, bus=bus, bot=bot, t=t,
                 lang=lang)


# ---------- optional documents → "Tasdiqlangan" ----------

@router.callback_query(F.data == "drv:doc")
async def docs_start(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, t) -> None:
    d = await drivers.get_driver(session, user)
    if d is None:
        raise Forbidden("not_driver")
    await cb.answer()
    if d.verified:
        await show(cb, f"✅ {t('bot.drv.already_verified')}")
        return
    await state.set_state(Docs.license)
    await show(cb, t("bot.docs.license"))


@router.message(StateFilter(Docs.license), F.photo)
async def got_license(msg: Message, state: FSMContext, t) -> None:
    if not msg.photo:
        return
    await state.update_data(license=msg.photo[-1].file_id)
    await state.set_state(Docs.techpass)
    await show(msg, t("bot.docs.techpass"))


async def _download(bot: Bot, file_id: str) -> bytes | None:
    """The bytes of a Telegram file, or None when it cannot be fetched (the bytes are never logged)."""
    try:
        buf = await bot.download(file_id)
    except Exception as e:                                # Telegram API error, network, timeout
        log.warning("document download failed: %s", type(e).__name__)
        return None
    return buf.read() if buf is not None else None


@router.message(StateFilter(Docs.techpass), F.photo)
async def got_techpass(msg: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings,
                       bot: Bot, t) -> None:
    d = await drivers.get_driver(session, user)
    if d is None:
        raise Forbidden("not_driver")
    if not msg.photo:
        return
    data = await state.get_data()
    license_id, techpass_id = data["license"], msg.photo[-1].file_id          # largest photo size
    if documents.enabled(settings):
        # decision 57: the encrypted server copy is made first and all-or-nothing; nothing is submitted without it
        lic = await _download(bot, license_id)
        if lic is None:
            await state.set_state(Docs.license)
            await show(msg, t("bot.docs.download_failed"))
            await show(msg, t("bot.docs.license"))
            return
        tp = await _download(bot, techpass_id)
        if tp is None:
            await show(msg, t("bot.docs.download_failed"))                    # stays on the tech passport step
            return
        try:
            async with session.begin_nested():
                await documents.store(session, d, "license", lic, documents.sniff(lic) or "", settings)
                await documents.store(session, d, "techpass", tp, documents.sniff(tp) or "", settings)
        except DomainError as e:
            log.warning("server copy of driver %s documents refused: %s", d.id, e.code)
            await state.set_state(Docs.license)
            await show(msg, t("bot.docs.download_failed"))
            await show(msg, t("bot.docs.license"))
            return
    await drivers.submit_documents(session, d, license_id, techpass_id)
    await state.clear()
    await show(msg, t("bot.docs.sent"))
    await admin.notify_new_documents(bot, session, settings, d)


@router.message(StateFilter(Docs.license, Docs.techpass), ~F.text.startswith("/"))
async def docs_remind(msg: Message, t) -> None:
    if not (msg.text or "").startswith("/"):
        await show(msg, t("bot.docs.photo_only"))
