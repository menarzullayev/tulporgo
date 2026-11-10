"""Common base for payment gateways.

A new third-party gateway is ONE class: subclass `GatewayProvider`, set `name`, implement `configured`, `start`
and `verify`, then register it in `providers/__init__.py`. See `other.py` for a documented stub.
"""
from abc import abstractmethod

from tulporgo_core.config import Settings
from tulporgo_core.models import Payment
from tulporgo_core.services.billing import PaymentProvider


class GatewayProvider(PaymentProvider):
    name: str = ""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def configured(self) -> bool:
        """True when every credential this provider needs is present (otherwise it is hidden from the UI)."""

    @abstractmethod
    async def start(self, payment: Payment) -> dict:
        """What the bot / Mini App shows the user: always a dict with a `type` key."""

    @abstractmethod
    async def verify(self, payload: dict) -> bool:
        """Authenticity check of an inbound callback (signature / auth). Never raises; False = reject."""
