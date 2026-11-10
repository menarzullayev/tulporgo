"""W1 replaces this placeholder with the passenger / driver / admin routers (see docs/goals/W1.md)."""
from aiogram import Router

router = Router(name="bot")


async def setup(**_) -> None:
    """Called once at start-up with bot, maker, settings, bus — subscribe to events, start schedulers."""
