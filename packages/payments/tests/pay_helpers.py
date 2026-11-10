"""Shared helpers for payment tests (imported by name; conftest.py names collide across packages)."""
import itertools

from tulporgo_core.config import Settings
from tulporgo_core.enums import Plan
from tulporgo_core.services import billing, drivers, users

_ids = itertools.count(5000)
CLICK_SECRET = "click-test-secret"
PAYME_KEY = "payme-test-key"


def make_settings(**kw) -> Settings:
    base = dict(database_url="sqlite+aiosqlite:///:memory:", bot_token="123456:TEST", admin_ids=[900],
                free_period_until=None, p2p_card_number="8600 0000 0000 0000", p2p_card_holder="TEST HOLDER",
                click_service_id="1001", click_merchant_id="2002", click_secret_key=CLICK_SECRET,
                payme_merchant_id="merchant-test", payme_key=PAYME_KEY, payme_test_mode=True, stars_rate_uzs=165)
    base.update(kw)
    return Settings(**base)


async def make_user(s, **kw):
    u = await users.get_or_create_user(s, next(_ids), username=kw.pop("username", None), first_name="Test")
    for k, v in kw.items():
        setattr(u, k, v)
    await s.flush()
    return u


async def make_driver(s, settings, **kw):
    u = await make_user(s, phone="+998901234567", **kw)
    d = await drivers.register_driver(s, u, settings, car_make="Cobalt", car_color="oq",
                                      car_plate=f"30A{next(_ids) % 1000:03d}BC")
    await s.flush()
    return d


async def make_payment(s, user, provider, plan=Plan.PRO, months=1, settings=None):
    cur = "XTR" if provider == "stars" else "UZS"
    return await billing.create_payment(s, user, provider, plan, months, currency=cur, settings=settings)
