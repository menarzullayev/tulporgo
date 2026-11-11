"""aiogram Router for the userbot UX inside @tulporgobot: `/elon` menu — consent, connect (opens the Mini App login),
status, groups on/off, interval, post text preview/edit, pause/resume, "Hisobni uzish".

Included by the bot (`tulporgo_bot.main.OPTIONAL_ROUTERS`). Handlers receive the shared context from
`ContextMiddleware`: session, settings, bus, user, lang, t. The Telegram code and the 2FA password are NEVER asked for
here — they are typed in the Mini App form only (Telegram blocks login codes sent as messages).

Old clients: `style` on buttons is ignored by apps that do not know it; every action also works as a plain button.
"""
import html
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from tulporgo_core.emoji import decorate
from tulporgo_core.enums import UserbotStatus
from tulporgo_core.errors import DomainError
from tulporgo_core.i18n import t as i18n_t
from tulporgo_core.models import Driver, User, UserbotAccount

from . import feedbot, runtime, service, template
from .config import ABSOLUTE_MIN_INTERVAL_MINUTES
from .errors import Invalid, NotConfigured
from .sync import refresh_groups

log = logging.getLogger(__name__)
router = Router(name="userbot")
router.include_router(feedbot.router)              # decision 73: passenger search
PAGE = 8


class TemplateForm(StatesGroup):
    from_ = State()
    to = State()
    time = State()
    seats = State()
    price = State()


def _btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data, style=style)


def _kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows])


async def _show(target: Message | CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    text = decorate(text)
    if isinstance(target, CallbackQuery):
        msg = target.message
        if isinstance(msg, Message):
            try:
                await msg.edit_text(text, reply_markup=markup)
            except Exception:                                  # noqa: BLE001 - "message is not modified" / too old
                await msg.answer(text, reply_markup=markup)
        elif msg is not None:                                  # InaccessibleMessage: cannot be edited, can be answered
            await msg.answer(text, reply_markup=markup)
        elif target.bot is not None:                           # inline-mode callback: no message at all
            await target.bot.send_message(target.from_user.id, text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)


def _error_text(e: DomainError, lang) -> str:
    key = f"userbot.err.{e.code}"
    text = i18n_t(key, lang)
    return text if text != key else i18n_t("userbot.err.generic", lang)


async def _ctx(session, user: User) -> tuple[Driver, UserbotAccount | None]:
    driver = await service.require_driver(session, user)
    return driver, await service.get_account(session, driver)


def _status_line(account: UserbotAccount | None, t) -> str:
    if account is None or account.status == UserbotStatus.NEEDS_LOGIN:
        return t("userbot.status.needs_login")
    st = account.status
    if st == UserbotStatus.FLOOD_WAIT:
        until = account.flood_until.strftime("%d.%m %H:%M") if account.flood_until else "?"
        return t("userbot.status.flood_wait", until=until)
    if st == UserbotStatus.STOPPED:
        return t("userbot.status.stopped", reason=html.escape(account.stop_reason or "-"))
    return t(f"userbot.status.{st}")


def _menu_text(account: UserbotAccount | None, settings, t) -> str:
    status = _status_line(account, t)
    if account is not None and account.session_encrypted:
        cap = account.daily_max_posts if account.daily_max_posts else t("userbot.cap.none")
        status += "\n" + t("userbot.status.details", groups=len(service.enabled_groups(account)),
                           interval=service.effective_interval(account, settings),
                           jitter=service.effective_jitter(account, settings), cap=cap)
    return t("userbot.menu", status=status)


def _menu_markup(account: UserbotAccount | None, settings, t) -> InlineKeyboardMarkup:
    status = account.status if account is not None else None
    connected = account is not None and bool(account.session_encrypted) and status != UserbotStatus.NEEDS_LOGIN
    rows: list[list[InlineKeyboardButton]] = []
    if not connected or status == UserbotStatus.STOPPED:
        rows.append([InlineKeyboardButton(text=t("userbot.btn.connect"), style="primary",
                                          web_app=WebAppInfo(url=f"{settings.miniapp_url}?page=userbot"))])
    if connected and status != UserbotStatus.STOPPED:
        rows.append([_btn(t("userbot.btn.groups"), "ub:groups:0"), _btn(t("userbot.btn.interval"), "ub:int")])
        toggle = (_btn(t("userbot.btn.resume"), "ub:resume", "success") if status == UserbotStatus.PAUSED
                  else _btn(t("userbot.btn.pause"), "ub:pause"))
        rows.append([_btn(t("userbot.btn.template"), "ub:tpl"), toggle])
    if connected and status != UserbotStatus.STOPPED:
        rows.append([_btn(t("feed.btn.menu"), "fd:menu")])               # decision 73
    if connected:
        rows.append([_btn(t("userbot.btn.logout"), "ub:logout", "danger")])
    return _kb(*rows) if rows else _kb()


async def _menu(target, session, settings, user, t, note: str = "") -> None:
    driver, account = await _ctx(session, user)
    if account is None or account.consent_at is None or account.consent_version < service.CONSENT_VERSION:
        # no consent, or consent to an older text (decision 73 added group watching) -> the risk screen first
        text = t("userbot.risk", min=settings.userbot_min_interval_minutes)
        await _show(target, text, _kb([_btn(t("userbot.btn.consent"), "ub:consent", "success"),
                                       _btn(t("common.cancel"), "ub:close")]))
        return
    text = _menu_text(account, settings, t)
    await _show(target, (note + "\n\n" if note else "") + text, _menu_markup(account, settings, t))


async def _guarded(target, lang, coro) -> None:
    try:
        await coro
    except DomainError as e:
        text = _error_text(e, lang)
        if isinstance(target, CallbackQuery):
            await target.answer(text, show_alert=True)
        else:
            await target.answer(text)


# ---------------------------------------------------------------- entry points

@router.message(Command("elon"), F.chat.type == "private")
async def cmd_elon(message: Message, state: FSMContext, session, settings, user, lang, t, **_):
    await state.clear()
    await _guarded(message, lang, _menu(message, session, settings, user, t))


@router.callback_query(F.data == "ub:menu")
async def cb_menu(cq: CallbackQuery, state: FSMContext, session, settings, user, lang, t, **_):
    await state.clear()
    await _guarded(cq, lang, _menu(cq, session, settings, user, t))


@router.callback_query(F.data == "ub:close")
async def cb_close(cq: CallbackQuery, **_):
    try:
        if isinstance(cq.message, Message):                     # None / inaccessible: nothing we can delete
            await cq.message.delete()
    except Exception:                                           # noqa: BLE001
        log.debug("could not delete the risk screen")
    await cq.answer()


@router.callback_query(F.data == "ub:consent")
async def cb_consent(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        driver, _ = await _ctx(session, user)
        await service.accept_consent(session, driver, settings)
        await _menu(cq, session, settings, user, t, note=t("userbot.consent.ok"))
    await _guarded(cq, lang, go())


# ---------------------------------------------------------------- groups

def _groups_view(account: UserbotAccount, driver: Driver, settings, t, page: int):
    groups = sorted(account.groups, key=lambda g: g.id)
    limit = service.selection_limit(driver, settings)
    pages = max(1, -(-len(groups) // PAGE))
    page = min(max(page, 0), pages - 1)
    text = (t("userbot.groups.title", enabled=len(service.enabled_groups(account)),
              limit=t("userbot.limit.unlimited") if limit is None else limit)
            if groups else t("userbot.groups.empty"))
    rows = [[_btn(("✅ " if g.enabled else "⬜ ") + g.title[:40], f"ub:g:{g.id}:{page}")]
            for g in groups[page * PAGE:(page + 1) * PAGE]]
    nav = []
    if page > 0:
        nav.append(_btn("◀️", f"ub:groups:{page - 1}"))
    if page < pages - 1:
        nav.append(_btn("▶️", f"ub:groups:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_btn(t("userbot.btn.sync"), "ub:sync")])
    rows.append([_btn(t("userbot.btn.back"), "ub:menu")])
    return text, _kb(*rows)


@router.callback_query(F.data.startswith("ub:groups:"))
async def cb_groups(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        driver, account = await _ctx(session, user)
        if account is None or not account.session_encrypted:
            raise Invalid("not_connected")
        text, markup = _groups_view(account, driver, settings, t, int(cq.data.split(":")[2]))
        await _show(cq, text, markup)
    await _guarded(cq, lang, go())


@router.callback_query(F.data.startswith("ub:g:"))
async def cb_group_toggle(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        _, _, gid, page = cq.data.split(":")
        driver, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        group = next((g for g in account.groups if g.id == int(gid)), None)
        await service.set_group_enabled(session, account, driver, settings, int(gid), not (group and group.enabled))
        text, markup = _groups_view(account, driver, settings, t, int(page))
        await _show(cq, text, markup)
    await _guarded(cq, lang, go())


@router.callback_query(F.data == "ub:sync")
async def cb_sync(cq: CallbackQuery, session, settings, bus, user, lang, t, **_):
    async def go():
        driver, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        try:
            groups = await refresh_groups(session, account, settings, runtime.get_factory(), bus)
        except NotConfigured as e:
            log.error("userbot is not configured: %s", e.code)
            raise Invalid("generic") from e
        text, markup = _groups_view(account, driver, settings, t, 0)
        await _show(cq, t("userbot.groups.synced", n=len(groups)) + "\n\n" + text, markup)
    await _guarded(cq, lang, go())


# ---------------------------------------------------------------- interval (decision 48)

@router.callback_query(F.data == "ub:int")
async def cb_interval(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        _, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        safe_min = settings.userbot_min_interval_minutes
        safe = sorted({safe_min, 60, 90, 120} - {m for m in (60, 90, 120) if m < safe_min})
        risky = [m for m in (30, 20, 10) if ABSOLUTE_MIN_INTERVAL_MINUTES <= m < safe_min]
        rows = [[_btn(f"{m} min", f"ub:i:{m}") for m in safe]]
        if risky:
            rows.append([_btn(f"⚠️ {m} min", f"ub:ir:{m}", "danger") for m in risky])
        rows.append([_btn(t("userbot.btn.back"), "ub:menu")])
        await _show(cq, t("userbot.interval.title", interval=service.effective_interval(account, settings),
                          min=safe_min), _kb(*rows))
    await _guarded(cq, lang, go())


@router.callback_query(F.data.startswith("ub:i:"))
async def cb_interval_safe(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        minutes = int(cq.data.split(":")[2])
        _, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        # a hand-made callback below the safe default is refused here without the acknowledgement
        await service.update_limits(session, account, settings, interval_minutes=minutes)
        await _menu(cq, session, settings, user, t, note=t("userbot.interval.set", minutes=minutes))
    await _guarded(cq, lang, go())


@router.callback_query(F.data.startswith("ub:ir:"))
async def cb_interval_warn(cq: CallbackQuery, lang, settings, t, **_):
    minutes = int((cq.data or "").split(":")[2])
    await _show(cq, t("userbot.interval.warn", minutes=minutes, min=settings.userbot_min_interval_minutes),
                _kb([_btn(t("userbot.btn.ack"), f"ub:ia:{minutes}", "danger")], [_btn(t("userbot.btn.back"), "ub:int")]))


@router.callback_query(F.data.startswith("ub:ia:"))
async def cb_interval_ack(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        minutes = int(cq.data.split(":")[2])
        _, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        await service.update_limits(session, account, settings, interval_minutes=minutes, acknowledge_risk=True)
        await _menu(cq, session, settings, user, t, note=t("userbot.interval.set", minutes=minutes))
    await _guarded(cq, lang, go())


# ---------------------------------------------------------------- post template

@router.callback_query(F.data == "ub:tpl")
async def cb_template(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        _, account = await _ctx(session, user)
        tpl = template.loads(account.post_template) if account else None
        text = (t("userbot.template.preview", text=html.escape(template.build_post_text(tpl, lang, settings)))
                if tpl else t("userbot.template.none"))
        await _show(cq, text, _kb([_btn(t("userbot.btn.edit_template"), "ub:tpl_edit")],
                                  [_btn(t("userbot.btn.back"), "ub:menu")]))
    await _guarded(cq, lang, go())


@router.callback_query(F.data == "ub:tpl_edit")
async def cb_template_edit(cq: CallbackQuery, state: FSMContext, session, user, lang, t, **_):
    async def go():
        _, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        await state.set_state(TemplateForm.from_)
        await _show(cq, t("userbot.template.ask_from"))
    await _guarded(cq, lang, go())


async def _step(message: Message, state: FSMContext, t, field: str, value: str, parse, next_state, ask_key: str):
    try:
        parsed = parse(value)
    except Invalid:
        await message.answer(t("userbot.template.bad"))
        return False
    await state.update_data(**{field: parsed})
    await state.set_state(next_state)
    await message.answer(t(ask_key))
    return True


@router.message(TemplateForm.from_, F.text)
async def tpl_from(message: Message, state: FSMContext, t, **_):
    await _step(message, state, t, "from_", message.text or "", lambda v: template.clean_text("from", v), TemplateForm.to,
                "userbot.template.ask_to")


@router.message(TemplateForm.to, F.text)
async def tpl_to(message: Message, state: FSMContext, t, **_):
    await _step(message, state, t, "to", message.text or "", lambda v: template.clean_text("to", v), TemplateForm.time,
                "userbot.template.ask_time")


@router.message(TemplateForm.time, F.text)
async def tpl_time(message: Message, state: FSMContext, t, **_):
    await _step(message, state, t, "time", message.text or "", lambda v: template.clean_text("time", v), TemplateForm.seats,
                "userbot.template.ask_seats")


@router.message(TemplateForm.seats, F.text)
async def tpl_seats(message: Message, state: FSMContext, t, **_):
    await _step(message, state, t, "seats", message.text or "", template.parse_seats, TemplateForm.price,
                "userbot.template.ask_price")


@router.message(TemplateForm.price, F.text)
async def tpl_price(message: Message, state: FSMContext, session, settings, user, lang, t, **_):
    try:
        price = template.parse_price(message.text)
    except Invalid:
        await message.answer(t("userbot.template.bad"))
        return
    data = await state.get_data()
    await state.clear()

    async def go():
        _, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        tpl = template.make_template(data["from_"], data["to"], data["time"], data["seats"], price)
        account.post_template = template.dumps(tpl)
        await session.flush()
        await message.answer(t("userbot.template.saved") + "\n\n"
                             + t("userbot.template.preview", text=html.escape(template.build_post_text(tpl, lang, settings))))
    await _guarded(message, lang, go())


# ---------------------------------------------------------------- pause / resume / logout

@router.callback_query(F.data == "ub:pause")
async def cb_pause(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        _, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        await service.pause(session, account)
        await _menu(cq, session, settings, user, t, note=t("userbot.paused"))
    await _guarded(cq, lang, go())


@router.callback_query(F.data == "ub:resume")
async def cb_resume(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        driver, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        service.require_plan(driver, settings)
        await service.resume(session, account)
        await _menu(cq, session, settings, user, t, note=t("userbot.resumed"))
    await _guarded(cq, lang, go())


@router.callback_query(F.data == "ub:logout")
async def cb_logout_ask(cq: CallbackQuery, t, **_):
    await _show(cq, t("userbot.logout.ask"), _kb([_btn(t("userbot.btn.confirm_logout"), "ub:logout_yes", "danger"),
                                                  _btn(t("common.cancel"), "ub:menu")]))


@router.callback_query(F.data == "ub:logout_yes")
async def cb_logout(cq: CallbackQuery, session, settings, user, lang, t, **_):
    async def go():
        _, account = await _ctx(session, user)
        if account is None:
            raise Invalid("not_connected")
        factory = None
        if account.session_encrypted:
            try:
                factory = runtime.get_factory()
            except NotConfigured:                               # no API credentials: still delete the local session
                factory = None
        await runtime.cancel_login(account.driver_id)
        await service.disconnect_account(session, account, settings, factory)
        await _show(cq, t("userbot.logout.done"))
    await _guarded(cq, lang, go())
