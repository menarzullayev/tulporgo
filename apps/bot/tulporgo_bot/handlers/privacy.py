"""/malumotlarim — privacy policy §8: download own data as a JSON file, or delete it after a confirmation.

Order on delete: refuse during an active trip → log the userbot session out on Telegram's side (W2) → anonymise
(core `services.privacy`). Checking first means a refused deletion never leaves the userbot half-disconnected.
"""
import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tulporgo_core.config import Settings
from tulporgo_core.models import Driver, User, UserbotAccount
from tulporgo_core.services import privacy

from .common import PRIVATE, btn, kb, show

log = logging.getLogger(__name__)
router = Router(name="privacy")
router.message.filter(F.chat.type == PRIVATE)


@router.message(Command("malumotlarim"))
async def menu(msg: Message, state: FSMContext, t) -> None:
    await state.clear()
    await show(msg, t("bot.privacy.menu"), kb([btn(t("bot.privacy.btn_export"), "pv:x")],
                                              [btn(t("bot.privacy.btn_delete"), "pv:d", style="danger")]))


@router.callback_query(F.data == "pv:x")
async def export(cq: CallbackQuery, session: AsyncSession, user: User, t) -> None:
    data = await privacy.export_user_data(session, user)
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    await cq.message.answer_document(BufferedInputFile(payload, filename="tulporgo-data.json"),
                                     caption=t("bot.privacy.export_caption"))
    await cq.answer()


@router.callback_query(F.data == "pv:d")
async def ask_delete(cq: CallbackQuery, t) -> None:
    await show(cq, t("bot.privacy.delete_confirm"), kb([btn(t("bot.privacy.btn_delete_yes"), "pv:dy", style="danger")],
                                                        [btn(t("bot.privacy.btn_keep"), "pv:no")]))
    await cq.answer()


@router.callback_query(F.data == "pv:no")
async def keep(cq: CallbackQuery, t) -> None:
    await show(cq, t("bot.privacy.kept"))
    await cq.answer()


@router.callback_query(F.data == "pv:dy")
async def delete(cq: CallbackQuery, session: AsyncSession, settings: Settings, bus, user: User, t) -> None:
    await privacy.ensure_deletable(session, user)              # DomainError → the error middleware answers
    await _logout_userbot(session, settings, user)
    await privacy.delete_user_data(session, user, bus=bus)
    await show(cq, t("bot.privacy.deleted"))
    await cq.answer()


async def _logout_userbot(session: AsyncSession, settings: Settings, user: User) -> None:
    """End a connected userbot session on Telegram's side (W2's "Hisobni uzish"); best effort, local data goes anyway."""
    try:
        from tulporgo_userbot import runtime, service
    except ModuleNotFoundError:                                 # userbot workstream not installed
        return
    acc = (await session.execute(
        select(UserbotAccount).join(Driver, Driver.id == UserbotAccount.driver_id)
        .where(Driver.user_id == user.id).options(selectinload(UserbotAccount.groups)))).scalar_one_or_none()
    if acc is None or not acc.session_encrypted:
        return
    try:
        factory = runtime.get_factory()
    except Exception:                                           # noqa: BLE001 — no API credentials configured
        factory = None
    await runtime.cancel_login(acc.driver_id)
    await service.disconnect_account(session, acc, settings, factory)
