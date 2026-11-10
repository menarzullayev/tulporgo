"""Driver notifications from the worker go through @tulporgobot (the userbot never writes to the driver itself)."""
import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Notifier(Protocol):
    async def send(self, tg_id: int, text: str) -> None: ...


class BotNotifier:
    def __init__(self, bot) -> None:
        self.bot = bot

    async def send(self, tg_id: int, text: str) -> None:
        try:
            await self.bot.send_message(tg_id, text)
        except Exception as e:                                   # noqa: BLE001 - a failed notice must not stop posting
            log.warning("could not notify driver %s: %s", tg_id, type(e).__name__)
