import pytest
from pay_helpers import make_driver, make_settings, make_user
from tulporgo_core.enums import PaymentStatus, Plan
from tulporgo_core.errors import Conflict, Forbidden, Invalid
from tulporgo_core.services import billing
from tulporgo_payments import service
from tulporgo_payments.providers import PROVIDERS, available_providers, get_provider
from tulporgo_payments.providers.base import GatewayProvider


async def test_checkout_amount_comes_from_decision_10_prices(s, cfg):
    d = await make_driver(s, cfg)
    for plan, price in ((Plan.BASIC, 29_000), (Plan.PRO, 59_000), (Plan.BUSINESS, 99_000)):
        c = await service.start_checkout(s, d.user, cfg, "click", plan, 1)
        assert c.payment.amount == price
    c = await service.start_checkout(s, d.user, cfg, "payme", "pro", 12)
    assert c.payment.amount == 59_000 * 12                   # no invented discount


@pytest.mark.parametrize("months", [0, 2, 5, 13, -1])
async def test_bad_months_rejected(s, cfg, months):
    d = await make_driver(s, cfg)
    with pytest.raises(Invalid):
        await service.start_checkout(s, d.user, cfg, "click", "pro", months)


async def test_bad_plan_and_unknown_provider_rejected(s, cfg):
    d = await make_driver(s, cfg)
    with pytest.raises(Invalid) as e:
        await service.start_checkout(s, d.user, cfg, "click", "platinum", 1)
    assert e.value.code == "bad_plan"
    with pytest.raises(Invalid) as e:
        await service.start_checkout(s, d.user, cfg, "bitcoin", "pro", 1)
    assert e.value.code == "provider_unavailable"


async def test_free_period_refuses_checkout(s, free_cfg):
    d = await make_driver(s, free_cfg)
    with pytest.raises(Conflict) as e:
        await service.start_checkout(s, d.user, free_cfg, "p2p", "pro", 1)
    assert e.value.code == "free_period"


async def test_non_driver_and_blocked_refused(s, cfg):
    u = await make_user(s)
    with pytest.raises(Forbidden) as e:
        await service.start_checkout(s, u, cfg, "p2p", "pro", 1)
    assert e.value.code == "driver_required"
    d = await make_driver(s, cfg)
    d.user.is_blocked = True
    with pytest.raises(Forbidden):
        await service.start_checkout(s, d.user, cfg, "p2p", "pro", 1)


async def test_unconfigured_provider_refused_and_hidden(s):
    cfg = make_settings(click_secret_key="", payme_key="", p2p_card_number="")
    d = await make_driver(s, cfg)
    for name in ("click", "payme", "p2p", "other"):
        with pytest.raises(Invalid):
            await service.start_checkout(s, d.user, cfg, name, "pro", 1)
    assert available_providers(cfg) == ["stars"]


async def test_pending_payment_is_reused_not_duplicated(s, cfg):
    d = await make_driver(s, cfg)
    a = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    b = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    assert a.payment.id == b.payment.id
    c = await service.start_checkout(s, d.user, cfg, "click", "pro", 3)
    assert c.payment.id != a.payment.id


async def test_confirm_is_idempotent_and_extends_once(s, cfg, bus):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    await service.confirm(s, c.payment, bus=bus, external_id="x1")
    until = d.subscription_until
    await service.confirm(s, c.payment, bus=bus, external_id="x1")
    assert d.subscription_until == until and c.payment.status == PaymentStatus.PAID
    assert len(bus.published) == 1


async def test_confirm_cancelled_payment_raises(s, cfg):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    c.payment.status = PaymentStatus.CANCELLED
    with pytest.raises(Conflict):
        await service.confirm(s, c.payment)


def test_registry_contains_every_provider_and_stub_is_inert(cfg):
    assert set(PROVIDERS) == {"p2p", "stars", "click", "payme", "other"}
    assert all(issubclass(c, GatewayProvider) for c in PROVIDERS.values())
    assert get_provider("nope", cfg) is None
    other = get_provider("other", cfg)
    assert other.configured() is False


async def test_stub_provider_start_and_verify_refuse(s, cfg):
    d = await make_driver(s, cfg)
    p = await billing.create_payment(s, d.user, "other", Plan.PRO, 1)
    other = get_provider("other", cfg)
    with pytest.raises(Invalid):
        await other.start(p)
    assert await other.verify({"anything": 1}) is False
