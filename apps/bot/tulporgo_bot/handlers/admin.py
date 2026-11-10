"""In-Telegram admin panel for the family team (decision 19): pending driver documents → "Tasdiqlangan", open
complaints, block / unblock (blacklist), KPI now. Every entry point re-checks `is_admin` — a forged callback from a
normal user does nothing."""
from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.methods import SendPhoto
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.enums import ComplaintStatus
from tulporgo_core.errors import Forbidden, NotFound
from tulporgo_core.models import Complaint, Driver, User
from tulporgo_core.services import drivers, feedback, kpi, users
from tulporgo_core.text.alphabet import convert

from .. import delivery
from . import states
from .common import PRIVATE, btn, esc, int_arg, is_admin, kb, parse_cb, person, show, user_t
from .recipients import admin_targets

router = Router(name="admin")
router.message.filter(F.chat.type == PRIVATE)


def need_admin(user: User, settings: Settings) -> None:
    if not is_admin(user, settings):
        raise Forbidden("admin_only")


def pending_docs_query():
    return select(Driver).where(Driver.license_file_id.is_not(None), Driver.techpass_file_id.is_not(None),
                                Driver.verified.is_(False)).order_by(Driver.id)


async def panel(event, session: AsyncSession, t) -> None:
    docs = await session.scalar(select(func.count()).select_from(pending_docs_query().subquery())) or 0
    cps = await session.scalar(select(func.count(Complaint.id)).where(Complaint.status == ComplaintStatus.OPEN)) or 0
    await show(event, f"<b>{t('bot.admin.panel')}</b>", kb(
        [btn(f"📄 {t('bot.admin.docs')} ({docs})", "ad:docs")],
        [btn(f"📝 {t('bot.admin.complaints')} ({cps})", "ad:cp")],
        [btn(f"🚫 {t('bot.admin.block')}", "ad:bl")],
        [btn(f"📊 {t('bot.admin.kpi')}", "ad:kpi")]))


@router.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    await state.clear()
    await panel(msg, session, t)


@router.callback_query(F.data == "ad:menu")
async def menu(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    await cb.answer()
    await panel(cb, session, t)


# ---------- documents ----------

async def notify_new_documents(bot: Bot, session: AsyncSession, settings: Settings, d: Driver) -> None:
    for chat_id, ta in await admin_targets(session, settings):
        await delivery.send(bot, chat_id, f"📄 {ta('bot.admin.new_docs', who=person(d.user), car=esc(d.car_plate))}",
                            kb([btn(f"📄 {ta('bot.admin.docs')}", "ad:docs")]))


@router.callback_query(F.data == "ad:docs")
async def docs_list(cb: CallbackQuery, bot: Bot, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    await cb.answer()
    rows = list((await session.execute(pending_docs_query().limit(5))).scalars())
    if not rows:
        await show(cb, t("bot.admin.none"), kb([btn(f"↩ {t('common.back')}", "ad:menu")]))
        return
    for d in rows:
        await delivery.call(bot, SendPhoto(chat_id=cb.from_user.id, photo=d.license_file_id))
        caption = f"{person(d.user)} · {esc(d.car_make)} {esc(d.car_plate)}\n{esc(d.user.phone or '')}"
        await delivery.call(bot, SendPhoto(chat_id=cb.from_user.id, photo=d.techpass_file_id, caption=caption,
                                           parse_mode="HTML", reply_markup=kb(
            [btn(f"✅ {t('bot.admin.approve')}", f"ad:dv:{d.id}", style="success"),
             btn(f"✖ {t('bot.admin.reject')}", f"ad:dr:{d.id}", style="danger")])))


async def _driver(session: AsyncSession, cb: CallbackQuery) -> Driver | None:
    parts = parse_cb(cb.data, 3)
    did = int_arg(parts[2]) if parts else None
    d = await session.get(Driver, did) if did else None
    if d is None:
        raise NotFound("driver_not_found")
    return d


async def _drop_buttons(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("ad:dv:"))
async def approve(cb: CallbackQuery, bot: Bot, session: AsyncSession, user: User, settings: Settings, bus, t) -> None:
    need_admin(user, settings)
    d = await drivers.verify(session, user, await _driver(session, cb), settings, bus)   # events notify the driver
    await cb.answer(t("bot.admin.approved", who=d.car_plate))
    await _drop_buttons(cb)


@router.callback_query(F.data.startswith("ad:dr:"))
async def reject(cb: CallbackQuery, bot: Bot, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    d = await _driver(session, cb)
    if d.verified:
        raise Forbidden("already_verified")
    d.license_file_id = d.techpass_file_id = None        # the driver can send clearer photos
    await cb.answer(t("bot.admin.rejected"))
    await _drop_buttons(cb)
    await delivery.send(bot, d.user.tg_id, f"✖ {user_t(d.user)('bot.docs.rejected')}",
                        kb([btn(f"📄 {user_t(d.user)('bot.btn.docs')}", "drv:doc")]))


# ---------- complaints ----------

@router.callback_query(F.data == "ad:cp")
async def complaints(cb: CallbackQuery, bot: Bot, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    await cb.answer()
    rows = list((await session.execute(select(Complaint).where(Complaint.status == ComplaintStatus.OPEN)
                                       .order_by(Complaint.id).limit(5))).scalars())
    if not rows:
        await show(cb, t("bot.admin.none"), kb([btn(f"↩ {t('common.back')}", "ad:menu")]))
        return
    for c in rows:
        author = await session.get(User, c.from_user_id)
        against = await session.get(User, c.against_user_id) if c.against_user_id else None
        text = f"📝 #{c.id} · {person(author)}" + (f" → {person(against)}" if against else "") + f"\n\n{esc(c.text[:800])}"
        row2 = [btn(f"🚫 {t('bot.admin.block')}", f"ad:bu:{against.id}", style="danger")] if against else []
        await delivery.send(bot, cb.from_user.id, text, kb(
            [btn(f"✅ {t('bot.admin.accepted')}", f"ad:cr:{c.id}:1", style="success"),
             btn(f"✖ {t('bot.admin.rejected_c')}", f"ad:cr:{c.id}:0")], row2))


@router.callback_query(F.data.startswith("ad:cr:"))
async def resolve(cb: CallbackQuery, bot: Bot, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    parts = parse_cb(cb.data, 4)
    cid, flag = (int_arg(parts[2]), parts[3]) if parts else (None, "")
    c = await session.get(Complaint, cid) if cid else None
    if c is None or flag not in ("0", "1"):
        raise NotFound("complaint_not_found")
    accepted = flag == "1"
    await feedback.resolve(session, user, c, accepted, t("bot.admin.resolution_ok" if accepted else "bot.admin.resolution_no"))
    await cb.answer(t("bot.admin.done"))
    await _drop_buttons(cb)
    author = await session.get(User, c.from_user_id)
    ta = user_t(author)
    await delivery.send(bot, author.tg_id, f"📝 {ta('bot.complaint.resolved', id=c.id)}\n{esc(c.resolution or '')}")


# ---------- blacklist ----------

@router.callback_query(F.data == "ad:bl")
async def block_prompt(cb: CallbackQuery, state: FSMContext, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    await cb.answer()
    await state.set_state(states.Admin.block)
    await show(cb, t("bot.admin.block_ask"))


@router.message(StateFilter(states.Admin.block), F.text, ~F.text.startswith("/"))
async def block_find(msg: Message, state: FSMContext, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    q = (msg.text or "").strip()
    if q.lstrip("@").isdigit() and not q.startswith("@"):
        found = (await session.execute(select(User).where(User.tg_id == int(q)))).scalar_one_or_none()
    else:
        found = (await session.execute(select(User).where(func.lower(User.username) == q.lstrip("@").lower()))).scalar_one_or_none()
    if found is None:
        await show(msg, t("bot.admin.user_none"))
        return
    await state.clear()
    status = t("bot.admin.is_blocked") if found.is_blocked else t("bot.admin.is_active")
    action = (btn(f"♻ {t('bot.admin.unblock')}", f"ad:ub:{found.id}", style="success") if found.is_blocked
              else btn(f"🚫 {t('bot.admin.block')}", f"ad:bu:{found.id}", style="danger"))
    await show(msg, f"{person(found)} (@{esc(found.username or '—')}, id {found.tg_id}) — {status}", kb([action]))


async def _set_blocked(cb: CallbackQuery, session: AsyncSession, admin: User, settings: Settings, blocked: bool, t) -> None:
    need_admin(admin, settings)
    parts = parse_cb(cb.data, 3)
    uid = int_arg(parts[2]) if parts else None
    target = await session.get(User, uid) if uid else None
    if target is None:
        raise NotFound("user_not_found")
    await users.set_blocked(session, admin, target, blocked)
    await cb.answer(t("bot.admin.blocked_done" if blocked else "bot.admin.unblocked_done", who=person(target)))
    await _drop_buttons(cb)


@router.callback_query(F.data.startswith("ad:bu:"))
async def do_block(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, t) -> None:
    await _set_blocked(cb, session, user, settings, True, t)


@router.callback_query(F.data.startswith("ad:ub:"))
async def do_unblock(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, t) -> None:
    await _set_blocked(cb, session, user, settings, False, t)


# ---------- KPI ----------

@router.callback_query(F.data == "ad:kpi")
async def kpi_now(cb: CallbackQuery, session: AsyncSession, user: User, settings: Settings, t) -> None:
    need_admin(user, settings)
    await cb.answer()
    text = convert(kpi.report(await kpi.compute(session)), "uz_new")
    await show(cb, esc(text), kb([btn(f"↩ {t('common.back')}", "ad:menu")]))
