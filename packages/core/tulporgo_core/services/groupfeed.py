"""Group feed (decision 73): who reads which group, which drivers a detected request goes to, and when.

- One reader account per group, only for groups that at least one driver selected (a group nobody asked for is never
  read). Readers are connected accounts whose owner accepted consent version 2 ("may watch groups, only reads").
- A request goes only to drivers who are members of that group (from the groups sync), have an active plan, are not
  paused, and have an enabled filter that matches. Biznes gets it at once, every other plan 60 s later.
- Duplicates (the same request posted in several groups) within 30 minutes are one event.
Nothing here stores the group message.
"""
import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..enums import UserbotStatus
from ..groupscan import Detection
from ..models import Driver, DriverFilter, GroupReader, UserbotAccount, UserbotGroup
from ..places import to_latin
from .billing import PlanInfo, effective_plan

UZT = timezone(timedelta(hours=5))
READ_CONSENT_VERSION = 2
OTHERS_DELAY = timedelta(seconds=60)          # decision 73: Biznes first, everybody else 60 s later
DEDUPE_WINDOW = timedelta(minutes=30)
CARD_TTL = timedelta(hours=2)
MEMBER_STATUSES = (UserbotStatus.CONNECTED, UserbotStatus.PAUSED, UserbotStatus.FLOOD_WAIT)

AreaOf = Callable[[int], int | None]           # place id -> district/city id (PlaceRef.area)


# ---------- matching ----------

def _hm(value: str | None) -> time | None:
    if not value:
        return None
    h, m = value.split(":")
    return time(int(h), int(m))


def _in_window(t: time, start: time | None, end: time | None) -> bool:
    if start is None and end is None:
        return True
    start, end = start or time(0, 0), end or time(23, 59)
    return start <= t <= end if start <= end else (t >= start or t <= end)        # 22:00–02:00 crosses midnight


def _on_corridor(frm: int | None, to: int | None, a: int | None, b: int | None, corridors: Sequence[Sequence[int]]) -> bool:
    """Request a→b lies on the filter route frm→to along some corridor, same direction (both ends known)."""
    if frm is None or to is None or a is None or b is None:
        return False
    for c in corridors:
        pos = {area: i for i, area in enumerate(c)}
        if all(x in pos for x in (frm, to, a, b)):
            lo, hi = pos[frm], pos[to]
            pa, pb = pos[a], pos[b]
            if lo < hi and lo <= pa < pb <= hi:
                return True
            if lo > hi and lo >= pa > pb >= hi:
                return True
    return False


def route_matches(routes: list, det: Detection, area_of: AreaOf, corridors: Sequence[Sequence[int]] = ()) -> bool:
    if not routes:
        return True
    a = det.from_place.area if det.from_place else None
    b = det.to_place.area if det.to_place else None
    for r in routes:
        frm = area_of(r["from"]) if r.get("from") else None
        to = area_of(r["to"]) if r.get("to") else None
        same_from = frm is None or a is None or frm == a
        same_to = to is None or b is None or to == b
        anchored = (frm is not None and frm == a) or (to is not None and to == b) or (frm is None and to is None)
        if same_from and same_to and anchored:
            return True
        if r.get("on_way") and _on_corridor(frm, to, a, b, corridors):
            return True
    return False


def filter_matches(f: DriverFilter, det: Detection, chat_id: int, now: datetime, area_of: AreaOf,
                   corridors: Sequence[Sequence[int]] = ()) -> bool:
    """`now` and `det.depart_at` are naive UTC (project convention)."""
    if not f.enabled:
        return False
    if f.kinds and det.kind not in f.kinds:
        return False
    if f.group_chat_ids and chat_id not in f.group_chat_ids:
        return False
    if f.seats_min and det.seats < f.seats_min or f.seats_max and det.seats > f.seats_max:
        return False
    if not route_matches(f.routes or [], det, area_of, corridors):
        return False
    local_now = now.replace(tzinfo=UTC).astimezone(UZT)
    if det.depart_at is None:
        if not f.include_asap:
            return False
        when = local_now
    else:
        when = det.depart_at.replace(tzinfo=UTC).astimezone(UZT)
        if when.date() > local_now.date() and not f.include_tomorrow:
            return False
    if f.weekdays and when.weekday() not in f.weekdays:
        return False
    return _in_window(when.time(), _hm(f.time_from), _hm(f.time_to))


@dataclass(frozen=True)
class Recipient:
    driver: Driver
    plan: PlanInfo
    filter_name: str
    delay: timedelta


async def recipients(s: AsyncSession, chat_id: int, det: Detection, settings: Settings, area_of: AreaOf,
                     now: datetime, corridors: Sequence[Sequence[int]] = ()) -> list[Recipient]:
    """Drivers who are members of `chat_id` (selected taxi group) and whose filter matches, Biznes first."""
    rows = (await s.execute(
        select(Driver).join(UserbotAccount, UserbotAccount.driver_id == Driver.id)
        .join(UserbotGroup, UserbotGroup.account_id == UserbotAccount.id)
        .where(UserbotGroup.chat_id == chat_id, UserbotGroup.enabled.is_(True),
               UserbotAccount.status.in_(MEMBER_STATUSES), Driver.feed_paused.is_(False))
    )).scalars().unique().all()
    out: list[Recipient] = []
    for d in rows:
        if d.user.is_blocked:
            continue
        plan = effective_plan(d, settings, now)
        if plan is None:
            continue
        filters = (await s.execute(select(DriverFilter).where(DriverFilter.driver_id == d.id,
                                                              DriverFilter.enabled.is_(True)))).scalars().all()
        hit = next((f for f in filters if filter_matches(f, det, chat_id, now, area_of, corridors)), None)
        if hit:
            out.append(Recipient(d, plan, hit.name, timedelta(0) if plan.priority else OTHERS_DELAY))
    return sorted(out, key=lambda r: (r.delay, r.driver.id))


# ---------- readers ----------

async def wanted_groups(s: AsyncSession) -> set[int]:
    """Groups at least one driver with an enabled filter selected — the only groups that are ever read."""
    rows = await s.execute(
        select(UserbotGroup.chat_id, DriverFilter.group_chat_ids)
        .join(UserbotAccount, UserbotGroup.account_id == UserbotAccount.id)
        .join(Driver, Driver.id == UserbotAccount.driver_id)
        .join(DriverFilter, DriverFilter.driver_id == Driver.id)
        .where(UserbotGroup.enabled.is_(True), DriverFilter.enabled.is_(True), Driver.feed_paused.is_(False),
               UserbotAccount.status.in_(MEMBER_STATUSES)))
    out: set[int] = set()
    for row in rows:
        chat: int = row[0]
        chosen: list[int] = row[1] or []
        if not chosen or chat in chosen:
            out.add(chat)
    return out


async def assign_readers(s: AsyncSession, now: datetime) -> dict[int, int]:
    """chat_id -> account_id. Keeps a working reader; otherwise picks the member account that already reads the most
    groups (fewer live connections). Drops readers of groups nobody wants any more."""
    wanted = await wanted_groups(s)
    able = (await s.execute(
        select(UserbotGroup.chat_id, UserbotAccount.id)
        .join(UserbotAccount, UserbotGroup.account_id == UserbotAccount.id)
        .where(UserbotAccount.status == UserbotStatus.CONNECTED,
               UserbotAccount.consent_version >= READ_CONSENT_VERSION,
               UserbotAccount.session_encrypted.is_not(None)))).all()
    members: dict[int, set[int]] = {}
    for chat, acc in able:
        members.setdefault(chat, set()).add(acc)
    current = {r.chat_id: r for r in (await s.execute(select(GroupReader))).scalars()}
    load: dict[int, int] = {}
    result: dict[int, int] = {}
    for chat, r in current.items():
        if chat in wanted and r.account_id in members.get(chat, set()):
            result[chat] = r.account_id
            load[r.account_id] = load.get(r.account_id, 0) + 1
        else:
            await s.delete(r)
    for chat in sorted(wanted - set(result)):
        cands = members.get(chat)
        if not cands:
            continue
        acc = max(sorted(cands), key=lambda a: load.get(a, 0))
        s.add(GroupReader(chat_id=chat, account_id=acc, assigned_at=now))
        result[chat] = acc
        load[acc] = load.get(acc, 0) + 1
    await s.flush()
    return result


# ---------- duplicates ----------

def _text_key(text: str) -> str:
    t = re.sub(r"[^a-z0-9]", "", to_latin(text))
    return hashlib.sha256(t.encode()).hexdigest()[:16]


@dataclass
class FeedEvent:
    key: str
    detection: Detection
    first_seen: datetime
    links: list[tuple[int, int]] = field(default_factory=list)       # (chat_id, message_id)


class Deduper:
    """In memory only. Same author + route + departure (30-min bucket), or the same text, within 30 minutes."""

    def __init__(self, window: timedelta = DEDUPE_WINDOW) -> None:
        self.window = window
        self._events: dict[str, FeedEvent] = {}

    @staticmethod
    def keys(author_id: int | None, det: Detection, text: str) -> list[str]:
        out = [f"t:{_text_key(text)}"]
        if author_id:
            bucket = int(det.depart_at.timestamp() // 1800) if det.depart_at else "now"
            a = det.from_place.area if det.from_place else "-"
            b = det.to_place.area if det.to_place else "-"
            out.append(f"r:{author_id}:{a}:{b}:{bucket}")
        return out

    def add(self, author_id: int | None, det: Detection, text: str, chat_id: int, message_id: int,
            now: datetime) -> tuple[bool, FeedEvent]:
        """(is_new, event). A duplicate adds its group link to the existing event."""
        self._events = {k: e for k, e in self._events.items() if now - e.first_seen < self.window}
        keys = self.keys(author_id, det, text)
        for k in keys:
            if k in self._events:
                ev = self._events[k]
                if all(c != chat_id for c, _ in ev.links):
                    ev.links.append((chat_id, message_id))
                for kk in keys:
                    self._events.setdefault(kk, ev)
                return False, ev
        ev = FeedEvent(keys[0], det, now, [(chat_id, message_id)])
        for k in keys:
            self._events[k] = ev
        return True, ev
