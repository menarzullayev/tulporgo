"""Mini App HTTP API (workstream W3): everything under /api except health and the W2/W4 routers.

Auth is `Authorization: tma <initData>` (see `tulporgo_api.deps.current_user`); only `/api/share/{token}` is public.
"""
from fastapi import APIRouter

from . import driver, me, places, requests, share, trips

router = APIRouter(prefix="/api")
for _m in (me, places, requests, trips, share, driver):
    router.include_router(_m.router)

__all__ = ["router"]
