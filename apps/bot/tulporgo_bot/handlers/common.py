"""Helpers shared by all handlers: HTML escaping, time/price formatting, keyboards, error texts, `show`."""
import html as _html
import logging
from datetime import UTC, datetime, timedelta, timezone
from functools import partial

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from tulporgo_core import emoji, i18n
from tulporgo_core.config import Settings
from tulporgo_core.enums import Lang
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.models import Driver, User

log = logging.getLogger(__name__)
UZT = timezone(timedelta(hours=5))               # Asia/Tashkent, no DST
PRIVATE = "private"


async def get_required[T](s: AsyncSession, model: type[T], pk: int) -> T:
    """Load a row that a NOT NULL foreign key points at. A miss means corrupt data, so fail loudly (LookupError)
    instead of passing None on to code that would crash later with an opaque AttributeError."""
    obj = await s.get(model, pk)
    if obj is None:
        raise LookupError(f"{model.__name__} #{pk} referenced by a foreign key does not exist")
    return obj


def bind(lang):
    """i18n function bound to someone else's language (notifications go to people who are not chatting right now)."""
    return partial(i18n.t, lang=lang)


def user_t(user: User):
    return bind(i18n.lang_of(user.lang))


def esc(value) -> str:
    return _html.escape("" if value is None else str(value), quote=False)


def money(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def price(n: int, t) -> str:
    return t("common.price", price=money(n))


def to_local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC).astimezone(UZT)


def unix(dt: datetime) -> int:
    return int(dt.replace(tzinfo=UTC).timestamp())


def time_plain(dt: datetime | None, t) -> str:
    return t("bot.when_now") if dt is None else to_local(dt).strftime("%d.%m %H:%M")


def time_html(dt: datetime | None, t) -> str:
    """Departure time as a `date_time` entity (Bot API 9.5): every user sees it in their own zone and can add a
    reminder. Clients that do not know the tag show the tag's text, so the plain text is the fallback."""
    if dt is None:
        return t("bot.when_now")
    return f'<tg-time unix="{unix(dt)}" format="dt">{time_plain(dt, t)}</tg-time>'


def local_to_utc(local: datetime) -> datetime:
    return local.astimezone(UTC).replace(tzinfo=None)


def rating_text(d: Driver, t) -> str:
    return f"⭐ {d.rating:.1f} ({d.rating_count})" if d.rating is not None else t("bot.rating_new")


def person(u: User) -> str:
    return esc(u.first_name or (f"@{u.username}" if u.username else f"#{u.id}"))


def contact_html(u: User) -> str:
    """Name, phone and @username — shown only to the other side of a confirmed trip."""
    parts = [person(u)]
    if u.phone:
        parts.append(esc(u.phone))
    if u.username:
        parts.append(f"@{esc(u.username)}")
    return " · ".join(parts)


def is_admin(user: User, settings: Settings) -> bool:
    return bool(user.is_admin or user.tg_id in settings.admin_ids)


def err_text(code: str, t) -> str:
    key = f"bot.err.{code}"
    return t(key) if key in i18n.catalog() else t("common.error")


# ---------- keyboards ----------

def btn(text: str, data: str | None = None, *, url: str | None = None, web_app: str | None = None,
        style: str | None = None) -> InlineKeyboardButton:
    """`style` = primary | success | danger (Bot API 9.4); clients that do not know it show a plain button."""
    return InlineKeyboardButton(text=text, callback_data=data, url=url, style=style,
                                web_app=WebAppInfo(url=web_app) if web_app else None)


def kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows if r])


def deep_link(settings: Settings, payload: str) -> str:
    return f"https://t.me/{settings.bot_username}?start={payload}"


def referral_link(settings: Settings, user: User) -> str:
    return deep_link(settings, f"ref_{user.referral_code}")


def lang_name(lang) -> str:
    return {Lang.UZ_NEW: "Özbekça", Lang.UZ_LATN: "Oʻzbekcha", Lang.UZ_CYRL: "Ўзбекча", Lang.RU: "Русский",
            Lang.EN: "English"}[Lang(lang)]


# ---------- sending to the person in the current chat ----------

async def show(event: CallbackQuery | Message, text: str, markup: InlineKeyboardMarkup | None = None):
    """Callback → edit the card in place (new message if it cannot be edited); message → reply."""
    text = emoji.decorate(text)
    if isinstance(event, CallbackQuery):
        if isinstance(event.message, Message):
            try:
                return await event.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
            except TelegramBadRequest as e:
                log.debug("edit failed (%s) — sending a new message", e)
            return await event.message.answer(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return None
    return await event.answer(text, reply_markup=markup, parse_mode=ParseMode.HTML)


async def say(event: CallbackQuery | Message, text: str, markup=None):
    """Always a NEW message (needed for reply keyboards, which cannot be attached by editing)."""
    msg = event.message if isinstance(event, CallbackQuery) else event
    if not isinstance(msg, Message):
        return None
    return await msg.answer(emoji.decorate(text), reply_markup=markup, parse_mode=ParseMode.HTML)


def parse_cb(data: str | None, n: int) -> list[str] | None:
    """'pk:f:12' → ['pk','f','12'] when it has exactly n parts; None for malformed (tampered) data."""
    parts = (data or "").split(":")
    return parts if len(parts) == n else None


def int_arg(value: str) -> int | None:
    return int(value) if value.isdigit() else None
