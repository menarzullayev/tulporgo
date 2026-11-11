"""FastAPI router mounted by apps/api at /api/userbot — the Mini App driver login and userbot settings.

Auth: every route needs the Mini App header `Authorization: tma <initData>` (tulporgo_api.deps.current_user).
Login runs ONLY here, never in chat (Telegram blocks login codes sent as messages):

    POST /api/userbot/consent                       risk screen accepted -> consent_at
    POST /api/userbot/login/start      {phone}      Telegram sends the code to the driver's app
    POST /api/userbot/login/code       {code}       -> {status: "password_required"} when 2FA is on, else connected
    POST /api/userbot/login/password   {password}   2FA; never stored, never logged
    POST /api/userbot/login/cancel
    GET  /api/userbot/status                        snapshot for the UI (never contains the session)
    POST /api/userbot/groups/sync                   refresh the writable groups from Telegram
    PUT  /api/userbot/groups           {chat_ids}   switch exactly these groups on (plan limit applies)
    PATCH /api/userbot/groups/{id}     {enabled}
    PUT  /api/userbot/settings         {interval_minutes?, jitter_minutes?, daily_max_posts?, clear_daily_cap?,
                                        acknowledge_risk}
    GET/PUT /api/userbot/template      {from, to, time, seats, price?}  (+ preview text)
    POST /api/userbot/pause | /resume | /logout      ("Hisobni uzish": log out + delete the session)
    /api/userbot/feed...                            group feed filters (decision 73, see feedapi.py)

Errors are DomainErrors: JSON {error: <stable code>, detail}.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_api.deps import current_user, get_bus, get_session, get_settings
from tulporgo_core.config import Settings
from tulporgo_core.i18n import lang_of
from tulporgo_core.models import Driver, User, UserbotAccount

from . import feedapi, runtime, service, template
from .errors import Invalid, NotConfigured, NotFound
from .sync import refresh_groups

router = APIRouter(prefix="/api/userbot", tags=["userbot"])


class PhoneIn(BaseModel):
    phone: str


class GroupsIn(BaseModel):
    chat_ids: list[int]


class GroupEnabledIn(BaseModel):
    enabled: bool


class SettingsIn(BaseModel):
    interval_minutes: int | None = None
    jitter_minutes: int | None = None
    daily_max_posts: int | None = None
    clear_daily_cap: bool = False
    acknowledge_risk: bool = False


class TemplateIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_: str = Field(alias="from")
    to: str
    time: str
    seats: int
    price: int | None = None


async def _secret(request: Request, field: str) -> str:
    """Read ONE secret field (login code / 2FA password) from the JSON body by hand. A Pydantic model would make
    FastAPI echo the whole offending request body (including the secret) in its 422 response."""
    try:
        body = await request.json()
    except ValueError:
        raise Invalid("bad_request") from None
    value = body.get(field) if isinstance(body, dict) else None
    if not isinstance(value, str):
        raise Invalid("bad_request")
    return value


async def _driver(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)) -> Driver:
    return await service.require_driver(s, user)


async def _view(s: AsyncSession, driver: Driver, settings: Settings) -> dict:
    return service.status_view(await service.get_account(s, driver), driver, settings)


async def _connected_account(s: AsyncSession, driver: Driver) -> UserbotAccount:
    account = await service.require_account(s, driver)
    if not account.session_encrypted:
        raise NotFound("not_connected")
    return account


@router.get("/status")
async def status(driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                 settings: Settings = Depends(get_settings)):
    return await _view(s, driver, settings)


@router.post("/consent")
async def consent(driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                  settings: Settings = Depends(get_settings)):
    await service.accept_consent(s, driver, settings)
    return await _view(s, driver, settings)


def _login_result(result) -> tuple[str, int]:
    """A finished login always carries the session string and the Telegram user id; anything else is a failure."""
    if result.session is None or result.tg_user_id is None:
        raise Invalid("login_failed")
    return result.session, result.tg_user_id


@router.post("/login/start")
async def login_start(body: PhoneIn, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                      settings: Settings = Depends(get_settings)):
    service.require_consent(await service.get_account(s, driver))      # no consent -> no login (decision 8)
    service.require_plan(driver, settings)
    await runtime.logins().start(driver.id, service.normalize_phone(body.phone))
    return {"status": "code_sent"}


@router.post("/login/code")
async def login_code(request: Request, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                     settings: Settings = Depends(get_settings)):
    account = service.require_consent(await service.get_account(s, driver))
    result = await runtime.logins().submit_code(driver.id, await _secret(request, "code"))
    if result.status == "password_required":
        return {"status": "password_required"}
    session_string, tg_user_id = _login_result(result)
    await service.finish_login(s, account, settings, session_string, tg_user_id)
    return await _view(s, driver, settings)


@router.post("/login/password")
async def login_password(request: Request, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                         settings: Settings = Depends(get_settings)):
    account = service.require_consent(await service.get_account(s, driver))
    result = await runtime.logins().submit_password(driver.id, await _secret(request, "password"))
    session_string, tg_user_id = _login_result(result)
    await service.finish_login(s, account, settings, session_string, tg_user_id)
    return await _view(s, driver, settings)


@router.post("/login/cancel")
async def login_cancel(driver: Driver = Depends(_driver)):
    await runtime.cancel_login(driver.id)
    return {"status": "cancelled"}


@router.post("/groups/sync")
async def groups_sync(driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                      settings: Settings = Depends(get_settings), bus=Depends(get_bus)):
    account = await _connected_account(s, driver)
    await refresh_groups(s, account, settings, runtime.get_factory(), bus)
    return await _view(s, driver, settings)


@router.put("/groups")
async def groups_select(body: GroupsIn, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                        settings: Settings = Depends(get_settings)):
    account = await service.require_account(s, driver)
    await service.select_groups(s, account, driver, settings, body.chat_ids)
    return await _view(s, driver, settings)


@router.patch("/groups/{group_id}")
async def group_enabled(group_id: int, body: GroupEnabledIn, driver: Driver = Depends(_driver),
                        s: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    account = await service.require_account(s, driver)
    await service.set_group_enabled(s, account, driver, settings, group_id, body.enabled)
    return await _view(s, driver, settings)


@router.put("/settings")
async def settings_update(body: SettingsIn, driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                          settings: Settings = Depends(get_settings)):
    account = await service.require_account(s, driver)
    await service.update_limits(s, account, settings, interval_minutes=body.interval_minutes,
                                jitter_minutes=body.jitter_minutes, daily_max_posts=body.daily_max_posts,
                                clear_daily_cap=body.clear_daily_cap, acknowledge_risk=body.acknowledge_risk)
    return await _view(s, driver, settings)


@router.get("/template")
async def template_get(user: User = Depends(current_user), driver: Driver = Depends(_driver),
                       s: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    account = await service.get_account(s, driver)
    tpl = template.loads(account.post_template) if account else None
    if tpl is None:
        return {"template": None, "preview": None}
    return {"template": {"from": tpl.from_, "to": tpl.to, "time": tpl.time, "seats": tpl.seats, "price": tpl.price},
            "preview": template.build_post_text(tpl, lang_of(user.lang), settings)}


@router.put("/template")
async def template_put(body: TemplateIn, user: User = Depends(current_user), driver: Driver = Depends(_driver),
                       s: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)):
    account = await service.require_account(s, driver)
    tpl = template.make_template(body.from_, body.to, body.time, body.seats, body.price)
    account.post_template = template.dumps(tpl)
    await s.flush()
    return {"preview": template.build_post_text(tpl, lang_of(user.lang), settings)}


@router.post("/pause")
async def pause(driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                settings: Settings = Depends(get_settings)):
    await service.pause(s, await service.require_account(s, driver))
    return await _view(s, driver, settings)


@router.post("/resume")
async def resume(driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                 settings: Settings = Depends(get_settings)):
    service.require_plan(driver, settings)
    await service.resume(s, await service.require_account(s, driver))
    return await _view(s, driver, settings)


@router.post("/logout")
async def logout(driver: Driver = Depends(_driver), s: AsyncSession = Depends(get_session),
                 settings: Settings = Depends(get_settings)):
    """"Hisobni uzish": end the session on Telegram, delete it here, and drop any half-finished login."""
    account = await service.require_account(s, driver)
    await runtime.cancel_login(driver.id)
    factory = None
    if account.session_encrypted:
        try:
            factory = runtime.get_factory()
        except NotConfigured:                      # no API credentials: still delete the local session
            factory = None
    await service.disconnect_account(s, account, settings, factory)
    return await _view(s, driver, settings)


router.include_router(feedapi.router)                      # decision 73: /api/userbot/feed
