"""aiogram Router for /obuna: plans -> months -> provider -> checkout; Stars invoices, P2P receipts + admin review.

Handlers receive the W1 context (`session, settings, bus, user, lang, t`). Callback data (<= 64 bytes):
  pay:pl:<plan>                      choose months
  pay:mo:<plan>:<months>             choose provider
  pay:go:<plan>:<months>:<provider>  checkout   (suffix :r = Stars recurring)
  pay:rc:<payment_id>                P2P: ask for the receipt photo
  pay:ok:<id> / pay:no:<id>          admin approve / reject
Everything works with plain text + plain buttons; styles (Bot API 9.4) are only decoration.
"""
import logging
import re
from datetime import date, datetime
from typing import Any

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotSubscriptionUpdated,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope
from tulporgo_core.emoji import decorate
from tulporgo_core.enums import Plan
from tulporgo_core.errors import DomainError
from tulporgo_core.i18n import lang_of, t
from tulporgo_core.models import Payment, User
from tulporgo_core.services import billing
from tulporgo_core.services.drivers import get_driver

from . import TERMS_URL, service
from .jobs import run_reminders, setup_jobs  # noqa: F401  (setup_jobs is called by the bot)
from .providers import available_providers, p2p, stars

log = logging.getLogger(__name__)
router = Router(name="payments")
MONTHS = (1, 3, 6, 12)
STYLE = {"p2p": None, "stars": "primary", "click": "primary", "payme": "primary"}


class Receipt(StatesGroup):
    waiting = State()


# ---------------------------------------------------------------- helpers

def money(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def fmt_date(dt: date | datetime | None) -> str:
    return dt.strftime("%d.%m.%Y") if dt else "—"


def plan_name(plan: str, lang) -> str:
    return t(f"pay.plan.{plan}", lang)


def btn(text: str, *, data: str | None = None, url: str | None = None, style: str | None = None):
    return InlineKeyboardButton(text=text, callback_data=data, url=url, style=style)


def kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def reply(message: Message, text: str, markup=None):
    return await message.answer(decorate(text), reply_markup=markup)


def cb_message(cb: CallbackQuery) -> Message | None:
    """The message a button sits on when it can be edited. Inline-mode callbacks have no message (None) and old
    messages arrive as InaccessibleMessage: it can only be answered, not edited, so it maps to None here too."""
    return cb.message if isinstance(cb.message, Message) else None


def cb_data(cb: CallbackQuery) -> str:
    """Callback data; every handler here is registered with an `F.data` filter, so "" never reaches the split."""
    return cb.data or ""


async def edit_or_send(cb: CallbackQuery, text: str, markup=None) -> None:
    if cb.message is None:                                 # inline-mode callback: nowhere to show it
        return
    msg = cb_message(cb)
    if msg is not None:
        try:
            await msg.edit_text(decorate(text), reply_markup=markup)
            return
        except Exception:                                  # message too old / unchanged: fall back to a new one
            log.debug("edit failed, sending a new message", exc_info=True)
    await cb.message.answer(decorate(text), reply_markup=markup)   # InaccessibleMessage can be answered, not edited


def admin_targets(settings: Settings) -> list[int]:
    ids = list(settings.admin_ids)
    if not ids and settings.owner_chat_id:
        ids.append(settings.owner_chat_id)
    return ids


# ---------------------------------------------------------------- /obuna

async def status_text(s: AsyncSession, user: User, settings: Settings, lang) -> tuple[str, bool]:
    """(text, offer_plans). Free period -> nothing to pay (decision 44)."""
    driver = await get_driver(s, user)
    if driver is None:
        return t("pay.driver_only", lang), False
    if billing.in_free_period(settings):
        # in_free_period() is True only when free_period_until is set
        return t("pay.status.free", lang, date=fmt_date(settings.free_period_until)), False
    if billing.subscription_active(driver, settings):
        head = t("pay.status.active", lang, plan=plan_name(driver.plan or Plan.BASIC, lang),
                 date=fmt_date(driver.subscription_until))
    else:
        head = t("pay.status.inactive", lang)
    return head, True


def plans_markup(lang) -> InlineKeyboardMarkup:
    return kb([[btn(t("pay.btn.plan", lang, plan=plan_name(p, lang), price=money(billing.price_of(p, 1))),
                    data=f"pay:pl:{p}")] for p in Plan])


@router.message(Command("obuna"))
async def cmd_obuna(message: Message, session: AsyncSession, settings: Settings, user: User, lang, state: FSMContext):
    await state.clear()
    text, offer = await status_text(session, user, settings, lang)
    if not offer:
        return await reply(message, text)
    lines = [text, "", t("pay.choose_plan", lang)]
    for p in (Plan.PRO, Plan.BUSINESS):
        lines.append(f"• {plan_name(p, lang)} — {t(f'pay.plan.{p}.info', lang)}")
    await reply(message, "\n".join(lines), plans_markup(lang))


async def _guard(cb: CallbackQuery, session, settings, user, lang) -> bool:
    """Plan/month/provider screens are only for drivers outside the free period."""
    if billing.in_free_period(settings):
        await cb.answer(t("pay.free_period_no_checkout", lang), show_alert=True)
        return False
    if await get_driver(session, user) is None:
        await cb.answer(t("pay.driver_only", lang), show_alert=True)
        return False
    return True


@router.callback_query(F.data.startswith("pay:pl:"))
async def cb_plan(cb: CallbackQuery, session, settings, user, lang):
    if not await _guard(cb, session, settings, user, lang):
        return
    try:
        plan = service.parse_plan(cb_data(cb).split(":")[2])
    except DomainError:
        return await cb.answer()
    rows = [[btn(t("pay.btn.months", lang, n=m, price=money(billing.price_of(plan, m))),
                 data=f"pay:mo:{plan}:{m}")] for m in MONTHS]
    rows.append([btn(t("common.back", lang), data="pay:home")])
    await edit_or_send(cb, t("pay.choose_months", lang, plan=plan_name(plan, lang)), kb(rows))
    await cb.answer()


@router.callback_query(F.data == "pay:home")
async def cb_home(cb: CallbackQuery, session, settings, user, lang):
    if not await _guard(cb, session, settings, user, lang):
        return
    await edit_or_send(cb, t("pay.choose_plan", lang), plans_markup(lang))
    await cb.answer()


@router.callback_query(F.data.startswith("pay:mo:"))
async def cb_months(cb: CallbackQuery, session, settings, user, lang):
    if not await _guard(cb, session, settings, user, lang):
        return
    try:
        _, _, plan_s, months_s = cb_data(cb).split(":")
        plan, months = service.parse_plan(plan_s), int(months_s)
        price = billing.price_of(plan, months)
    except (ValueError, DomainError):
        return await cb.answer()
    names = [n for n in available_providers(settings) if n != "other"]
    if not names:
        await edit_or_send(cb, t("pay.no_providers", lang))
        return await cb.answer()
    rows = [[btn(t(f"pay.provider.{n}", lang), data=f"pay:go:{plan}:{months}:{n}", style=STYLE.get(n))]
            for n in names]
    rows.append([btn(t("common.back", lang), data=f"pay:pl:{plan}")])
    await edit_or_send(cb, t("pay.choose_provider", lang, plan=plan_name(plan, lang), months=months,
                             price=money(price)), kb(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("pay:go:"))
async def cb_terms(cb: CallbackQuery, session, settings, user, lang):
    """Step before any payment: show the terms and require one explicit confirm. Nothing is created here."""
    if not await _guard(cb, session, settings, user, lang):
        return
    try:
        _, _, plan_s, months_s, provider = cb_data(cb).split(":")
        plan, months = service.parse_plan(plan_s), int(months_s)
        price = billing.price_of(plan, months)
    except (ValueError, DomainError):
        return await cb.answer()
    if provider not in available_providers(settings) or provider == "other":
        return await cb.answer(t("pay.provider_unavailable", lang), show_alert=True)
    cur = f"{stars.expected_amount(plan, months, settings)} Stars" if provider == "stars" else f"{money(price)} so'm"
    rows = [[btn(t("pay.terms.btn_read", lang), url=TERMS_URL)],
            [btn(t("pay.terms.btn_confirm", lang), data=f"pay:tc:{plan}:{months}:{provider}", style="success")],
            [btn(t("common.back", lang), data=f"pay:mo:{plan}:{months}")]]
    await edit_or_send(cb, t("pay.terms.accept", lang, plan=plan_name(plan, lang), months=months, price=cur,
                             url=TERMS_URL), kb(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("pay:tc:"))
async def cb_go(cb: CallbackQuery, session: AsyncSession, settings: Settings, user: User, lang, bot: Bot,
                state: FSMContext):
    parts = cb_data(cb).split(":")
    try:
        plan_s, months, provider = parts[2], int(parts[3]), parts[4]
    except (IndexError, ValueError):
        return await cb.answer()
    try:
        c = await service.start_checkout(session, user, settings, provider, plan_s, months)
    except DomainError as e:
        key = {"free_period": "pay.free_period_no_checkout", "driver_required": "pay.driver_only",
               "provider_unavailable": "pay.provider_unavailable"}.get(e.code, "common.error")
        return await cb.answer(t(key, lang), show_alert=True)
    p, start = c.payment, c.start
    name = plan_name(p.plan, lang)
    if start["type"] == "p2p":
        text = t("pay.p2p.instructions", lang, plan=name, months=p.months, price=money(p.amount),
                 card=start["card"], holder=start["holder"] or "—", ref=start["reference"])
        await state.set_state(Receipt.waiting)
        await state.update_data(payment_id=p.id)
        await edit_or_send(cb, text, kb([[btn(t("pay.p2p.btn_receipt", lang), data=f"pay:rc:{p.id}",
                                               style="success")]]))
    elif start["type"] == "stars":
        await edit_or_send(cb, t("pay.stars.text", lang, plan=name, months=p.months, stars=p.amount))
        gw = stars.StarsProvider(settings)             # built directly: get_provider() is typed Optional
        texts: dict[str, Any] = {"title": t("pay.stars.invoice_title", lang, plan=name),
                                 "description": t("pay.stars.invoice_desc", lang, plan=name, months=p.months),
                                 "label": t("pay.stars.label", lang)}
        params = gw.invoice_params(p, **texts)
        params.pop("provider_token", None)
        await bot.send_invoice(chat_id=cb.from_user.id, **params)
        if p.months == 1:                                  # recurring monthly subscription link (subscription_period)
            rec = gw.invoice_params(p, recurring=True, **texts)
            rec.pop("provider_token", None)
            link = await bot.create_invoice_link(**rec)
            await bot.send_message(cb.from_user.id, decorate(t("pay.stars.recurring_text", lang, stars=p.amount)),
                                   reply_markup=kb([[btn(t("pay.stars.btn_recurring", lang), url=link)]]))
    else:                                                  # click / payme: a checkout URL
        await edit_or_send(cb, t("pay.url.text", lang, plan=name, months=p.months, price=money(p.amount)),
                           kb([[btn(t("pay.btn.pay_url", lang), url=start["url"])]]))
    await cb.answer()


# ---------------------------------------------------------------- /terms, /paysupport, /refund

class Support(StatesGroup):
    waiting = State()


@router.message(Command("terms"))
async def cmd_terms(message: Message, lang):
    await reply(message, t("pay.terms.text", lang, url=TERMS_URL))


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message, lang, state: FSMContext):
    """Mandatory for bots that sell with Stars: tell the user how to get payment help."""
    await state.set_state(Support.waiting)
    await reply(message, t("pay.support.intro", lang))


@router.message(Support.waiting, F.text, ~F.text.startswith("/"))
async def on_support_text(message: Message, session: AsyncSession, settings: Settings, user: User, lang, bot: Bot,
                          state: FSMContext):
    await state.clear()
    rows = (await session.execute(select(Payment.id, Payment.provider, Payment.status).where(Payment.user_id == user.id)
                                  .order_by(Payment.id.desc()).limit(5))).all()
    listing = ", ".join(f"#{i} {pv}/{st}" for i, pv, st in rows) or "-"
    text = t("pay.support.from_user", lang_of(None), tg_id=user.tg_id, name=user.first_name or user.username or "-",
             payments=listing, text=(message.text or "")[:3000])
    for admin_id in admin_targets(settings):
        await _send(bot, admin_id, text)
    await reply(message, t("pay.support.sent", lang))


@router.message(Support.waiting, ~F.text.startswith("/"))
async def on_support_not_text(message: Message, lang):
    await reply(message, t("pay.support.need_text", lang))


SUPPORT_TAG = re.compile(r"\[support:(\d+)\]")


@router.message(F.reply_to_message, F.text)
async def on_admin_support_reply(message: Message, user: User, lang, bot: Bot, state: FSMContext):
    """An admin replies to a forwarded support message; the user's id is read from its [support:<id>] tag."""
    origin = message.reply_to_message
    m = SUPPORT_TAG.search((origin.text or "") if origin else "")
    if not m or not user.is_admin:
        raise SkipHandler
    target = int(m.group(1))
    owner_lang = lang_of(None)
    if await _send(bot, target, t("pay.support.reply", owner_lang, text=message.text)):
        await reply(message, t("pay.support.reply_sent", lang))


@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject, session: AsyncSession, user: User, lang, bot: Bot):
    """Admin-only: refund a paid Stars payment (refundStarPayment) and shorten the subscription."""
    if not user.is_admin:
        return await reply(message, t("pay.admin.only", lang))
    arg = (command.args or "").strip()
    if not arg.isdigit():
        return await reply(message, t("pay.refund.usage", lang))
    p = await session.get(Payment, int(arg))
    if p is None:
        return await reply(message, t("pay.refund.refused", lang))

    async def call(user_id: int, charge_id: str):
        return await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)
    try:
        p, changed = await stars.refund(session, user, p, call)
    except DomainError:
        return await reply(message, t("pay.refund.refused", lang))
    except Exception:
        log.exception("refundStarPayment failed for payment %s", p.id)
        return await reply(message, t("pay.refund.failed", lang))
    if not changed:
        return await reply(message, t("pay.refund.already", lang, id=p.id))
    await reply(message, t("pay.refund.done", lang, id=p.id))
    owner = await session.get(User, p.user_id)
    if owner is not None:
        await _send(bot, owner.tg_id, t("pay.refund.user_notice", lang_of(owner.lang)))


# ---------------------------------------------------------------- P2P receipt + admin review

@router.callback_query(F.data.startswith("pay:rc:"))
async def cb_receipt(cb: CallbackQuery, session, user, lang, state: FSMContext):
    pid_s = cb_data(cb).split(":")[2]
    pid = int(pid_s) if pid_s.isdigit() else 0
    p = await session.get(Payment, pid) if pid else None
    if p is None or p.user_id != user.id or p.provider != "p2p":
        return await cb.answer(t("common.error", lang), show_alert=True)
    if p.status == "awaiting_review":
        return await cb.answer(t("pay.p2p.already_submitted", lang), show_alert=True)
    if p.status != "pending":
        return await cb.answer(t("pay.p2p.closed", lang), show_alert=True)
    if cb.message is None:                                 # inline-mode callback: nowhere to reply
        return await cb.answer()
    await state.set_state(Receipt.waiting)
    await state.update_data(payment_id=p.id)
    await cb.message.answer(decorate(t("pay.p2p.send_receipt", lang)))
    await cb.answer()


@router.message(Receipt.waiting, F.photo | (F.document & F.document.mime_type.startswith("image/")))
async def on_receipt(message: Message, session: AsyncSession, settings: Settings, user: User, lang, bot: Bot,
                     state: FSMContext):
    pid = (await state.get_data()).get("payment_id")
    p = await session.get(Payment, pid) if pid else None
    if p is None:
        await state.clear()
        return await reply(message, t("common.error", lang))
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    else:                                                  # the router filter guarantees one of the two
        return await reply(message, t("pay.p2p.need_photo", lang))
    try:
        await p2p.attach_receipt(session, user, p, file_id)
    except DomainError as e:
        await state.clear()
        key = "pay.p2p.already_submitted" if e.code == "already_submitted" else "pay.p2p.closed"
        return await reply(message, t(key, lang))
    await state.clear()
    await reply(message, t("pay.p2p.received", lang))
    for admin_id in admin_targets(settings):
        try:
            tl = lang_of(None)
            caption = t("pay.admin.review", tl, id=p.id, name=user.first_name or user.username or "—",
                        tg_id=user.tg_id, plan=plan_name(p.plan, tl), months=p.months, price=money(p.amount),
                        ref=p2p.reference(p))
            markup = kb([[btn(t("pay.admin.btn_approve", tl), data=f"pay:ok:{p.id}", style="success"),
                          btn(t("pay.admin.btn_reject", tl), data=f"pay:no:{p.id}", style="danger")]])
            if message.photo:
                await bot.send_photo(admin_id, file_id, caption=decorate(caption), reply_markup=markup)
            else:
                await bot.send_document(admin_id, file_id, caption=decorate(caption), reply_markup=markup)
        except Exception:
            log.exception("could not forward receipt of payment %s to admin %s", p.id, admin_id)


@router.message(Receipt.waiting, ~F.text.startswith("/"))
async def on_receipt_not_photo(message: Message, lang):
    await reply(message, t("pay.p2p.need_photo", lang))


async def _finish_review(cb: CallbackQuery, label: str) -> None:
    msg = cb_message(cb)
    if msg is None:
        return
    try:
        if msg.caption is not None:
            await msg.edit_caption(caption=msg.caption + "\n\n" + label, reply_markup=None)
        else:
            await msg.edit_text((msg.text or "") + "\n\n" + label, reply_markup=None)
    except Exception:
        log.debug("could not edit review message", exc_info=True)


@router.callback_query(F.data.startswith("pay:ok:") | F.data.startswith("pay:no:"))
async def cb_review(cb: CallbackQuery, session: AsyncSession, settings: Settings, bus, user: User, lang, bot: Bot):
    if not user.is_admin:                                  # admins only — checked before anything is loaded
        return await cb.answer(t("pay.admin.only", lang), show_alert=True)
    _, action, pid_s = cb_data(cb).split(":")
    p = await session.get(Payment, int(pid_s)) if pid_s.isdigit() else None
    if p is None:
        return await cb.answer(t("common.error", lang), show_alert=True)
    try:
        if action == "ok":
            p, changed = await p2p.approve(session, user, p, bus=bus)
        else:
            p, changed = await p2p.reject(session, user, p)
    except DomainError as e:
        key = "pay.admin.already" if e.code in ("already_paid",) else "pay.admin.not_reviewable"
        return await cb.answer(t(key, lang), show_alert=True)
    if not changed:
        return await cb.answer(t("pay.admin.already", lang), show_alert=True)
    owner = await session.get(User, p.user_id)
    if action == "ok":
        await _finish_review(cb, t("pay.admin.approved", lang))
        await notify_paid(bot, session, p, settings)
    else:
        await _finish_review(cb, t("pay.admin.rejected", lang))
        if owner is not None:
            await _send(bot, owner.tg_id, t("pay.p2p.rejected", lang_of(owner.lang)))
    await cb.answer()


# ---------------------------------------------------------------- Telegram Stars

@router.pre_checkout_query()
async def on_pre_checkout(q: PreCheckoutQuery, session: AsyncSession, user: User, lang):
    reason = await stars.validate_pre_checkout(session, user, q.invoice_payload, q.currency, q.total_amount)
    if reason is None:
        return await q.answer(ok=True)
    log.warning("pre_checkout refused: %s (payload=%s amount=%s)", reason, q.invoice_payload, q.total_amount)
    await q.answer(ok=False, error_message=t("pay.stars.rejected", lang))


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: AsyncSession, settings: Settings, bus, user: User, lang,
                                bot: Bot):
    sp = message.successful_payment
    if sp is None:                                         # the F.successful_payment filter guarantees it
        return
    try:
        p, new = await stars.process_successful_payment(
            session, user, invoice_payload=sp.invoice_payload, currency=sp.currency, total_amount=sp.total_amount,
            charge_id=sp.telegram_payment_charge_id, is_recurring=bool(sp.is_recurring),
            is_first_recurring=bool(sp.is_first_recurring), expires_at=sp.subscription_expiration_date, bus=bus)
    except DomainError as e:                               # Telegram already took the Stars: tell a human
        log.error("successful_payment rejected (%s): charge=%s payload=%s amount=%s", e.code,
                  sp.telegram_payment_charge_id, sp.invoice_payload, sp.total_amount)
        await reply(message, t("pay.stars.rejected", lang))
        for admin_id in admin_targets(settings):
            await _send(bot, admin_id, f"Stars payment needs a manual check: {e.code}, "
                                       f"charge {sp.telegram_payment_charge_id}, payload {sp.invoice_payload}, "
                                       f"{sp.total_amount} {sp.currency}, user {user.tg_id}")
        return
    if new:
        await notify_paid(bot, session, p, settings)


@router.subscription()
async def on_subscription_updated(update: BotSubscriptionUpdated, bot: Bot, **data):
    """Bot API 10.2: the user cancelled / re-enabled / failed to renew a Stars subscription.
    The bot's outer middleware may not cover this observer, so fall back to the sessionmaker from setup_jobs."""
    session = data.get("session")
    if session is not None:
        return await _on_subscription(session, bot, update)
    maker = STATE.get("maker")
    if maker is None:
        return None
    async with session_scope(maker) as s:
        return await _on_subscription(s, bot, update)


async def _on_subscription(session: AsyncSession, bot: Bot, update: BotSubscriptionUpdated):
    p = await stars.record_subscription_state(session, update.invoice_payload, update.state)
    if p is None:
        return
    owner = await session.get(User, p.user_id)
    if owner is not None and owner.tg_id == update.user.id:
        key = {"canceled": "pay.stars.sub_canceled", "active": "pay.stars.sub_active",
               "failed": "pay.stars.sub_failed"}[update.state]
        await _send(bot, owner.tg_id, t(key, lang_of(owner.lang)))


# ---------------------------------------------------------------- notifications and jobs

STATE: dict = {}
PENDING: set = set()                                       # background notify tasks (kept referenced)


async def _send(bot: Bot, chat_id: int, text: str, markup=None) -> bool:
    try:
        await bot.send_message(chat_id, decorate(text), reply_markup=markup)
        return True
    except Exception:
        log.warning("could not message %s", chat_id, exc_info=True)
        return False


async def notify_paid(bot: Bot, session: AsyncSession, payment: Payment, settings: Settings) -> bool:
    """Tell the driver the payment succeeded — once (flag in payment.payload, so event + direct paths don't repeat)."""
    if (payment.payload or {}).get("notified"):
        return False
    owner = await session.get(User, payment.user_id)
    driver = await get_driver(session, owner) if owner else None
    if owner is None or driver is None:
        return False
    payment.payload = {**(payment.payload or {}), "notified": True}
    lg = lang_of(owner.lang)
    return await _send(bot, owner.tg_id, t("pay.success", lg, plan=plan_name(payment.plan, lg),
                                           date=fmt_date(driver.subscription_until)))

