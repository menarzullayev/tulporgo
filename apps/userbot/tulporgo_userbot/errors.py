"""Userbot domain errors (stable `code`, mapped to JSON by the API and to texts by the bot)."""
from tulporgo_core.errors import DomainError, Forbidden, Invalid, NotFound

__all__ = ["DomainError", "Forbidden", "Invalid", "NotFound", "NotConfigured", "TooMany"]


class NotConfigured(DomainError):
    status = 503


class TooMany(DomainError):
    status = 429
