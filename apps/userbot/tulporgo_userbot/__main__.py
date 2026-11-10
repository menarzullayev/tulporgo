import asyncio
import contextlib

from .worker import run

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(run())
