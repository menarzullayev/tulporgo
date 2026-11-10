# ruff: noqa: F401, F811  (fixtures are imported explicitly, see pay_fixtures.py)
import pytest
from pay_fixtures import bus, cfg, engine, free_cfg, maker, s
from pay_helpers import make_driver, make_user
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.errors import Forbidden, Invalid
from tulporgo_core.models import Payment
from tulporgo_payments import service
from tulporgo_payments.providers import get_provider, stars


async def checkout(s, cfg, months=1, plan="pro"):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "stars", plan, months)
    return d, c


def paid_kwargs(p, **kw):
    return dict(invoice_payload=f"pay:{p.id}", currency="XTR", total_amount=p.amount, charge_id="CH-1", **kw)


async def test_amount_is_stars_converted_from_decision_10_price(s, cfg):
    d, c = await checkout(s, cfg)
    assert c.payment.currency == "XTR" and c.payment.amount == round(59_000 / 165)
    p = c.start["invoice"]
    assert p["currency"] == "XTR" and p["prices"] == [{"label": "Subscription", "amount": c.payment.amount}]
    assert p["provider_token"] == "" and p["payload"] == f"pay:{c.payment.id}" and "subscription_period" not in p


async def test_recurring_link_uses_30_day_period(s, cfg):
    d = await make_driver(s, cfg)
    calls = []

    async def fake(method, params):
        calls.append((method, params))
        return "https://t.me/$fakelink"
    c = await service.start_checkout(s, d.user, cfg, "stars", "pro", 1, recurring=True, tg_call=fake)
    assert c.start["invoice_link"] == "https://t.me/$fakelink" and c.start["recurring"] is True
    assert calls[0][0] == "createInvoiceLink" and calls[0][1]["subscription_period"] == 2_592_000


async def test_recurring_only_for_one_month_and_cap(s, cfg):
    d, c = await checkout(s, cfg, months=3)
    with pytest.raises(Invalid) as e:
        get_provider("stars", cfg).invoice_params(c.payment, recurring=True)
    assert e.value.code == "recurring_one_month_only"
    d2, c2 = await checkout(s, cfg)
    c2.payment.amount = 10_001
    with pytest.raises(Invalid):
        get_provider("stars", cfg).invoice_params(c2.payment, recurring=True)


async def test_pre_checkout_accepts_matching_payment(s, cfg):
    d, c = await checkout(s, cfg)
    p = c.payment
    assert await stars.validate_pre_checkout(s, d.user, f"pay:{p.id}", "XTR", p.amount) is None


async def test_pre_checkout_rejects_every_mismatch(s, cfg):
    d, c = await checkout(s, cfg)
    p, other = c.payment, await make_user(s)
    check = stars.validate_pre_checkout
    assert await check(s, d.user, f"pay:{p.id}", "XTR", p.amount + 1) == "amount_mismatch"
    assert await check(s, d.user, f"pay:{p.id}", "XTR", p.amount - 1) == "amount_mismatch"
    assert await check(s, d.user, f"pay:{p.id}", "UZS", p.amount) == "amount_mismatch"
    assert await check(s, d.user, "pay:99999", "XTR", p.amount) == "unknown_payment"
    assert await check(s, d.user, "garbage", "XTR", p.amount) == "bad_payload"
    assert await check(s, other, f"pay:{p.id}", "XTR", p.amount) == "wrong_user"
    p.status = PaymentStatus.PAID
    assert await check(s, d.user, f"pay:{p.id}", "XTR", p.amount) == "not_pending"


async def test_pre_checkout_rejects_other_provider_payment(s, cfg):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    assert await stars.validate_pre_checkout(s, d.user, f"pay:{c.payment.id}", "XTR", c.payment.amount) \
        == "wrong_provider"


async def test_successful_payment_marks_paid_with_charge_id(s, cfg, bus):
    d, c = await checkout(s, cfg)
    p, new = await stars.process_successful_payment(s, d.user, bus=bus, **paid_kwargs(c.payment))
    assert new and p.status == PaymentStatus.PAID and p.external_id == "CH-1"
    assert d.plan == "pro" and d.subscription_until is not None


async def test_successful_payment_amount_mismatch_does_not_pay(s, cfg):
    d, c = await checkout(s, cfg)
    kw = paid_kwargs(c.payment)
    kw["total_amount"] -= 1
    with pytest.raises(Invalid) as e:
        await stars.process_successful_payment(s, d.user, **kw)
    assert e.value.code == "amount_mismatch" and c.payment.status == PaymentStatus.PENDING


async def test_successful_payment_wrong_user_and_bad_payload(s, cfg):
    d, c = await checkout(s, cfg)
    with pytest.raises(Forbidden):
        await stars.process_successful_payment(s, await make_user(s), **paid_kwargs(c.payment))
    with pytest.raises(Invalid):
        await stars.process_successful_payment(s, d.user, **{**paid_kwargs(c.payment), "invoice_payload": "x"})
    with pytest.raises(Invalid):
        await stars.process_successful_payment(s, d.user, **{**paid_kwargs(c.payment), "charge_id": ""})


async def test_replayed_charge_is_a_noop(s, cfg, bus):
    d, c = await checkout(s, cfg)
    await stars.process_successful_payment(s, d.user, bus=bus, **paid_kwargs(c.payment))
    until = d.subscription_until
    p, new = await stars.process_successful_payment(s, d.user, bus=bus, **paid_kwargs(c.payment))
    assert not new and d.subscription_until == until and len(bus.published) == 1


async def test_second_charge_for_a_paid_one_off_invoice_does_not_extend(s, cfg):
    d, c = await checkout(s, cfg)
    await stars.process_successful_payment(s, d.user, **paid_kwargs(c.payment))
    until = d.subscription_until
    _, new = await stars.process_successful_payment(s, d.user, **{**paid_kwargs(c.payment), "charge_id": "CH-2"})
    assert not new and d.subscription_until == until


async def test_recurring_renewal_creates_new_payment_and_extends(s, cfg):
    from sqlalchemy import select
    d, c = await checkout(s, cfg)
    await stars.process_successful_payment(s, d.user, **paid_kwargs(c.payment, is_recurring=True,
                                                                    is_first_recurring=True))
    first_until = d.subscription_until
    renewal, new = await stars.process_successful_payment(
        s, d.user, **{**paid_kwargs(c.payment, is_recurring=True), "charge_id": "CH-2"})
    assert new and renewal.id != c.payment.id and renewal.status == PaymentStatus.PAID
    assert d.subscription_until > first_until
    assert len((await s.execute(select(Payment))).scalars().all()) == 2


async def test_subscription_state_recorded_and_unknown_ignored(s, cfg):
    d, c = await checkout(s, cfg)
    p = await stars.record_subscription_state(s, f"pay:{c.payment.id}", "canceled")
    assert p.payload["stars_subscription"] == "canceled"
    assert await stars.record_subscription_state(s, f"pay:{c.payment.id}", "weird") is None
    assert await stars.record_subscription_state(s, "pay:424242", "active") is None
    assert await stars.record_subscription_state(s, "nonsense", "active") is None


async def test_verify_checks_shape(cfg):
    gw = get_provider("stars", cfg)
    assert await gw.verify({"currency": "XTR", "invoice_payload": "pay:5"})
    assert not await gw.verify({"currency": "UZS", "invoice_payload": "pay:5"})
    assert not await gw.verify({"currency": "XTR", "invoice_payload": "evil"})
