"""Shared test helpers (fake Telethon client, driver/account builders). Not named conftest on purpose."""
import itertools
from datetime import timedelta

from tulporgo_core.db import utcnow
from tulporgo_core.enums import Plan, UserbotStatus
from tulporgo_core.models import UserbotAccount, UserbotGroup
from tulporgo_core.services import drivers, users
from tulporgo_userbot import crypto, template
from tulporgo_userbot.client import GroupInfo

SESSION_PLAIN = "1ApWapzMBu-FAKE-SESSION-STRING-DO-NOT-LEAK"
_ids = itertools.count(5000)


class FakeClient:
    """Stands in for a Telethon client. Behaviour is configured on the factory so tests can change it on the fly."""

    def __init__(self, factory: "FakeFactory", session: str | None) -> None:
        self.f, self.session = factory, session
        self.connected = False
        self.disconnected = False
        self.logged_out = False
        self.handlers: list = []                     # group-message hooks (decision 73 reader)

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.disconnected = True

    async def is_authorized(self) -> bool:
        return self.f.authorized

    async def send_code(self, phone: str) -> str:
        if self.f.send_code_error:
            raise self.f.send_code_error
        self.f.code_requests.append(phone)
        return "HASH-1"

    async def sign_in_code(self, phone: str, code: str, code_hash: str) -> int:
        if code_hash != "HASH-1":
            raise AssertionError("wrong code hash passed")
        if self.f.code_error and code != self.f.good_code:
            raise self.f.code_error
        if code != self.f.good_code:
            from telethon.errors import PhoneCodeInvalidError
            raise PhoneCodeInvalidError(request=None)
        if self.f.needs_password:
            from telethon.errors import SessionPasswordNeededError
            raise SessionPasswordNeededError(request=None)
        return self.f.me_id

    async def sign_in_password(self, password: str) -> int:
        if password != self.f.good_password:
            from telethon.errors import PasswordHashInvalidError
            raise PasswordHashInvalidError(request=None)
        return self.f.me_id

    def session_string(self) -> str:
        return SESSION_PLAIN

    async def list_groups(self):
        if self.f.list_error:
            raise self.f.list_error
        return list(self.f.groups)

    async def send_message(self, chat_id: int, text: str) -> int:
        self.f.send_calls += 1
        err = self.f.send_errors.get(chat_id) or self.f.send_error
        if err is not None:
            raise err
        self.f.sent.append((chat_id, text))
        return len(self.f.sent)

    def on_group_message(self, handler) -> None:
        self.handlers.append(handler)

    async def push(self, msg) -> None:
        for h in self.handlers:
            await h(msg)

    async def log_out(self):
        if self.f.logout_error:
            raise self.f.logout_error
        self.logged_out = True
        self.f.logged_out_sessions.append(self.session)


class FakeFactory:
    def __init__(self) -> None:
        self.clients: list[FakeClient] = []
        self.sent: list[tuple[int, str]] = []
        self.send_calls = 0
        self.code_requests: list[str] = []
        self.logged_out_sessions: list[str | None] = []
        self.authorized = True
        self.send_error: Exception | None = None
        self.send_errors: dict[int, Exception] = {}
        self.send_code_error: Exception | None = None
        self.code_error: Exception | None = None
        self.list_error: Exception | None = None
        self.logout_error: Exception | None = None
        self.needs_password = False
        self.good_code = "12345"
        self.good_password = "hunter2-2FA"
        self.me_id = 777_001
        self.groups = [GroupInfo(-1001, "Samarqand taksi"), GroupInfo(-1002, "Toshkent yo'nalish"),
                       GroupInfo(-1003, "Buxoro")]

    def __call__(self, session: str | None) -> FakeClient:
        c = FakeClient(self, session)
        self.clients.append(c)
        return c


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send(self, tg_id: int, text: str) -> None:
        self.messages.append((tg_id, text))




async def make_driver(s, settings, *, plan: Plan | None = None, tg_id: int | None = None, lang: str | None = None,
                      subscribed: bool = True):
    tg_id = tg_id or next(_ids)
    u = await users.get_or_create_user(s, tg_id, username=None, first_name="Haydovchi")
    u.phone = "+998901234567"
    u.lang = lang
    d = await drivers.register_driver(s, u, settings, car_make="Cobalt", car_color="oq",
                                      car_plate=f"30A{next(_ids) % 1000:03d}BC")
    if plan:
        d.plan = plan
        d.subscription_until = utcnow() + timedelta(days=30 if subscribed else -2)
    await s.commit()
    return d


async def make_account(s, settings, driver, *, groups: int = 2, status: str = UserbotStatus.CONNECTED,
                       consent: bool = True, with_template: bool = True, enabled: bool = True,
                       interval: int | None = None, risk: bool = False):
    acc = UserbotAccount(driver_id=driver.id, status=status, session_encrypted=crypto.encrypt_session(settings, SESSION_PLAIN),
                         tg_user_id=777_001, consent_at=utcnow() if consent else None,
                         consent_version=2 if consent else 1,
                         min_interval_minutes=settings.userbot_min_interval_minutes if interval is None else interval,
                         jitter_minutes=settings.userbot_jitter_minutes, risk_acknowledged=risk)
    if with_template:
        acc.post_template = template.dumps(template.make_template("Samarqand", "Toshkent", "08:00", 3, 120000))
    acc.groups = [UserbotGroup(chat_id=-1001 - i, title=f"Guruh {i + 1}", enabled=enabled) for i in range(groups)]
    s.add(acc)
    await s.commit()
    return acc
