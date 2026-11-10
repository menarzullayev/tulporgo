"""Provider registry: one class per gateway (see base.GatewayProvider and other.py)."""
from tulporgo_core.config import Settings

from .base import GatewayProvider
from .click import ClickProvider
from .other import OtherGateway
from .p2p import P2PProvider
from .payme import PaymeProvider
from .stars import StarsProvider

PROVIDERS: dict[str, type[GatewayProvider]] = {
    "p2p": P2PProvider, "stars": StarsProvider, "click": ClickProvider, "payme": PaymeProvider,
    "other": OtherGateway,
}


def get_provider(name: str, settings: Settings, tg_call=None) -> GatewayProvider | None:
    cls = PROVIDERS.get(name)
    if cls is None:
        return None
    return cls(settings, tg_call=tg_call) if cls is StarsProvider else cls(settings)


def available_providers(settings: Settings) -> list[str]:
    """Names of providers that are fully configured, in display order."""
    return [n for n in PROVIDERS if (p := get_provider(n, settings)) is not None and p.configured()]


__all__ = ["PROVIDERS", "GatewayProvider", "available_providers", "get_provider"]
