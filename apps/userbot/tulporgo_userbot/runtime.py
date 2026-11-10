"""Process-wide runtime objects shared by the API router and the bot router: the Telethon client factory and the
pending-login registry. Tests install a fake factory with `set_factory()` — no real login ever happens."""
from .client import ClientFactory, make_telethon_factory
from .login import LoginRegistry

_factory: ClientFactory | None = None
_logins: LoginRegistry | None = None


def set_factory(factory: ClientFactory | None) -> None:
    global _factory, _logins
    _factory, _logins = factory, None


def get_factory() -> ClientFactory:
    global _factory
    if _factory is None:
        _factory = make_telethon_factory()                       # raises NotConfigured without API id/hash
    return _factory


def logins() -> LoginRegistry:
    global _logins
    if _logins is None:
        _logins = LoginRegistry(get_factory())
    return _logins


async def cancel_login(key: int) -> None:
    """Drop a half-finished login if there is one; never needs the Telegram credentials."""
    if _logins is not None:
        await _logins.cancel(key)
