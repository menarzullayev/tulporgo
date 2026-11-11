"""Safe posting scheduler (decisions 8 and 48).

Rules enforced here, each with a negative test:
- an account posts only after consent, with a session, in status `connected`, on a plan that includes auto-posting;
- per group: at least `effective_interval` minutes since the last post, plus a random jitter; never lower than the safe
  default unless the driver acknowledged the risk; at most ONE post per account per tick; optional daily cap;
- the number of groups follows the plan (Pro <= 15, Business unlimited, Basic none; free period = Business);
- FloodWait -> status `flood_wait` until `flood_until`, nothing is sent meanwhile, no retry, no waiting in a loop;
- PeerFlood / dead session -> account `stopped` (never posts again until a new login); banned / write-forbidden in a
  chat -> that group is switched off. The driver is told through the bot and `UserbotStopped` is published.
"""
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from telethon import errors as tg
from tulporgo_core.config import Settings
from tulporgo_core.db import session_scope, utcnow
from tulporgo_core.enums import PostStatus, UserbotStatus
from tulporgo_core.events import UserbotStopped
from tulporgo_core.i18n import lang_of, t
from tulporgo_core.models import Driver, User, UserbotAccount, UserbotGroup, UserbotPost
from tulporgo_core.services import billing

from . import service, template
from .client import ClientFactory, UserbotClient
from .config import TASHKENT_UTC_OFFSET_HOURS
from .crypto import SessionUnreadable, decrypt_session
from .notifier import Notifier

log = logging.getLogger(__name__)

FLOOD_ERRORS = (tg.FloodWaitError, tg.FloodPremiumWaitError)
ACCOUNT_DEAD_ERRORS = (tg.AuthKeyUnregisteredError, tg.UserDeactivatedError, tg.UserDeactivatedBanError,
                       tg.SessionRevokedError, tg.SessionExpiredError, tg.AuthKeyDuplicatedError)
GROUP_STOP_ERRORS = (tg.UserBannedInChannelError, tg.ChatWriteForbiddenError, tg.ChatAdminRequiredError,
                     tg.ChannelPrivateError, tg.ChatRestrictedError, tg.UserNotParticipantError)


@dataclass
class _Outbox:
    """What to do after the transaction commits: notices to the driver and events for other processes."""
    notices: list[tuple[int, str, str, dict]]       # tg_id, lang, i18n key, params
    events: list


class Scheduler:
    def __init__(self, maker: async_sessionmaker[AsyncSession], settings: Settings, bus, factory: ClientFactory,
                 notifier: Notifier, *, rng: random.Random | None = None,
                 clock: Callable[[], datetime] = utcnow) -> None:
        self.maker, self.settings, self.bus, self.factory, self.notifier = maker, settings, bus, factory, notifier
        self.rng = rng or random.Random()
        self.clock = clock
        self._clients: dict[int, UserbotClient] = {}        # account id -> connected client (session only in memory)
        self._first_seen: dict[int, datetime] = {}          # group id -> when the worker first saw it
        self._offset: dict[int, float] = {}                 # group id -> jitter in minutes for the NEXT post
        self._backoff: dict[int, datetime] = {}             # group id -> do not try before (after a failed attempt)

    # ------------------------------------------------------------------ clients

    async def _client_for(self, account: UserbotAccount) -> UserbotClient:
        client = self._clients.get(account.id)
        if client is None:
            if account.session_encrypted is None:               # nothing stored: handled like a revoked session
                raise tg.AuthKeyUnregisteredError(request=None)
            client = self.factory(decrypt_session(self.settings, account.session_encrypted))
            await client.connect()
            self._clients[account.id] = client
        return client

    async def client_for(self, account: UserbotAccount) -> UserbotClient:
        """The one live client of an account, shared with the group reader (never two connections per session)."""
        return await self._client_for(account)

    def live_client(self, account_id: int) -> UserbotClient | None:
        return self._clients.get(account_id)

    async def forget(self, account_id: int) -> None:
        """Drop the live client (paused / stopped / disconnected account, or a UserbotStopped event)."""
        client = self._clients.pop(account_id, None)
        if client is not None:
            try:
                await client.disconnect()
            except Exception:                                # noqa: BLE001
                log.debug("disconnect failed for account %s", account_id)

    async def close(self) -> None:
        for account_id in list(self._clients):
            await self.forget(account_id)

    # ------------------------------------------------------------------ loop body

    async def tick(self, now: datetime | None = None) -> int:
        """One pass over all live accounts. Returns the number of posts sent."""
        now = now or self.clock()
        async with session_scope(self.maker) as s:
            rows = (await s.execute(select(UserbotAccount.id, UserbotAccount.status)
                                    .where(UserbotAccount.status.in_([UserbotStatus.CONNECTED,
                                                                      UserbotStatus.FLOOD_WAIT])))).all()
        live = {r.id for r in rows}
        for account_id in list(self._clients):
            if account_id not in live:
                await self.forget(account_id)                # paused, stopped or disconnected since the last tick
        sent = 0
        for account_id in sorted(live):
            try:
                sent += await self._process(account_id, now)
            except Exception:                                # noqa: BLE001 - one account must not stop the others
                log.exception("userbot tick failed for account %s", account_id)
        return sent

    async def _process(self, account_id: int, now: datetime) -> int:
        out = _Outbox([], [])
        async with session_scope(self.maker) as s:
            posted = await self._process_in(s, account_id, now, out)
        for ev in out.events:                                # after commit: listeners see the final state
            await self.bus.publish(ev)
        for tg_id, lang, key, params in out.notices:
            await self.notifier.send(tg_id, t(key, lang, **params))
        return posted

    async def _process_in(self, s: AsyncSession, account_id: int, now: datetime, out: _Outbox) -> int:
        account = (await s.execute(select(UserbotAccount).where(UserbotAccount.id == account_id)
                                   .options(selectinload(UserbotAccount.groups)))).scalar_one()
        # flood wait: nothing is sent before flood_until; afterwards the normal schedule resumes by itself
        if account.status == UserbotStatus.FLOOD_WAIT:
            if account.flood_until and now < account.flood_until:
                return 0
            account.status = UserbotStatus.CONNECTED
            account.flood_until = None
        if account.status != UserbotStatus.CONNECTED:
            return 0
        if account.consent_at is None or not account.session_encrypted:
            return 0                                          # no consent / no session -> never post
        driver = (await s.execute(select(Driver).where(Driver.id == account.driver_id))).scalar_one()
        plan = billing.effective_plan(driver, self.settings, now)
        if plan is None or not plan.autopost:
            return 0
        tpl = template.loads(account.post_template)
        if tpl is None:
            return 0
        groups = service.allowed_groups(account, driver, self.settings, now)
        if not groups:
            return 0
        if account.daily_max_posts is not None and await service.posts_today(s, account, now) >= account.daily_max_posts:
            return 0
        group = self._next_due_group(account, groups, now)
        if group is None:
            return 0
        user = (await s.execute(select(User).where(User.id == driver.user_id))).scalar_one()
        lang = lang_of(user.lang)
        text = template.build_post_text(tpl, lang, self.settings)
        await s.refresh(account, attribute_names=["status", "consent_at", "session_encrypted"])
        if account.status != UserbotStatus.CONNECTED or account.consent_at is None:
            return 0                                          # changed by the driver/bot since we loaded it
        return await self._post(s, account, group, user, lang, text, now, out)

    def _interval(self, account: UserbotAccount) -> timedelta:
        return timedelta(minutes=service.effective_interval(account, self.settings))

    def _next_due_group(self, account: UserbotAccount, groups: list[UserbotGroup], now: datetime) -> UserbotGroup | None:
        interval = self._interval(account)
        jitter_max = service.effective_jitter(account, self.settings)
        due: list[tuple[datetime, UserbotGroup]] = []
        for g in groups:
            if g.id not in self._offset:
                self._offset[g.id] = self.rng.uniform(0, jitter_max)
            offset = timedelta(minutes=min(self._offset[g.id], jitter_max))
            if g.last_posted_at is not None:
                due_at = g.last_posted_at + interval + offset
            else:
                due_at = self._first_seen.setdefault(g.id, now) + offset
            if (now >= due_at and (g.last_posted_at is None or now >= g.last_posted_at + interval)
                    and now >= self._backoff.get(g.id, now)):
                due.append((g.last_posted_at or datetime.min, g))
        return min(due, key=lambda x: (x[0], x[1].id))[1] if due else None

    async def _post(self, s: AsyncSession, account: UserbotAccount, group: UserbotGroup, user: User, lang, text: str,
                    now: datetime, out: _Outbox) -> int:
        try:
            client = await self._client_for(account)
            if not await client.is_authorized():
                raise tg.AuthKeyUnregisteredError(request=None)
            await client.send_message(group.chat_id, text)
        except FLOOD_ERRORS as e:
            seconds = int(getattr(e, "seconds", 0) or 0)
            account.status = UserbotStatus.FLOOD_WAIT
            account.flood_until = now + timedelta(seconds=seconds)
            self._record(s, group, PostStatus.FAILED, f"flood_wait:{seconds}")
            until = account.flood_until + timedelta(hours=TASHKENT_UTC_OFFSET_HOURS)  # shown in the driver's local time
            out.notices.append((user.tg_id, str(lang), "userbot.notify.flood_wait",
                                {"until": until.strftime("%d.%m %H:%M")}))
            log.warning("flood wait %ss for account %s", seconds, account.id)
            return 0
        except tg.PeerFloodError:
            await self._stop(s, account, "peer_flood", user, lang, out, key="userbot.notify.peer_flood")
            return 0
        except (*ACCOUNT_DEAD_ERRORS, SessionUnreadable) as e:
            reason = type(e).__name__.removesuffix("Error")
            await self._stop(s, account, reason, user, lang, out, drop_session=True)
            return 0
        except GROUP_STOP_ERRORS as e:
            reason = type(e).__name__.removesuffix("Error")
            group.enabled = False
            self._record(s, group, PostStatus.FAILED, reason)
            out.events.append(UserbotStopped(account.id, f"group:{group.chat_id}:{reason}"))
            out.notices.append((user.tg_id, str(lang), "userbot.notify.group_stopped",
                                {"title": group.title, "reason": reason}))
            return 0
        except tg.SlowModeWaitError as e:                            # this chat only; not an account-level flood
            self._backoff[group.id] = now + timedelta(seconds=int(e.seconds or 0))
            self._record(s, group, PostStatus.SKIPPED, f"slow_mode:{e.seconds}")
            return 0
        except Exception as e:                                       # noqa: BLE001 - unknown failure: no retry loop
            self._backoff[group.id] = now + self._interval(account)
            self._record(s, group, PostStatus.FAILED, type(e).__name__)
            log.warning("post to group %s failed: %s", group.id, type(e).__name__)
            return 0
        group.last_posted_at = now
        self._offset[group.id] = self.rng.uniform(0, service.effective_jitter(account, self.settings))
        self._record(s, group, PostStatus.SENT, None)
        return 1

    def _record(self, s: AsyncSession, group: UserbotGroup, status: str, error: str | None) -> None:
        s.add(UserbotPost(group_id=group.id, status=status, error=error))

    async def _stop(self, s: AsyncSession, account: UserbotAccount, reason: str, user: User, lang, out: _Outbox, *,
                    drop_session: bool = False, key: str = "userbot.notify.account_stopped") -> None:
        account.status = UserbotStatus.STOPPED
        account.stop_reason = reason[:256]
        if drop_session:
            account.session_encrypted = None
        out.events.append(UserbotStopped(account.id, reason[:256]))
        out.notices.append((user.tg_id, str(lang), key, {"reason": reason}))
        await self.forget(account.id)
        log.warning("userbot account %s stopped: %s", account.id, reason)
