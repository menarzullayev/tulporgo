import pytest
from pay_helpers import make_driver, make_user
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.errors import Conflict, Forbidden, Invalid
from tulporgo_payments import service
from tulporgo_payments.providers import p2p


async def checkout(s, cfg):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "p2p", "pro", 1)
    return d, c


async def admin(s):
    return await make_user(s, is_admin=True)


async def test_start_shows_card_amount_and_unique_reference(s, cfg):
    d, c = await checkout(s, cfg)
    assert c.start["card"] == cfg.p2p_card_number and c.start["holder"] == "TEST HOLDER"
    assert c.start["amount"] == 59_000 and c.start["reference"] == f"TG{c.payment.id:06d}"
    d2 = await make_driver(s, cfg)
    c2 = await service.start_checkout(s, d2.user, cfg, "p2p", "pro", 1)
    assert c2.start["reference"] != c.start["reference"]


async def test_receipt_then_approve_extends_subscription_once(s, cfg, bus):
    d, c = await checkout(s, cfg)
    p = c.payment
    await p2p.attach_receipt(s, d.user, p, "FILE1")
    assert p.status == PaymentStatus.AWAITING_REVIEW and p.receipt_file_id == "FILE1"
    adm = await admin(s)
    before = d.subscription_until
    _, changed = await p2p.approve(s, adm, p, bus=bus)
    assert changed and p.status == PaymentStatus.PAID and p.reviewed_by_id == adm.id
    assert d.plan == "pro" and d.subscription_until > before
    until = d.subscription_until
    _, changed = await p2p.approve(s, adm, p, bus=bus)      # double approval: no-op
    assert not changed and d.subscription_until == until and len(bus.published) == 1


async def test_non_admin_cannot_approve_or_reject(s, cfg):
    d, c = await checkout(s, cfg)
    await p2p.attach_receipt(s, d.user, c.payment, "F")
    with pytest.raises(Forbidden):
        await p2p.approve(s, d.user, c.payment)               # the driver cannot approve their own payment
    with pytest.raises(Forbidden):
        await p2p.reject(s, d.user, c.payment)
    assert c.payment.status == PaymentStatus.AWAITING_REVIEW


async def test_approve_without_receipt_refused(s, cfg):
    d, c = await checkout(s, cfg)
    with pytest.raises(Conflict) as e:
        await p2p.approve(s, await admin(s), c.payment)
    assert e.value.code == "not_reviewable"


async def test_reject_closes_payment_and_blocks_later_approval(s, cfg):
    d, c = await checkout(s, cfg)
    await p2p.attach_receipt(s, d.user, c.payment, "F")
    adm = await admin(s)
    _, changed = await p2p.reject(s, adm, c.payment)
    assert changed and c.payment.status == PaymentStatus.FAILED
    _, changed = await p2p.reject(s, adm, c.payment)
    assert not changed
    with pytest.raises(Conflict):
        await p2p.approve(s, adm, c.payment)
    assert d.plan != "pro"


async def test_reject_after_paid_refused(s, cfg):
    d, c = await checkout(s, cfg)
    await p2p.attach_receipt(s, d.user, c.payment, "F")
    adm = await admin(s)
    await p2p.approve(s, adm, c.payment)
    with pytest.raises(Conflict):
        await p2p.reject(s, adm, c.payment)


async def test_receipt_rules(s, cfg):
    d, c = await checkout(s, cfg)
    stranger = await make_user(s)
    with pytest.raises(Forbidden):
        await p2p.attach_receipt(s, stranger, c.payment, "F")
    with pytest.raises(Invalid):
        await p2p.attach_receipt(s, d.user, c.payment, "")
    await p2p.attach_receipt(s, d.user, c.payment, "F")
    with pytest.raises(Conflict) as e:
        await p2p.attach_receipt(s, d.user, c.payment, "F2")
    assert e.value.code == "already_submitted"
    c.payment.status = PaymentStatus.PAID
    with pytest.raises(Conflict) as e:
        await p2p.attach_receipt(s, d.user, c.payment, "F3")
    assert e.value.code == "payment_closed"


async def test_other_provider_payment_is_not_p2p(s, cfg):
    d = await make_driver(s, cfg)
    c = await service.start_checkout(s, d.user, cfg, "click", "pro", 1)
    with pytest.raises(Invalid):
        await p2p.attach_receipt(s, d.user, c.payment, "F")
    with pytest.raises(Invalid):
        await p2p.approve(s, await admin(s), c.payment)
