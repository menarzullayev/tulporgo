"""Live reading of taxi groups for drivers (decision 73).

Every tick: `groupfeed.assign_readers` picks one reader account per wanted group; the reader's live Telethon client
(shared with the posting scheduler, never a second connection for the same session) gets a message hook. A message in
a group assigned to THAT account is detected locally, merged with duplicates, and every matching member driver gets a
card from @tulporgobot — Biznes at once, others 60 s later. A duplicate in another group adds its link to cards already
sent and reaches members of that group who had no card yet. The text is dropped after detection; only the card's own
message id is kept (FeedCard) so the bot can delete it after 2 hours.

Decision 75: passengers delete their post once they have a taxi. While its cards live, the reader keeps (in memory only)
which group messages a request came from; when all of them are deleted, every card says so, loses its buttons and is
deleted 10 minutes later, and a delayed card that was not sent yet is not sent at all.
"""
import asyncio
import contextlib
import functools
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope, utcnow
from tulporgo_core.groupscan import MIN_CONFIDENCE, Detection, detect
from tulporgo_core.i18n import lang_of
from tulporgo_core.models import Driver, FeedCard, User, UserbotAccount, UserbotGroup
from tulporgo_core.places import PlaceIndex, corridors
from tulporgo_core.services import groupfeed

from . import cards
from .client import GroupDeletion, GroupMessage, UserbotClient

log = logging.getLogger(__name__)
INDEX_TTL = timedelta(minutes=10)
CHANNEL_ID_LIMIT = -1_000_000_000_000                         # marked ids below this are supergroups / channels


@dataclass
class _Request:
    """One request (all its duplicates) while its cards live. Ids and the detection only — never the text."""
    det: Detection
    first_seen: datetime
    sources: set[tuple[int, int]] = field(default_factory=set)          # (group chat id, message id) still posted
    cards: dict[int, tuple[int, int, str]] = field(default_factory=dict)  # driver id -> (chat, card message id, lang)
    gone: bool = False


class CardSender(Protocol):
    async def send(self, chat_id: int, text: str, buttons: list[list[dict]]) -> int | None: ...
    async def edit(self, chat_id: int, message_id: int, text: str, buttons: list[list[dict]]) -> None: ...
    async def delete(self, chat_id: int, message_id: int) -> None: ...


class BotCardSender:
    """@tulporgobot sends the cards; a failure (bot removed from the channel, blocked) only skips that card."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @staticmethod
    def _markup(buttons: list[list[dict]]):
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(**b) for b in row] for row in buttons])

    async def send(self, chat_id: int, text: str, buttons: list[list[dict]]) -> int | None:
        try:
            m = await self.bot.send_message(chat_id, text, reply_markup=self._markup(buttons),
                                            disable_web_page_preview=True)
            return m.message_id
        except Exception as e:                                  # noqa: BLE001
            log.warning("card not sent to %s: %s", chat_id, type(e).__name__)
            return None

    async def edit(self, chat_id: int, message_id: int, text: str, buttons: list[list[dict]]) -> None:
        with contextlib.suppress(Exception):
            await self.bot.edit_message_text(text, chat_id=chat_id, message_id=message_id,
                                             reply_markup=self._markup(buttons), disable_web_page_preview=True)

    async def delete(self, chat_id: int, message_id: int) -> None:
        with contextlib.suppress(Exception):
            await self.bot.delete_message(chat_id, message_id)


class Reader:
    def __init__(self, maker: async_sessionmaker[AsyncSession], settings: Settings,
                 client_for: Callable[[UserbotAccount], Awaitable[UserbotClient]],
                 live_client: Callable[[int], UserbotClient | None], sender: CardSender, *,
                 clock: Callable[[], datetime] = utcnow, corridors: Sequence[Sequence[int]] = (),
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.maker, self.settings, self.sender = maker, settings, sender
        self.client_for, self.live_client = client_for, live_client
        self.clock, self.sleep = clock, sleep
        self.corridors: Sequence[Sequence[int]] = corridors
        self._fixed_corridors = bool(corridors)
        self.deduper = groupfeed.Deduper()
        self._assigned: dict[int, set[int]] = {}               # account id -> chats it reads
        self._hooked: dict[int, UserbotClient] = {}            # account id -> client that carries our hook
        self._index: PlaceIndex | None = None
        self._areas: dict[int, int] = {}
        self._index_at: datetime | None = None
        # event key -> driver id -> (chat, message id, groups on the card, filter name); dropped with the event
        self._sent: dict[str, dict[int, tuple[int, int, list[cards.CardGroup], str]]] = {}
        self._sent_at: dict[str, datetime] = {}
        self._requests: dict[str, _Request] = {}               # event key -> request (dedupe window)
        self._by_source: dict[tuple[int, int], _Request] = {}  # group message -> request (card lifetime)
        self._tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------ assignment

    async def refresh(self, now: datetime | None = None) -> dict[int, int]:
        now = now or self.clock()
        async with session_scope(self.maker) as s:
            assignment = await groupfeed.assign_readers(s, now)
            accounts = {a.id: a for a in (await s.execute(
                select(UserbotAccount).where(UserbotAccount.id.in_(set(assignment.values()))))).scalars()}
        by_account: dict[int, set[int]] = {}
        for chat, acc in assignment.items():
            by_account.setdefault(acc, set()).add(chat)
        self._assigned = by_account
        for acc_id, account in accounts.items():
            if self._hooked.get(acc_id) is not None and self._hooked[acc_id] is self.live_client(acc_id):
                continue
            try:
                client = await self.client_for(account)
            except Exception as e:                             # noqa: BLE001 - the posting scheduler handles dead sessions
                log.warning("reader %s not connected: %s", acc_id, type(e).__name__)
                continue
            client.on_group_message(functools.partial(self.handle, acc_id))
            client.on_group_delete(functools.partial(self.handle_delete, acc_id))
            self._hooked[acc_id] = client
        await self.purge(now)
        for key in [k for k, at in self._sent_at.items() if now - at > groupfeed.DEDUPE_WINDOW]:
            self._sent.pop(key, None)
            self._sent_at.pop(key, None)
            self._requests.pop(key, None)
        for src in [k for k, r in self._by_source.items() if now - r.first_seen > groupfeed.CARD_TTL]:
            del self._by_source[src]
        return assignment

    async def _places(self, s: AsyncSession, now: datetime) -> PlaceIndex:
        if self._index is None or self._index_at is None or now - self._index_at > INDEX_TTL:
            self._index = await PlaceIndex.load(s)
            self._areas = {r.id: r.area for r in self._index.refs}
            if not self._fixed_corridors:
                self.corridors = corridors(self._index)                # owner-approved roads (data/corridors.csv)
            self._index_at = now
        return self._index

    # ------------------------------------------------------------ messages

    async def handle(self, account_id: int, msg: GroupMessage) -> None:
        if msg.chat_id not in self._assigned.get(account_id, set()):
            return                                              # another account reads this group
        now = self.clock()
        try:
            async with session_scope(self.maker) as s:
                det = detect(msg.text, await self._places(s, now), now)
                if det is None or det.confidence < MIN_CONFIDENCE:
                    return
                _new, event = self.deduper.add(msg.sender_id, det, msg.text, msg.chat_id, msg.message_id, now)
                recips = await groupfeed.recipients(s, msg.chat_id, det, self.settings, self._areas.get, now,
                                                    self.corridors)
                titles = await self._titles(s, [c for c, _ in event.links])
                plan = [(r, r.driver.user) for r in recips]               # Driver.user is loaded eagerly
        except Exception:                                       # noqa: BLE001 - one bad message must not stop reading
            log.exception("feed message failed")
            return
        req = self._requests.get(event.key)
        if req is not None and req.gone:                        # deleted and posted again: a new live request
            self._sent[event.key] = {}
        if req is None or req.gone:
            req = self._requests[event.key] = _Request(det, now)
        sent = self._sent.setdefault(event.key, {})
        self._sent_at.setdefault(event.key, event.first_seen)
        req.sources.add((msg.chat_id, msg.message_id))
        self._by_source[(msg.chat_id, msg.message_id)] = req
        group = cards.CardGroup(msg.chat_id, msg.message_id, titles.get(msg.chat_id, "?"), msg.chat_username)
        for r, user in plan:
            if r.driver.id in sent:
                await self._add_link(r.driver.id, sent, group, det, user, now, msg)
                continue
            sent[r.driver.id] = (0, 0, [group], r.filter_name)          # reserved: no second card for this event
            job = self._deliver(r.driver, user, sent, det, msg, r.filter_name, r.delay, req)
            if r.delay:
                task = asyncio.ensure_future(job)
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            else:
                await job

    async def _titles(self, s: AsyncSession, chats: list[int]) -> dict[int, str]:
        rows = await s.execute(select(UserbotGroup.chat_id, UserbotGroup.title).where(UserbotGroup.chat_id.in_(chats)))
        return {c: title for c, title in rows}

    async def _deliver(self, driver: Driver, user: User, sent: dict, det, msg: GroupMessage, filter_name: str,
                       delay: timedelta, req: _Request) -> None:
        if delay:
            await self.sleep(delay.total_seconds())
        if req.gone:
            return                                              # the passenger deleted the request meanwhile
        now = self.clock()
        _, _, groups, _ = sent[driver.id]
        lang = str(lang_of(user.lang))
        text, buttons = cards.render(det, groups, lang, now, excerpt=msg.text, author=msg.sender_username,
                                     filter_name=filter_name)
        target = driver.delivery_chat_id or user.tg_id
        message_id = await self.sender.send(target, text, buttons)
        if message_id is None:
            return
        sent[driver.id] = (target, message_id, groups, filter_name)
        req.cards[driver.id] = (target, message_id, lang)
        async with session_scope(self.maker) as s:
            s.add(FeedCard(driver_id=driver.id, chat_id=target, message_id=message_id,
                           delete_at=now + groupfeed.CARD_TTL))

    async def _add_link(self, driver_id: int, sent: dict, group: cards.CardGroup, det, user: User, now: datetime,
                        msg: GroupMessage) -> None:
        target, message_id, groups, filter_name = sent[driver_id]
        if any(g.chat_id == group.chat_id for g in groups):
            return
        groups.append(group)
        if message_id:                                          # already sent: show the new group too
            text, buttons = cards.render(det, groups, str(lang_of(user.lang)), now, excerpt=msg.text,
                                         author=msg.sender_username, filter_name=filter_name)
            await self.sender.edit(target, message_id, text, buttons)

    # ------------------------------------------------------------ deletions (decision 75)

    async def handle_delete(self, account_id: int, deletion: GroupDeletion) -> None:
        mine = self._assigned.get(account_id, set())
        for mid in deletion.message_ids:
            if deletion.chat_id is not None:
                keys = [(deletion.chat_id, mid)]
            else:                                               # basic group: no chat id, ids unique per account
                keys = [k for k in self._by_source if k[1] == mid and k[0] in mine and k[0] > CHANNEL_ID_LIMIT]
            for key in keys:
                req = self._by_source.pop(key, None)
                if req is None:
                    continue
                req.sources.discard(key)
                if not req.sources and not req.gone:
                    try:
                        await self._mark_gone(req)
                    except Exception:                           # noqa: BLE001 - one bad card must not stop reading
                        log.exception("marking a deleted request failed")

    async def _mark_gone(self, req: _Request) -> None:
        req.gone = True
        now = self.clock()
        for chat, message_id, lang in req.cards.values():
            text, buttons = cards.render_gone(req.det, lang)
            await self.sender.edit(chat, message_id, text, buttons)
        if req.cards:
            async with session_scope(self.maker) as s:
                for chat, message_id, _ in req.cards.values():
                    await s.execute(update(FeedCard)
                                    .where(FeedCard.chat_id == chat, FeedCard.message_id == message_id,
                                           FeedCard.delete_at > now + groupfeed.GONE_TTL)
                                    .values(delete_at=now + groupfeed.GONE_TTL))

    # ------------------------------------------------------------ housekeeping

    async def purge(self, now: datetime | None = None) -> int:
        """Delete cards older than 2 hours (decision 73)."""
        now = now or self.clock()
        async with session_scope(self.maker) as s:
            due = (await s.execute(select(FeedCard).where(FeedCard.delete_at <= now))).scalars().all()
            for c in due:
                await self.sender.delete(c.chat_id, c.message_id)
            if due:
                await s.execute(delete(FeedCard).where(FeedCard.id.in_([c.id for c in due])))
        return len(due)

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
