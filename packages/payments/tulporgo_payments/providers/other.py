"""Documented stub for a future third-party gateway (e.g. Uzum, Paynet, Octo).

Adding a real gateway:
1. Copy this class, set `name` (must fit Payment.provider, <= 16 chars) and read its credentials from
   `tulporgo_core.config.Settings` (add fields there, additively).
2. `configured()` returns True only when the credentials exist, so an unfinished gateway never shows in /obuna.
3. `start(payment)` builds the checkout (usually a URL) from `payment.id` and `payment.amount` — the amount always
   comes from the stored Payment, never from the client.
4. `verify(payload)` checks the gateway's signature/auth for its callback; add a callback route to `api.py` that
   verifies, finds the Payment by id, checks amount and status, then calls `service.confirm()` (idempotent).
5. Register the class in `providers/__init__.py` and add `pay.provider.<name>` texts.
"""
from tulporgo_core.errors import Invalid
from tulporgo_core.models import Payment

from .base import GatewayProvider


class OtherGateway(GatewayProvider):
    name = "other"

    def configured(self) -> bool:
        return False                                       # stub: never offered to users

    async def start(self, payment: Payment, *, recurring: bool = False, **texts: str) -> dict:
        raise Invalid("provider_unavailable", "no third-party gateway is connected")

    async def verify(self, payload: dict) -> bool:
        return False                                       # a stub trusts nothing
