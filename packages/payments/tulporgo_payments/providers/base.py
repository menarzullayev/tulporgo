"""Common base for payment gateways.

A new third-party gateway is ONE class: subclass `GatewayProvider`, set `name`, implement `configured`, `start`
and `verify`, then register it in `providers/__init__.py`. See `other.py` for a documented stub.
"""
from abc import abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from tulporgo_core.config import Settings
from tulporgo_core.models import Payment
from tulporgo_core.services.billing import PaymentProvider

TgCall = Callable[[str, dict], Awaitable[Any]]


class GatewayProvider(PaymentProvider):
    name: str = ""

    def __init__(self, settings: Settings, tg_call: TgCall | None = None) -> None:
        """`tg_call` (raw Bot API caller) is only used by Stars; other gateways ignore it."""
        self.settings = settings
        self.tg_call = tg_call

    @abstractmethod
    def configured(self) -> bool:
        """True when every credential this provider needs is present (otherwise it is hidden from the UI)."""

    @abstractmethod
    async def start(self, payment: Payment, *, recurring: bool = False, **texts: str) -> dict:
        """What the bot / Mini App shows the user: always a dict with a `type` key.

        `recurring` and `texts` (invoice captions) are meaningful for Stars only; other gateways ignore them."""

    @abstractmethod
    async def verify(self, payload: dict) -> bool:
        """Authenticity check of an inbound callback (signature / auth). Never raises; False = reject."""
