"""HTML Widgets (Bot API 10.4): a small trip-status card in PRIVATE chats. aiogram 3.31 does not know `sendWidget`,
so the method is declared here. Telegram's limits are enforced BEFORE the call (`check_widget`), and a widget that
fails for any reason never costs the user their normal trip card (see `notify.send_trip_card`)."""
import json
import logging
import zlib
from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from aiogram.methods.base import TelegramMethod
from aiogram.types import InlineKeyboardMarkup, Message
from tulporgo_core.models import Driver, RideRequest, Trip

from . import delivery
from .handlers.common import esc, price, time_plain

log = logging.getLogger(__name__)

MAX_HTML_BYTES = 32768           # raw HTML
MAX_COMPRESSED_BYTES = 4096      # zlib level 9
MAX_DATA_BYTES = 1024            # public_data / chat_data
MAX_CAPTION = 1024
MIN_WIDTH = 200
MIN_HEIGHT, MAX_HEIGHT = 50, 600
YELLOW, INK, WHITE = "#FFC72C", "#111214", "#FFFFFF"      # brand colours (BRAND.md)


class WidgetError(ValueError):
    """The widget breaks a Telegram limit (or is aimed at a chat where widgets are not allowed): never sent."""


class SendWidget(TelegramMethod[Message]):
    """sendWidget (Bot API 10.4). Private chats only in production; widgets cannot be forwarded or copied."""

    __returning__ = Message
    __api_method__ = "sendWidget"

    chat_id: int | str
    message_thread_id: int | None = None
    html: str
    width: int | None = None
    height: int | None = None
    public_data: str | None = None
    chat_data: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    show_caption_above_media: bool | None = None
    allow_queries: bool | None = None
    is_shared: bool | None = None
    disable_notification: bool | None = None
    protect_content: bool | None = None
    reply_parameters: Any | None = None
    reply_markup: InlineKeyboardMarkup | None = None


def compressed_size(html: str) -> int:
    return len(zlib.compress(html.encode(), 9))


def check_widget(method: SendWidget) -> None:
    """Raise `WidgetError` for anything Telegram would refuse — before any network call."""
    if isinstance(method.chat_id, str) or method.chat_id <= 0:
        raise WidgetError("widgets are for private chats only")
    size = len(method.html.encode())
    if not 1 <= size <= MAX_HTML_BYTES:
        raise WidgetError(f"html is {size} bytes (1..{MAX_HTML_BYTES})")
    packed = compressed_size(method.html)
    if packed > MAX_COMPRESSED_BYTES:
        raise WidgetError(f"html is {packed} bytes after zlib level 9 (max {MAX_COMPRESSED_BYTES})")
    for name in ("public_data", "chat_data"):
        value = getattr(method, name)
        if value is not None and len(value.encode()) > MAX_DATA_BYTES:
            raise WidgetError(f"{name} is over {MAX_DATA_BYTES} bytes")
    if method.caption is not None and len(method.caption) > MAX_CAPTION:
        raise WidgetError(f"caption is over {MAX_CAPTION} characters")
    if method.width is not None and method.width < MIN_WIDTH:
        raise WidgetError(f"width must be at least {MIN_WIDTH}")
    if method.height is not None and not MIN_HEIGHT <= method.height <= MAX_HEIGHT:
        raise WidgetError(f"height must be {MIN_HEIGHT}..{MAX_HEIGHT}")


@dataclass
class TripWidget:
    html: str
    chat_data: str
    height: int


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 1] + "…"


def build_trip_widget(trip: Trip, r: RideRequest, d: Driver, t) -> TripWidget:
    """Self-contained and static: inline CSS only, no external URLs, no scripts. Every value is HTML-escaped; the same
    facts go to `chat_data` as JSON (clipped to stay under the 1024-byte limit)."""
    route = f"{_clip(r.from_text, 40)} → {_clip(r.to_text, 40)}"
    when = time_plain(r.depart_at, t)
    cost = price(trip.price, t)
    car = _clip(f"{d.car_make}, {d.car_color}, {d.car_plate}", 60)
    status = t(f"bot.status.{trip.status}")
    rows = "".join(f'<div class="r"><span>{esc(label)}</span><b>{esc(value)}</b></div>'
                   for label, value in ((t("bot.trip.time"), when), (t("bot.trip.price"), cost),
                                        (t("bot.trip.car"), car)))
    html = (
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<style>:root{{--bg:{WHITE};--fg:{INK};--mut:#5b5f66;--ac:{YELLOW}}}'
        f'@media(prefers-color-scheme:dark){{:root{{--bg:{INK};--fg:{WHITE};--mut:#a9adb4}}}}'
        'body{margin:0;padding:10px 12px;background:var(--bg);color:var(--fg);font:14px/1.35 system-ui,sans-serif}'
        '.h{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}'
        '.t{font-weight:700;font-size:15px}'
        f'.s{{background:var(--ac);color:{INK};border-radius:10px;padding:2px 9px;font-weight:600;font-size:12px}}'
        '.r{display:flex;justify-content:space-between;gap:8px;padding:2px 0}.r span{color:var(--mut)}'
        '</style>'
        f'<div class="h"><div class="t">{esc(route)}</div><div class="s">{esc(status)}</div></div>{rows}')
    data = json.dumps({"trip": trip.id, "status": trip.status, "route": route, "price": trip.price,
                       "depart": r.depart_at.isoformat() if r.depart_at else None, "car": car},
                      ensure_ascii=False, separators=(",", ":"))
    return TripWidget(html=html, chat_data=data, height=140)


async def send_trip_widget(bot: Bot, chat_id: int, widget: TripWidget, thread_id: int | None = None) -> Message | None:
    """Best effort: returns None (and logs once) when the widget is refused or the server does not know the method."""
    try:
        method = SendWidget(chat_id=chat_id, html=widget.html, height=widget.height, chat_data=widget.chat_data,
                            message_thread_id=thread_id)
        check_widget(method)
        return await delivery.call(bot, method)
    except Exception as e:                  # noqa: BLE001 — old client/server (404/400), limits, flood
        delivery.warn_once("widget", "widget not sent (%s) — the trip card is enough", e)
        return None
