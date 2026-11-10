"""Bot flows through a real aiogram Dispatcher with a fake Bot session (no network): /obuna, checkout screens,
Stars invoices, P2P receipt + admin review, notifications and reminders."""
import asyncio
import importlib
import itertools
from datetime import date, datetime, timedelta

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    AnswerPreCheckoutQuery,
    CreateInvoiceLink,
    EditMessageCaption,
    EditMessageText,
    SendDocument,
    SendInvoice,
    SendMessage,
    SendPhoto,
)
from aiogram.types import (
    BotSubscriptionUpdated,
    CallbackQuery,
    Chat,
    Message,
    PhotoSize,
    PreCheckoutQuery,
    SuccessfulPayment,
    Update,
)
from aiogram.types import User as TgUser
from pay_helpers import make_driver, make_settings
from sqlalchemy import select
from tulporgo_bot.main import OPTIONAL_ROUTERS, build_dispatcher
from tulporgo_core.db import Base, make_engine, make_sessionmaker, utcnow
from tulporgo_core.enums import PaymentStatus
from tulporgo_core.events import InMemoryBus, PaymentConfirmed
from tulporgo_core.models import Driver, Payment, User
from tulporgo_payments import bot as paybot
from tulporgo_payments import jobs

ADMIN = 900
_n = itertools.count(1)


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def close(self): ...

    async def stream_content(self, *a, **k):
        raise NotImplementedError

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        self.calls.append(method)
        if isinstance(method, (SendMessage, SendInvoice, SendPhoto, SendDocument)):
            return Message(message_id=next(_n), date=datetime.now(), chat=Chat(id=method.chat_id, type="private"))
        if isinstance(method, CreateInvoiceLink):
            return "https://t.me/$fake-sub-link"
        return True


class Env:
    def __init__(self, maker, cfg, bus, bot, dp, session):
        self.maker, self.cfg, self.bus, self.bot, self.dp, self.session = maker, cfg, bus, bot, dp, session

    @property
    def calls(self):
        return self.session.calls

    def of(self, cls, chat_id=None):
        return [c for c in self.calls if isinstance(c, cls) and (chat_id is None or getattr(c, "chat_id", None) == chat_id)]

    def texts(self, chat_id):
        out = []
        for c in self.calls:
            if getattr(c, "chat_id", None) == chat_id:
                out.append(getattr(c, "text", None) or getattr(c, "caption", None) or "")
        return out

    def last_alert(self):
        a = self.of(AnswerCallbackQuery)
        return (a[-1].text, a[-1].show_alert) if a else None

    async def feed(self, **update_fields):
        await self.dp.feed_update(self.bot, Update(update_id=next(_n), **update_fields))

    def tg(self, uid):
        return TgUser(id=uid, is_bot=False, first_name="Ali", language_code="en")

    async def say(self, uid, text=None, **kw):
        m = Message(message_id=next(_n), date=datetime.now(), chat=Chat(id=uid, type="private"), text=text,
                    from_user=self.tg(uid), **kw)
        await self.feed(message=m)

    async def press(self, uid, data):
        m = Message(message_id=next(_n), date=datetime.now(), chat=Chat(id=uid, type="private"), text="x",
                    from_user=TgUser(id=1, is_bot=True, first_name="bot"))
        await self.feed(callback_query=CallbackQuery(id=str(next(_n)), from_user=self.tg(uid), chat_instance="ci",
                                                     data=data, message=m))

    async def seed_driver(self, **kw):
        async with self.maker() as s:
            d = await make_driver(s, self.cfg, lang="en", **kw)
            tg = d.user.tg_id
            await s.commit()
        return tg

    async def payments(self):
        async with self.maker() as s:
            return (await s.execute(select(Payment).order_by(Payment.id))).scalars().all()

    async def driver(self, tg):
        async with self.maker() as s:
            u = (await s.execute(select(User).where(User.tg_id == tg))).scalar_one()
            return (await s.execute(select(Driver).where(Driver.user_id == u.id))).scalar_one()


def detach_routers():
    """A module-level Router attaches to one Dispatcher; detach so every test (and other packages' tests) can build
    its own."""
    for spec in OPTIONAL_ROUTERS:
        mod, attr = spec.split(":")
        try:
            getattr(importlib.import_module(mod), attr)._parent_router = None
        except ModuleNotFoundError:
            pass


async def make_env(tmp_path, **cfg_kw):
    eng = make_engine(f"sqlite+aiosqlite:///{(tmp_path / 'bot.db').as_posix()}")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    maker = make_sessionmaker(eng)
    cfg = make_settings(**cfg_kw)
    bus = InMemoryBus()
    session = FakeSession()
    bot = Bot("123456:TEST", session=session)
    detach_routers()
    dp = build_dispatcher(cfg, maker, bus)
    paybot.STATE["maker"] = maker
    return Env(maker, cfg, bus, bot, dp, session), eng


@pytest.fixture
async def env(tmp_path):
    e, eng = await make_env(tmp_path)
    yield e
    detach_routers()
    await eng.dispose()


@pytest.fixture
async def free_env(tmp_path):
    e, eng = await make_env(tmp_path, free_period_until=date.today() + timedelta(days=20))
    yield e
    detach_routers()
    await eng.dispose()


def buttons(call):
    kb = call.reply_markup
    return [b for row in kb.inline_keyboard for b in row] if kb else []


# ------------------------------------------------------------------ /obuna

async def test_obuna_for_non_driver(env):
    await env.say(77, "/obuna")
    out = env.of(SendMessage, 77)
    assert len(out) == 1 and "driver" in out[0].text.lower() and out[0].reply_markup is None


async def test_obuna_lists_plans_with_decision_10_prices(env):
    tg = await env.seed_driver()
    await env.say(tg, "/obuna")
    m = env.of(SendMessage, tg)[0]
    labels = [b.text for b in buttons(m)]
    assert any("29 000" in x for x in labels) and any("59 000" in x for x in labels) and any("99 000" in x for x in labels)
    assert [b.callback_data for b in buttons(m)] == ["pay:pl:basic", "pay:pl:pro", "pay:pl:business"]
    assert "auto-posting, up to 15 groups" in m.text and "unlimited groups, priority" in m.text


async def test_obuna_during_free_period_says_free_and_offers_nothing(free_env):
    env = free_env
    tg = await env.seed_driver()
    await env.say(tg, "/obuna")
    m = env.of(SendMessage, tg)[0]
    assert "free" in m.text.lower() and env.cfg.free_period_until.strftime("%d.%m.%Y") in m.text
    assert m.reply_markup is None                          # nothing to pay


async def test_checkout_screens_blocked_during_free_period(free_env):
    env = free_env
    tg = await env.seed_driver()
    for data in ("pay:pl:pro", "pay:mo:pro:1", "pay:go:pro:1:click", "pay:home"):
        await env.press(tg, data)
        text, alert = env.last_alert()
        assert alert and "free" in text.lower()
    assert await env.payments() == []


async def test_obuna_shows_active_subscription_and_still_offers_renewal(env):
    tg = await env.seed_driver()
    async with env.maker() as s:
        d = (await s.execute(select(Driver))).scalar_one()
        d.plan, d.subscription_until = "pro", utcnow() + timedelta(days=20)
        await s.commit()
    await env.say(tg, "/obuna")
    m = env.of(SendMessage, tg)[0]
    assert "Subscription active" in m.text and "Pro" in m.text and len(buttons(m)) == 3


async def test_plan_to_months_to_providers_navigation(env):
    tg = await env.seed_driver()
    await env.press(tg, "pay:pl:pro")
    e = env.of(EditMessageText)[-1]
    assert [b.callback_data for b in buttons(e)][:4] == [f"pay:mo:pro:{m}" for m in (1, 3, 6, 12)]
    assert "708 000" in buttons(e)[3].text                  # 12 x 59 000, no discount
    await env.press(tg, "pay:mo:pro:3")
    e = env.of(EditMessageText)[-1]
    assert [b.callback_data for b in buttons(e)][:4] == [f"pay:go:pro:3:{p}" for p in ("p2p", "stars", "click", "payme")]


async def test_unconfigured_providers_not_offered(tmp_path):
    e, eng = await make_env(tmp_path, click_secret_key="", payme_key="", p2p_card_number="")
    tg = await e.seed_driver()
    await e.press(tg, "pay:mo:pro:1")
    assert [b.callback_data for b in buttons(e.of(EditMessageText)[-1])][:1] == ["pay:go:pro:1:stars"]
    await e.press(tg, "pay:go:pro:1:click")                 # forged callback for a hidden provider
    assert e.last_alert()[1] is True and await e.payments() == []
    detach_routers()
    await eng.dispose()


async def test_forged_callbacks_are_harmless(env):
    tg = await env.seed_driver()
    for data in ("pay:pl:gold", "pay:mo:pro:7", "pay:mo:pro:x", "pay:go:pro:5:click", "pay:go:pro", "pay:go:pro:1:nope",
                 "pay:rc:abc", "pay:rc:99999"):
        await env.press(tg, data)
    assert await env.payments() == []


async def test_non_driver_cannot_open_checkout(env):
    await env.press(77, "pay:pl:pro")
    assert env.last_alert()[1] is True and await env.payments() == []


# ------------------------------------------------------------------ Click / Payme buttons

@pytest.mark.parametrize("provider,host", [("click", "my.click.uz"), ("payme", "test.paycom.uz")])
async def test_url_providers_show_pay_button(env, provider, host):
    tg = await env.seed_driver()
    await env.press(tg, f"pay:go:business:6:{provider}")
    e = env.of(EditMessageText)[-1]
    url_btn = buttons(e)[0]
    assert host in url_btn.url and "594 000" in e.text
    (p,) = await env.payments()
    assert p.amount == 594_000 and p.provider == provider and p.status == PaymentStatus.PENDING


# ------------------------------------------------------------------ P2P

async def p2p_start(env):
    tg = await env.seed_driver()
    await env.press(tg, "pay:go:pro:1:p2p")
    return tg


async def test_p2p_instructions_show_card_amount_reference(env):
    await p2p_start(env)
    text = env.of(EditMessageText)[-1].text
    assert "8600 0000 0000 0000" in text and "TEST HOLDER" in text and "59 000" in text
    (p,) = await env.payments()
    assert f"TG{p.id:06d}" in text


async def test_p2p_receipt_goes_to_admins_with_styled_buttons(env):
    tg = await p2p_start(env)
    await env.say(tg, photo=[PhotoSize(file_id="PH1", file_unique_id="u1", width=10, height=10)])
    (p,) = await env.payments()
    assert p.status == PaymentStatus.AWAITING_REVIEW and p.receipt_file_id == "PH1"
    (photo,) = env.of(SendPhoto, ADMIN)
    assert photo.photo == "PH1" and f"#{p.id}" in photo.caption
    b = buttons(photo)
    assert [(x.callback_data, x.style) for x in b] == [(f"pay:ok:{p.id}", "success"), (f"pay:no:{p.id}", "danger")]
    assert any("Receipt received" in t for t in env.texts(tg))


async def test_p2p_text_instead_of_photo_is_asked_again(env):
    tg = await p2p_start(env)
    await env.say(tg, "mana pul o'tkazdim")
    assert any("photo" in t.lower() for t in env.texts(tg))
    assert (await env.payments())[0].status == PaymentStatus.PENDING


async def test_admin_approves_driver_notified_once(env):
    tg = await p2p_start(env)
    await env.say(tg, photo=[PhotoSize(file_id="PH1", file_unique_id="u1", width=1, height=1)])
    (p,) = await env.payments()
    await env.press(ADMIN, f"pay:ok:{p.id}")
    (p,) = await env.payments()
    assert p.status == PaymentStatus.PAID
    assert (await env.driver(tg)).plan == "pro"
    success = [t for t in env.texts(tg) if "Payment received" in t]
    assert len(success) == 1 and "Pro" in success[0]
    assert any(isinstance(c, (EditMessageText, EditMessageCaption)) for c in env.calls)
    until = (await env.driver(tg)).subscription_until
    await env.press(ADMIN, f"pay:ok:{p.id}")                # double approval: no-op, no second notification
    assert (await env.driver(tg)).subscription_until == until
    assert len([t for t in env.texts(tg) if "Payment received" in t]) == 1
    assert env.last_alert()[1] is True
    assert len([e for e in env.bus.published if isinstance(e, PaymentConfirmed)]) == 1


async def test_non_admin_cannot_approve(env):
    tg = await p2p_start(env)
    await env.say(tg, photo=[PhotoSize(file_id="PH1", file_unique_id="u1", width=1, height=1)])
    (p,) = await env.payments()
    await env.press(tg, f"pay:ok:{p.id}")                   # the driver tries to approve their own payment
    assert env.last_alert() == ("Admins only.", True)
    assert (await env.payments())[0].status == PaymentStatus.AWAITING_REVIEW
    other = await env.seed_driver()
    await env.press(other, f"pay:no:{p.id}")
    assert (await env.payments())[0].status == PaymentStatus.AWAITING_REVIEW


async def test_admin_rejects_driver_told(env):
    tg = await p2p_start(env)
    await env.say(tg, photo=[PhotoSize(file_id="PH1", file_unique_id="u1", width=1, height=1)])
    (p,) = await env.payments()
    await env.press(ADMIN, f"pay:no:{p.id}")
    assert (await env.payments())[0].status == PaymentStatus.FAILED
    assert any("not confirmed" in t for t in env.texts(tg))
    await env.press(ADMIN, f"pay:ok:{p.id}")                # approving a rejected payment is refused
    assert (await env.payments())[0].status == PaymentStatus.FAILED and (await env.driver(tg)).plan != "pro"


async def test_admin_cannot_approve_payment_without_receipt(env):
    await p2p_start(env)
    (p,) = await env.payments()
    await env.press(ADMIN, f"pay:ok:{p.id}")
    assert (await env.payments())[0].status == PaymentStatus.PENDING and env.last_alert()[1] is True


async def test_receipt_button_for_someone_elses_payment_refused(env):
    await p2p_start(env)
    (p,) = await env.payments()
    other = await env.seed_driver()
    await env.press(other, f"pay:rc:{p.id}")
    assert env.last_alert()[1] is True
    await env.say(other, photo=[PhotoSize(file_id="X", file_unique_id="x", width=1, height=1)])
    assert (await env.payments())[0].receipt_file_id is None


# ------------------------------------------------------------------ Stars

async def stars_start(env):
    tg = await env.seed_driver()
    await env.press(tg, "pay:go:pro:1:stars")
    (p,) = await env.payments()
    return tg, p


async def test_stars_sends_xtr_invoice_and_recurring_link(env):
    tg, p = await stars_start(env)
    (inv,) = env.of(SendInvoice, tg)
    assert inv.currency == "XTR" and inv.prices[0].amount == p.amount == round(59_000 / 165)
    assert inv.payload == f"pay:{p.id}" and not inv.provider_token
    (link,) = env.of(CreateInvoiceLink)
    assert link.subscription_period == 2_592_000 and link.currency == "XTR"
    rec_msg = env.of(SendMessage, tg)[-1]
    assert buttons(rec_msg)[0].url == "https://t.me/$fake-sub-link"


async def test_stars_multi_month_has_no_recurring_link(env):
    tg = await env.seed_driver()
    await env.press(tg, "pay:go:pro:3:stars")
    assert env.of(SendInvoice, tg) and env.of(CreateInvoiceLink) == []


async def pre_checkout(env, tg, payload, amount, currency="XTR"):
    await env.feed(pre_checkout_query=PreCheckoutQuery(id="q1", from_user=env.tg(tg), currency=currency,
                                                       total_amount=amount, invoice_payload=payload))
    return env.of(AnswerPreCheckoutQuery)[-1]


async def test_pre_checkout_ok_and_every_refusal(env):
    tg, p = await stars_start(env)
    assert (await pre_checkout(env, tg, f"pay:{p.id}", p.amount)).ok is True
    bad = await pre_checkout(env, tg, f"pay:{p.id}", p.amount + 1)
    assert bad.ok is False and bad.error_message
    assert (await pre_checkout(env, tg, "pay:424242", p.amount)).ok is False
    assert (await pre_checkout(env, tg, f"pay:{p.id}", p.amount, currency="UZS")).ok is False
    other = await env.seed_driver()
    assert (await pre_checkout(env, other, f"pay:{p.id}", p.amount)).ok is False


def success_msg(env, tg, p, amount=None, charge="CHG1", **kw):
    sp = SuccessfulPayment(currency="XTR", total_amount=p.amount if amount is None else amount,
                           invoice_payload=f"pay:{p.id}", telegram_payment_charge_id=charge,
                           provider_payment_charge_id="", **kw)
    return Message(message_id=next(_n), date=datetime.now(), chat=Chat(id=tg, type="private"),
                   from_user=env.tg(tg), successful_payment=sp)


async def test_successful_payment_activates_and_notifies_once_even_if_replayed(env):
    tg, p = await stars_start(env)
    await env.feed(message=success_msg(env, tg, p))
    (p2,) = await env.payments()
    assert p2.status == PaymentStatus.PAID and p2.external_id == "CHG1" and (await env.driver(tg)).plan == "pro"
    assert len([t for t in env.texts(tg) if "Payment received" in t]) == 1
    until = (await env.driver(tg)).subscription_until
    await env.feed(message=success_msg(env, tg, p))          # Telegram re-delivers the same update
    assert (await env.driver(tg)).subscription_until == until
    assert len([t for t in env.texts(tg) if "Payment received" in t]) == 1


async def test_successful_payment_with_wrong_amount_is_not_paid_and_admin_alerted(env):
    tg, p = await stars_start(env)
    await env.feed(message=success_msg(env, tg, p, amount=p.amount - 5))
    assert (await env.payments())[0].status == PaymentStatus.PENDING and (await env.driver(tg)).plan != "pro"
    assert any("manual check" in t for t in env.texts(ADMIN))
    assert not any("Payment received" in t for t in env.texts(tg))


async def test_stars_recurring_renewal_extends_again(env):
    tg, p = await stars_start(env)
    await env.feed(message=success_msg(env, tg, p, is_recurring=True, is_first_recurring=True))
    first = (await env.driver(tg)).subscription_until
    await env.feed(message=success_msg(env, tg, p, charge="CHG2", is_recurring=True))
    assert (await env.driver(tg)).subscription_until > first
    assert len(await env.payments()) == 2


async def test_bot_subscription_updated_tells_the_user(env):
    tg, p = await stars_start(env)
    ev = lambda state, payload=None: BotSubscriptionUpdated(user=env.tg(tg), invoice_payload=payload or f"pay:{p.id}",  # noqa: E731
                                                            state=state)
    await env.feed(subscription=ev("canceled"))
    assert any("cancelled" in t for t in env.texts(tg))
    await env.feed(subscription=ev("failed"))
    assert any("payment failed" in t for t in env.texts(tg))
    n = len(env.texts(tg))
    await env.feed(subscription=ev("canceled", "pay:999999"))   # unknown payload: silent
    await env.feed(subscription=ev("exploded"))                 # unknown state: silent
    assert len(env.texts(tg)) == n
    assert (await env.payments())[0].payload["stars_subscription"] == "failed"


async def test_bot_subscription_updated_for_another_users_payment_is_ignored(env):
    tg, p = await stars_start(env)
    other = await env.seed_driver()
    await env.feed(subscription=BotSubscriptionUpdated(user=env.tg(other), invoice_payload=f"pay:{p.id}",
                                                       state="canceled"))
    assert env.texts(other) == [] or not any("cancel" in t for t in env.texts(other))


# ------------------------------------------------------------------ jobs

async def test_reminder_sent_three_days_before_expiry_only_once(env):
    near = await env.seed_driver()
    far = await env.seed_driver()
    now = utcnow()
    async with env.maker() as s:
        ds = (await s.execute(select(Driver).order_by(Driver.id))).scalars().all()
        ds[0].subscription_until = now + timedelta(days=2, hours=20)
        ds[1].subscription_until = now + timedelta(days=10)
        await s.commit()
    sent: set = set()
    assert await jobs.run_reminders(env.bot, env.maker, env.cfg, now=now, sent=sent) == 1
    assert any("ends on" in t for t in env.texts(near)) and env.texts(far) == []
    assert await jobs.run_reminders(env.bot, env.maker, env.cfg, now=now, sent=sent) == 0   # no spam
    m = env.of(SendMessage, near)[-1]
    assert buttons(m)[0].callback_data == "pay:home"


async def test_no_reminder_during_free_period_or_for_expired(free_env):
    env = free_env
    await env.seed_driver()
    async with env.maker() as s:
        d = (await s.execute(select(Driver))).scalar_one()
        d.subscription_until = utcnow() + timedelta(days=1)
        await s.commit()
    assert await jobs.run_reminders(env.bot, env.maker, env.cfg, sent=set()) == 0


async def test_no_reminder_for_already_expired(env):
    await env.seed_driver()
    async with env.maker() as s:
        d = (await s.execute(select(Driver))).scalar_one()
        d.subscription_until = utcnow() - timedelta(days=1)
        await s.commit()
    assert await jobs.run_reminders(env.bot, env.maker, env.cfg, sent=set()) == 0


async def test_setup_jobs_notifies_driver_for_payments_confirmed_elsewhere(env):
    tg = await env.seed_driver()
    async with env.maker() as s:
        u = (await s.execute(select(User).where(User.tg_id == tg))).scalar_one()
        p = Payment(user_id=u.id, provider="click", plan="pro", months=1, amount=59_000)
        s.add(p)
        await s.commit()
        pid = p.id
    handle = jobs.setup_jobs(env.bot, env.maker, env.cfg, bus=env.bus)
    await handle                                            # usable with or without await
    await asyncio.sleep(0.05)                               # let the first reminder pass finish
    async with env.maker() as s:                            # simulate the API process confirming the payment
        from tulporgo_payments import service
        pay = await s.get(Payment, pid)
        await service.confirm(s, pay, bus=env.bus, external_id="c1")
        await s.commit()
    for _ in range(40):
        await asyncio.sleep(0.05)
        if any("Payment received" in t for t in env.texts(tg)):
            break
    handle.cancel()
    assert len([t for t in env.texts(tg) if "Payment received" in t]) == 1
    await asyncio.gather(*paybot.PENDING, return_exceptions=True)
    assert len([t for t in env.texts(tg) if "Payment received" in t]) == 1   # notified flag prevents repeats
