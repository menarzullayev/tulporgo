"""HTTP API for the Mini App and payment callbacks: `uvicorn tulporgo_api.main:app`. Workstream W3 (+ W2/W4 routers)."""
import importlib
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from tulporgo_core.config import Settings, get_settings
from tulporgo_core.db import make_engine, make_sessionmaker
from tulporgo_core.errors import DomainError
from tulporgo_core.events import InMemoryBus, RedisBus

log = logging.getLogger(__name__)
OPTIONAL_ROUTERS = ["tulporgo_api.routes:router", "tulporgo_api.legal:router", "tulporgo_userbot.api:router",
                    "tulporgo_payments.api:router"]


def create_app(settings: Settings | None = None, maker=None, bus=None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="TulporGo API", version="0.1.0")
    app.state.settings = settings
    app.state.maker = maker or make_sessionmaker(make_engine(settings.database_url))
    if bus is None:
        if settings.redis_url:
            import redis.asyncio as redis
            bus = RedisBus(redis.from_url(settings.redis_url))
        else:
            bus = InMemoryBus()
    app.state.bus = bus

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, e: DomainError):
        return JSONResponse({"error": e.code, "detail": str(e)}, status_code=e.status)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    for spec in OPTIONAL_ROUTERS:
        mod_name, attr = spec.split(":")
        try:
            app.include_router(getattr(importlib.import_module(mod_name), attr))
        except ModuleNotFoundError as e:
            if e.name and mod_name.startswith(e.name):
                log.info("router %s not available yet", spec)
            else:
                raise
    return app


def __getattr__(name: str):
    if name == "app":                                    # lazy: importing the module must not need env settings
        return create_app()
    raise AttributeError(name)
