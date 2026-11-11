"""Feed card text and buttons (decision 73). Plain HTML message + inline buttons, so old Telegram apps show it too
(CLAUDE.md rule 6). User content (excerpt, usernames, group titles) is HTML-escaped and never alphabet-converted."""
import html
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from tulporgo_core.groupscan import Detection
from tulporgo_core.i18n import t

UZT = timezone(timedelta(hours=5))
EXCERPT = 200


def message_link(chat_id: int, message_id: int, chat_username: str | None = None) -> str | None:
    """t.me link that opens the message for members; basic groups (no -100 prefix) have no message links."""
    if chat_username:
        return f"https://t.me/{chat_username}/{message_id}"
    s = str(chat_id)
    return f"https://t.me/c/{s[4:]}/{message_id}" if s.startswith("-100") else None


@dataclass(frozen=True)
class CardGroup:
    chat_id: int
    message_id: int
    title: str
    chat_username: str | None = None


def when_text(det: Detection, lang: str, now: datetime) -> str:
    if det.depart_at is None:
        return t("feed.when.now", lang)
    local = det.depart_at.replace(tzinfo=UTC).astimezone(UZT)
    today = now.replace(tzinfo=UTC).astimezone(UZT).date()
    hm = local.strftime("%H:%M")
    if local.date() == today:
        return t("feed.when.today", lang, hm=hm)
    if local.date() == today + timedelta(days=1):
        return t("feed.when.tomorrow", lang, hm=hm)
    return t("feed.when.date", lang, date=local.strftime("%d.%m"), hm=hm)


def render(det: Detection, groups: list[CardGroup], lang: str, now: datetime, *, excerpt: str = "",
           author: str | None = None, filter_name: str | None = None) -> tuple[str, list[list[dict]]]:
    unknown = t("feed.unknown_place", lang)
    frm = det.from_place.name if det.from_place else unknown
    to = det.to_place.name if det.to_place else unknown
    head = f"<b>{t(f'feed.kind.{det.kind}', lang)}</b> · {html.escape(frm, quote=False)} → {html.escape(to, quote=False)}"
    facts = [when_text(det, lang, now), t("feed.seats", lang, n=det.seats)]
    if det.cargo:
        facts.append(t("feed.cargo", lang))
    lines = [head, "🕒 " + " · ".join(facts)]
    lines.append(t("feed.groups", lang, titles=html.escape(", ".join(g.title for g in groups), quote=False)))
    text = " ".join(excerpt.split())
    if text:
        cut = text[:EXCERPT] + ("…" if len(text) > EXCERPT else "")
        lines.append(f"<i>«{html.escape(cut, quote=False)}»</i>")
    if author:
        lines.append(f"👤 @{html.escape(author, quote=False)}")
    if filter_name:
        lines.append(t("feed.filter", lang, name=html.escape(filter_name, quote=False)))
    rows: list[list[dict]] = []
    for g in groups:
        link = message_link(g.chat_id, g.message_id, g.chat_username)
        if link:
            rows.append([{"text": t("feed.open", lang, title=g.title[:40]), "url": link}])
    rows.append([{"text": t("feed.taken", lang), "callback_data": "feed:taken"},
                 {"text": t("feed.pause", lang), "callback_data": "feed:pause"}])
    return "\n".join(lines), rows
