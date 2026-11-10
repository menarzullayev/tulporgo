"""The driver's post template (route, time, seats, price) and the text that goes into groups.

Stored as JSON in `UserbotAccount.post_template`. The text is assembled from i18n lines — the driver never types a
free-form message, so no spam links can slip in: values containing `@`, URLs or domain-like words are rejected, and the
only contact line is the fixed "@tulporgobot orqali bog'laning" (decision 8/48).
"""
import json
import re
from dataclasses import asdict, dataclass

from tulporgo_core.config import Settings
from tulporgo_core.i18n import t

from .errors import Invalid

FIELD_MAX = 60
LINK_LIKE = re.compile(r"(@|https?:|www\.|t\.me|telegram\.me|tg://|://|\b[\w-]+\.(com|uz|ru|org|net|me|io|ai|info|xyz)\b)",
                       re.I)
MAX_PRICE = 100_000_000


@dataclass(frozen=True)
class Template:
    from_: str
    to: str
    time: str
    seats: int
    price: int | None = None          # None = "narx kelishiladi" (decision 7): the price line is omitted


def clean_text(name: str, value: str) -> str:
    v = re.sub(r"\s+", " ", (value or "")).strip()
    if not v or len(v) > FIELD_MAX or LINK_LIKE.search(v):
        raise Invalid("bad_template", f"invalid {name}")
    return v


def parse_seats(value: str | int) -> int:
    try:
        n = int(str(value).strip())
    except ValueError as e:
        raise Invalid("bad_template", "invalid seats") from e
    if not 1 <= n <= 8:
        raise Invalid("bad_template", "invalid seats")
    return n


def parse_price(value: str | int | None) -> int | None:
    if value is None or str(value).strip() in ("", "-"):
        return None
    digits = re.sub(r"[\s,.]", "", str(value))
    if not digits.isdigit() or not 0 < int(digits) <= MAX_PRICE:
        raise Invalid("bad_template", "invalid price")
    return int(digits)


def make_template(from_: str, to: str, time: str, seats: str | int, price: str | int | None = None) -> Template:
    return Template(clean_text("from", from_), clean_text("to", to), clean_text("time", time), parse_seats(seats),
                    parse_price(price))


def dumps(tpl: Template) -> str:
    return json.dumps(asdict(tpl), ensure_ascii=False)


def loads(raw: str | None) -> Template | None:
    """Stored template, or None when missing/corrupt (a corrupt template must not crash the worker)."""
    if not raw:
        return None
    try:
        d = json.loads(raw)
        return make_template(d["from_"], d["to"], d["time"], d["seats"], d.get("price"))
    except (ValueError, KeyError, TypeError, Invalid):
        return None


def build_post_text(tpl: Template, lang, settings: Settings) -> str:
    lines = [t("userbot.post.route", lang, from_=tpl.from_, to=tpl.to), t("userbot.post.time", lang, time=tpl.time),
             t("userbot.post.seats", lang, seats=tpl.seats)]
    if tpl.price:
        lines.append(t("userbot.post.price", lang, price=f"{tpl.price:,}".replace(",", " ")))
    lines.append(t("userbot.post.contact", lang, bot=settings.bot_username))
    return "\n".join(lines)
