"""Userbot domain logic on top of the core models (decisions 8, 48). Used by the Mini App API, the bot router and the
worker, so every rule lives here once.

Order a driver goes through: consent -> login (login.py + finish_login) -> sync/select groups -> posting (scheduler.py).
"""
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tulporgo_core.config import Settings
from tulporgo_core.db import utcnow
from tulporgo_core.enums import PostStatus, UserbotStatus
from tulporgo_core.events import UserbotStopped
from tulporgo_core.models import Driver, User, UserbotAccount, UserbotGroup, UserbotPost
from tulporgo_core.services import billing, drivers

from .client import ClientFactory, GroupInfo
from .config import ABSOLUTE_MIN_INTERVAL_MINUTES, TASHKENT_UTC_OFFSET_HOURS
from .crypto import decrypt_session, encrypt_session
from .errors import Forbidden, Invalid, NotFound

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- driver / account lookup

async def require_driver(s: AsyncSession, user: User) -> Driver:
    driver = await drivers.get_driver(s, user)
    if driver is None:
        raise Forbidden("not_driver")
    return driver


async def get_account(s: AsyncSession, driver: Driver) -> UserbotAccount | None:
    return (await s.execute(select(UserbotAccount).where(UserbotAccount.driver_id == driver.id)
                            .options(selectinload(UserbotAccount.groups)))).scalar_one_or_none()


async def require_account(s: AsyncSession, driver: Driver) -> UserbotAccount:
    account = await get_account(s, driver)
    if account is None:
        raise NotFound("not_connected")
    return account


def plan_allows_autopost(driver: Driver, settings: Settings) -> bool:
    plan = billing.effective_plan(driver, settings)
    return bool(plan and plan.autopost)


def require_plan(driver: Driver, settings: Settings) -> None:
    if not plan_allows_autopost(driver, settings):
        raise Forbidden("plan_required")


def group_limit(driver: Driver, settings: Settings, now: datetime | None = None) -> int | None:
    """How many groups the driver may have switched on: 0 = none (Basic / no subscription), None = unlimited.
    During the free period everyone is Business (billing.effective_plan)."""
    plan = billing.effective_plan(driver, settings, now)
    if plan is None or not plan.autopost:
        return 0
    return plan.max_groups


# ---------------------------------------------------------------- consent (decision 8)

async def accept_consent(s: AsyncSession, driver: Driver, settings: Settings) -> UserbotAccount:
    """Creates the account on first consent. Safe defaults come from settings (decision 48)."""
    account = await get_account(s, driver)
    if account is None:
        account = UserbotAccount(driver_id=driver.id, status=UserbotStatus.NEEDS_LOGIN,
                                 min_interval_minutes=settings.userbot_min_interval_minutes,
                                 jitter_minutes=settings.userbot_jitter_minutes, risk_acknowledged=False)
        account.groups = []
        s.add(account)
    account.consent_at = utcnow()
    await s.flush()
    return account


def require_consent(account: UserbotAccount | None) -> UserbotAccount:
    if account is None or account.consent_at is None:
        raise Forbidden("consent_required", "the risk screen must be accepted before connecting")
    return account


# ---------------------------------------------------------------- login result

async def finish_login(s: AsyncSession, account: UserbotAccount, settings: Settings, session_string: str,
                       tg_user_id: int) -> UserbotAccount:
    """The StringSession leaves this function only as a Fernet token (decision 8)."""
    require_consent(account)
    account.session_encrypted = encrypt_session(settings, session_string)
    account.tg_user_id = tg_user_id
    account.status = UserbotStatus.CONNECTED
    account.stop_reason = None
    account.flood_until = None
    await s.flush()
    return account


# ---------------------------------------------------------------- limits (decision 48)

def effective_interval(account: UserbotAccount, settings: Settings) -> int:
    """Minutes between two posts in one group. Below the safe default only if the driver acknowledged the risk."""
    if account.risk_acknowledged:
        return max(ABSOLUTE_MIN_INTERVAL_MINUTES, account.min_interval_minutes)
    return max(settings.userbot_min_interval_minutes, account.min_interval_minutes)


def effective_jitter(account: UserbotAccount, settings: Settings) -> int:
    if account.risk_acknowledged:
        return max(0, account.jitter_minutes)
    return max(settings.userbot_jitter_minutes, account.jitter_minutes)


async def update_limits(s: AsyncSession, account: UserbotAccount, settings: Settings, *,
                        interval_minutes: int | None = None, jitter_minutes: int | None = None,
                        daily_max_posts: int | None = None, clear_daily_cap: bool = False,
                        acknowledge_risk: bool = False) -> UserbotAccount:
    below = ((interval_minutes is not None and interval_minutes < settings.userbot_min_interval_minutes)
             or (jitter_minutes is not None and jitter_minutes < settings.userbot_jitter_minutes))
    if below and not acknowledge_risk:
        raise Forbidden("risk_ack_required", "lowering the safe limits needs an explicit risk acknowledgement")
    if interval_minutes is not None:
        if interval_minutes < ABSOLUTE_MIN_INTERVAL_MINUTES:
            raise Invalid("interval_too_low")
        account.min_interval_minutes = interval_minutes
    if jitter_minutes is not None:
        if jitter_minutes < 0:
            raise Invalid("bad_jitter")
        account.jitter_minutes = jitter_minutes
    if daily_max_posts is not None:
        if daily_max_posts < 1:
            raise Invalid("bad_daily_cap")
        account.daily_max_posts = daily_max_posts
    elif clear_daily_cap:
        account.daily_max_posts = None
    if below:
        account.risk_acknowledged = True
    await s.flush()
    return account


def day_start_utc(now: datetime) -> datetime:
    """Start of the driver's local day (Tashkent) as naive UTC."""
    local = now + timedelta(hours=TASHKENT_UTC_OFFSET_HOURS)
    return local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=TASHKENT_UTC_OFFSET_HOURS)


async def posts_today(s: AsyncSession, account: UserbotAccount, now: datetime) -> int:
    ids = select(UserbotGroup.id).where(UserbotGroup.account_id == account.id)
    q = select(func.count(UserbotPost.id)).where(UserbotPost.group_id.in_(ids), UserbotPost.status == PostStatus.SENT,
                                                 UserbotPost.created_at >= day_start_utc(now))
    return (await s.execute(q)).scalar_one()


# ---------------------------------------------------------------- groups

def enabled_groups(account: UserbotAccount) -> list[UserbotGroup]:
    return sorted((g for g in account.groups if g.enabled), key=lambda g: g.id)


def allowed_groups(account: UserbotAccount, driver: Driver, settings: Settings,
                   now: datetime | None = None) -> list[UserbotGroup]:
    """Enabled groups the current plan covers (first N by id). After a downgrade the rest simply stop posting."""
    limit = group_limit(driver, settings, now)
    groups = enabled_groups(account)
    return groups if limit is None else groups[:limit]


async def sync_groups(s: AsyncSession, account: UserbotAccount, found: list[GroupInfo]) -> list[UserbotGroup]:
    """Mirror the driver's writable groups. New groups start OFF — the driver picks them. Chats the driver left
    disappear. Titles are refreshed."""
    by_chat = {g.chat_id: g for g in account.groups}
    seen = {gi.chat_id for gi in found}
    for gi in found:
        g = by_chat.get(gi.chat_id)
        if g is None:
            g = UserbotGroup(account_id=account.id, chat_id=gi.chat_id, title=gi.title, enabled=False)
            account.groups.append(g)
        else:
            g.title = gi.title
    for g in [g for g in account.groups if g.chat_id not in seen]:
        await s.execute(delete(UserbotPost).where(UserbotPost.group_id == g.id))
        account.groups.remove(g)
    await s.flush()
    return sorted(account.groups, key=lambda g: g.id)


def _check_can_enable(account: UserbotAccount, driver: Driver, settings: Settings, already_enabled: int) -> None:
    limit = group_limit(driver, settings)
    if limit == 0:
        raise Forbidden("plan_required")
    if limit is not None and already_enabled >= limit:
        raise Forbidden("group_limit", f"your plan allows {limit} groups")


async def set_group_enabled(s: AsyncSession, account: UserbotAccount, driver: Driver, settings: Settings,
                            group_id: int, enabled: bool) -> UserbotGroup:
    group = next((g for g in account.groups if g.id == group_id), None)
    if group is None:
        raise NotFound("group_not_found")
    if enabled and not group.enabled:
        _check_can_enable(account, driver, settings, len(enabled_groups(account)))
    group.enabled = enabled
    await s.flush()
    return group


async def select_groups(s: AsyncSession, account: UserbotAccount, driver: Driver, settings: Settings,
                        chat_ids: list[int]) -> list[UserbotGroup]:
    """Switch exactly these groups on (everything else off), checking the plan limit."""
    wanted = set(chat_ids)
    known = {g.chat_id for g in account.groups}
    if wanted - known:
        raise NotFound("group_not_found")
    if wanted:
        _check_can_enable(account, driver, settings, len(wanted) - 1)
    for g in account.groups:
        g.enabled = g.chat_id in wanted
    await s.flush()
    return sorted(account.groups, key=lambda g: g.id)


# ---------------------------------------------------------------- pause / resume / stop / disconnect

async def pause(s: AsyncSession, account: UserbotAccount) -> UserbotAccount:
    """Driver pause. A pending flood wait is kept, so pausing and resuming never shortens Telegram's wait."""
    if account.status in (UserbotStatus.CONNECTED, UserbotStatus.FLOOD_WAIT):
        account.status = UserbotStatus.PAUSED
        await s.flush()
    return account


async def resume(s: AsyncSession, account: UserbotAccount, now: datetime | None = None) -> UserbotAccount:
    """Only a driver-paused account resumes. A flood wait or a stop is Telegram's decision, never bypassed."""
    now = now or utcnow()
    waiting = bool(account.flood_until and account.flood_until > now)
    if account.status == UserbotStatus.CONNECTED:
        return account
    if account.status == UserbotStatus.FLOOD_WAIT and waiting:
        raise Forbidden("flood_wait_active", "Telegram asked to wait; posting resumes by itself afterwards")
    if account.status == UserbotStatus.STOPPED:
        raise Forbidden("needs_login", "the account was stopped; reconnect it")
    if account.status == UserbotStatus.NEEDS_LOGIN or not account.session_encrypted:
        raise Forbidden("not_connected")
    account.status = UserbotStatus.FLOOD_WAIT if waiting else UserbotStatus.CONNECTED
    if not waiting:
        account.flood_until = None
    await s.flush()
    return account


async def stop_account(s: AsyncSession, account: UserbotAccount, reason: str, bus=None, *,
                       drop_session: bool = False) -> None:
    """Hard stop: the account never posts again until the driver logs in anew. `drop_session` is used when Telegram
    already invalidated the session (nothing left to protect or reuse)."""
    account.status = UserbotStatus.STOPPED
    account.stop_reason = reason[:256]
    if drop_session:
        account.session_encrypted = None
    await s.flush()
    if bus:
        await bus.publish(UserbotStopped(account.id, reason[:256]))


async def disconnect_account(s: AsyncSession, account: UserbotAccount, settings: Settings,
                             factory: ClientFactory | None) -> None:
    """"Hisobni uzish": end the session on Telegram's side (best effort), then delete everything session-related.
    Local deletion never depends on the network call succeeding."""
    if factory is not None and account.session_encrypted:
        client = None
        try:
            client = factory(decrypt_session(settings, account.session_encrypted))
            await client.connect()
            await client.log_out()
        except Exception as e:                      # noqa: BLE001 - logging out is best effort
            log.warning("remote log_out failed (%s); deleting the local session anyway", type(e).__name__)
        finally:
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:                   # noqa: BLE001
                    log.debug("disconnect after log_out failed")
    ids = [g.id for g in account.groups]
    if ids:
        await s.execute(delete(UserbotPost).where(UserbotPost.group_id.in_(ids)))
    for g in list(account.groups):
        account.groups.remove(g)
    account.session_encrypted = None
    account.tg_user_id = None
    account.status = UserbotStatus.NEEDS_LOGIN
    account.consent_at = None                       # a new connection shows the risk screen again
    account.flood_until = None
    account.stop_reason = None
    await s.flush()


# ---------------------------------------------------------------- status view

def status_view(account: UserbotAccount | None, driver: Driver, settings: Settings) -> dict:
    """JSON-friendly snapshot for the Mini App. Never contains the session (encrypted or not)."""
    limit = group_limit(driver, settings)
    if account is None:
        return {"status": UserbotStatus.NEEDS_LOGIN, "consent": False, "connected": False, "groups": [],
                "group_limit": limit, "autopost": limit != 0}
    return {
        "status": account.status,
        "consent": account.consent_at is not None,
        "connected": account.session_encrypted is not None and account.status != UserbotStatus.NEEDS_LOGIN,
        "stop_reason": account.stop_reason,
        "flood_until": account.flood_until.isoformat() if account.flood_until else None,
        "interval_minutes": effective_interval(account, settings),
        "jitter_minutes": effective_jitter(account, settings),
        "min_safe_interval_minutes": settings.userbot_min_interval_minutes,
        "risk_acknowledged": account.risk_acknowledged,
        "daily_max_posts": account.daily_max_posts,
        "group_limit": limit,
        "autopost": limit != 0,
        "has_template": bool(account.post_template),
        "groups": [{"id": g.id, "chat_id": g.chat_id, "title": g.title, "enabled": g.enabled}
                   for g in sorted(account.groups, key=lambda g: g.id)],
    }


PHONE = re.compile(r"^\+?\d{9,15}$")


def normalize_phone(raw: str) -> str:
    p = re.sub(r"[\s\-()]", "", raw or "")
    if not PHONE.match(p):
        raise Invalid("bad_phone")
    return p if p.startswith("+") else "+" + p
