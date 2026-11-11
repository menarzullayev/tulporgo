"""Live reading of taxi groups for drivers (decision 73).

Every tick: `groupfeed.assign_readers` picks one reader account per wanted group; the reader's live Telethon client
(shared with the posting scheduler, never a second connection for the same session) gets a message hook. A message in
a group assigned to THAT account is detected locally, merged with duplicates, and every matching member driver gets a
card from @tulporgobot — Biznes at once, others 60 s later. A duplicate in another group adds its link to cards already
sent and reaches members of that group who had no card yet. The text is dropped after detection; only the card's own
message id is kept (FeedCard) so the bot can delete it after 2 hours.
"""
import asyncio
import contextlib
import functools
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope, utcnow
from tulporgo_core.groupscan import MIN_CONFIDENCE, detect
from tulporgo_core.i18n import lang_of
from tulporgo_core.models import Driver, FeedCard, User, UserbotAccount, UserbotGroup
from tulporgo_core.places import PlaceIndex
from tulporgo_core.services import groupfeed

from . import cards
from .client import GroupMessage, UserbotClient

log = logging.getLogger(__name__)
INDEX_TTL = timedelta(minutes=10)


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
        self.clock, self.corridors, self.sleep = clock, corridors, sleep
        self.deduper = groupfeed.Deduper()
        self._assigned: dict[int, set[int]] = {}               # account id -> chats it reads
        self._hooked: dict[int, UserbotClient] = {}            # account id -> client that carries our hook
        self._index: PlaceIndex | None = None
        self._areas: dict[int, int] = {}
        self._index_at: datetime | None = None
        # event key -> driver id -> (chat, message id, groups on the card, filter name); dropped with the event
        self._sent: dict[str, dict[int, tuple[int, int, list[cards.CardGroup], str]]] = {}
        self._sent_at: dict[str, datetime] = {}
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
            self._hooked[acc_id] = client
        await self.purge(now)
        for key in [k for k, at in self._sent_at.items() if now - at > groupfeed.DEDUPE_WINDOW]:
            self._sent.pop(key, None)
            self._sent_at.pop(key, None)
        return assignment

    async def _places(self, s: AsyncSession, now: datetime) -> PlaceIndex:
        if self._index is None or self._index_at is None or now - self._index_at > INDEX_TTL:
            self._index = await PlaceIndex.load(s)
            self._areas = {r.id: r.area for r in self._index.refs}
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
        sent = self._sent.setdefault(event.key, {})
        self._sent_at.setdefault(event.key, event.first_seen)
        group = cards.CardGroup(msg.chat_id, msg.message_id, titles.get(msg.chat_id, "?"), msg.chat_username)
        for r, user in plan:
            if r.driver.id in sent:
                await self._add_link(r.driver.id, sent, group, det, user, now, msg)
                continue
            sent[r.driver.id] = (0, 0, [group], r.filter_name)          # reserved: no second card for this event
            job = self._deliver(r.driver, user, sent, det, msg, r.filter_name, r.delay)
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
                       delay: timedelta) -> None:
        if delay:
            await self.sleep(delay.total_seconds())
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
