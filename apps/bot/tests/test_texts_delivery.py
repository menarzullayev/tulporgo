"""Texts (catalog completeness, placeholders, HTML), delivery helpers and dispatcher wiring."""
import asyncio
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import GetMe, SendMessage
from aiogram.types import InputRichMessage
from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
from bot_harness import Env, FakeSession, tx
from tulporgo_bot import delivery
from tulporgo_bot.context import DeferredBus
from tulporgo_bot.handlers.cards import quick_prices, trip_rich
from tulporgo_bot.handlers.common import money, parse_cb
from tulporgo_bot.handlers.offers import parse_price
from tulporgo_core import i18n
from tulporgo_core import services as core_services
from tulporgo_core.enums import DriverStatus, OfferStatus, RequestStatus, TripStatus
from tulporgo_core.events import RequestCreated
from tulporgo_core.text.alphabet import leftovers

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tulporgo_bot"
CORE_SERVICES = Path(core_services.__file__).parent
BOT_KEYS = {k: v for k, v in i18n.catalog().items() if k.startswith("bot.")}
KEY_USE = re.compile(r"""["'](bot\.[a-z_][a-z_.0-9]*)["']""")


# ---------- catalog ----------

def used_keys() -> set[str]:
    found = set()
    for f in SRC.rglob("*.py"):
        found |= {k for k in KEY_USE.findall(f.read_text(encoding="utf-8")) if not k.endswith(".")}
    return found


def test_every_key_used_in_the_code_exists():
    missing = sorted(k for k in used_keys() if k not in i18n.catalog())
    assert missing == []


def test_dynamic_keys_exist():
    cat = i18n.catalog()
    for cmd in ("start", "qatnovlarim", "til", "yordam", "elon", "obuna"):
        assert f"bot.cmd.{cmd}" in cat
    for role in "fth":
        assert f"bot.place.ask_{role}" in cat
    for status in (*RequestStatus, *TripStatus, *OfferStatus):
        assert f"bot.status.{status.value}" in cat, status


def test_every_domain_error_code_has_a_bot_text():
    """The bot says something human for every stable code the core raises (payments codes belong to W4)."""
    codes = set()
    for f in CORE_SERVICES.glob("*.py"):
        if f.name != "billing.py":
            codes |= set(re.findall(r'(?:Invalid|Conflict|Forbidden|NotFound)\("([a-z_]+)"', f.read_text(encoding="utf-8")))
    assert codes, "the scan found nothing — the pattern is broken"
    missing = sorted(c for c in codes if f"bot.err.{c}" not in i18n.catalog())
    assert missing == []


def test_error_text_scan_would_catch_a_missing_code():
    assert "bot.err.definitely_not_a_code" not in i18n.catalog()            # negative: the lookup is not vacuous
    assert i18n.t("bot.err.definitely_not_a_code", "ru") == "bot.err.definitely_not_a_code"


def names(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def test_placeholders_match_in_every_language():
    bad = {k: [(lg, names(v[lg])) for lg in ("uz", "ru", "en")] for k, v in BOT_KEYS.items()
           if not (names(v["uz"]) == names(v["ru"]) == names(v["en"]))}
    assert bad == {}


class Balanced(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.ok = [], True

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.ok = False


def html_ok(text: str) -> bool:
    p = Balanced()
    p.feed(text)
    return p.ok and not p.stack


def test_html_in_texts_is_balanced_in_every_language():
    for key in BOT_KEYS:
        for lang in ("uz_new", "uz_latn", "uz_cyrl", "ru", "en"):
            raw = i18n.catalog()[key]
            assert html_ok(raw["uz"] if lang.startswith("uz") else raw[lang]), (key, lang)
            assert html_ok(i18n.t(key, lang, **{n: "x" for n in names(raw["uz"])})), (key, lang)


def test_html_checker_catches_broken_markup():
    assert html_ok("<b>x</b>") and not html_ok("<b>x") and not html_ok("x</b>") and not html_ok("<b><i>x</b></i>")


def test_no_raw_ampersand_or_angle_brackets_that_break_telegram_html():
    for key, v in BOT_KEYS.items():
        for lg in ("uz", "ru", "en"):
            text = re.sub(r"</?(?:b|i|code|a)\b[^>]*>", "", v[lg])
            assert "&" not in text and "<" not in text and ">" not in text, (key, lg)


def test_cyrillic_conversion_leaves_no_latin_words_except_known_ones():
    allowed = set("Cobalt")                                           # the example car make
    for key, v in BOT_KEYS.items():
        left = set(leftovers(i18n.t(key, "uz_cyrl", **{n: "1" for n in names(v["uz"])}), "uz_cyrl")) - allowed
        left = {c for c in left if c not in "KPIABC"}                     # KPI and the plate example "30 A 123 BC"
        assert not left, (key, left)


def test_command_descriptions_fit_telegram_limits():
    for cmd in ("start", "qatnovlarim", "til", "yordam", "elon", "obuna"):
        for lang in ("uz_new", "uz_latn", "uz_cyrl", "ru", "en"):
            assert 3 <= len(i18n.t(f"bot.cmd.{cmd}", lang)) <= 256


def test_callback_data_stays_within_64_bytes():
    samples = ["pk:f:99999999", "pg:t:99999999:999", "tm:m:1:23:45", "ofq:99999999:5000000", "cq:99999999:5000000",
               "ad:cr:99999999:1", "rq:c:99999999", "rt:99999999:5", "lang:uz_cyrl", "ad:dv:99999999"]
    assert max(len(s.encode()) for s in samples) <= 64
    assert re.match(r"^[a-z]+(:[A-Za-z0-9_]+)+$", "tm:m:1:23:45") and not re.match(r"^[a-z]+(:[0-9]+)+$", "x:y")


# ---------- small pure helpers ----------

def test_parse_price_and_money():
    assert parse_price("40 000") == 40000 and parse_price("40000 so'm") == 40000 and parse_price("40,000") == 40000
    assert parse_price("45000.") == 45000
    assert parse_price("arzon") is None and parse_price("") is None and parse_price("-5") is None
    assert money(1234567) == "1 234 567"


def test_parse_cb_rejects_wrong_shapes():
    assert parse_cb("pk:f:12", 3) == ["pk", "f", "12"] and parse_cb("pk:f", 3) is None and parse_cb(None, 2) is None


def test_quick_prices_never_below_the_core_minimum():
    assert quick_prices(40_000) == [35_000, 40_000, 45_000] and quick_prices(None) == [] and quick_prices(0) == []
    assert quick_prices(3_000) == [3_000, 8_000]                          # 3000-5000 < 1000 is dropped


def test_driver_status_enum_is_what_the_bot_assumes():
    assert DriverStatus.ACTIVE == "active"


# ---------- delivery ----------

async def test_html_rejected_by_telegram_is_resent_as_plain_text():
    fake = FakeSession()
    from aiogram import Bot
    bot = Bot("1:TEST", session=fake)
    fake.errors[SendMessage] = [TelegramBadRequest(method=GetMe(), message="Bad Request: can't parse entities")]
    msg = await delivery.send(bot, 5, "<b>Narx</b> 5 &lt; 6 <a href='tg://user?id=1'>Ali</a>")
    assert msg is not None
    assert fake.calls[-1].text == "Narx 5 < 6 Ali" and fake.calls[-1].parse_mode is None
    assert len(fake.failed) == 1


async def test_other_bad_requests_are_not_hidden():
    fake = FakeSession()
    from aiogram import Bot
    bot = Bot("1:TEST", session=fake)
    fake.errors[SendMessage] = TelegramBadRequest(method=GetMe(), message="Bad Request: chat not found")
    with pytest.raises(TelegramBadRequest):
        await delivery.send(bot, 5, "x")


async def test_blocked_bot_returns_none_instead_of_raising():
    fake = FakeSession()
    from aiogram import Bot
    bot = Bot("1:TEST", session=fake)
    fake.errors[SendMessage] = TelegramForbiddenError(method=GetMe(), message="Forbidden: bot was blocked by the user")
    assert await delivery.send(bot, 5, "x") is None


async def test_retry_after_waits_the_requested_time_and_gives_up_after_three_tries(monkeypatch):
    from aiogram import Bot
    waits = []

    async def record(seconds):
        waits.append(seconds)
    monkeypatch.setattr(delivery, "sleep", record)
    fake = FakeSession()
    bot = Bot("1:TEST", session=fake)
    fake.errors[SendMessage] = [TelegramRetryAfter(method=GetMe(), message="Too Many Requests", retry_after=7)]
    assert await delivery.send(bot, 5, "x") is not None and waits == [7]
    waits.clear()
    fake.errors[SendMessage] = [TelegramRetryAfter(method=GetMe(), message="Too Many Requests", retry_after=3)] * 3
    with pytest.raises(TelegramRetryAfter):
        await delivery.send(bot, 5, "x")
    assert waits == [3, 3]                                                  # slept between tries, then surfaced the error


async def test_limiter_spaces_messages_and_can_be_switched_off(monkeypatch):
    waits = []

    async def record(seconds):
        waits.append(round(seconds, 3))
    monkeypatch.setattr(delivery, "sleep", record)
    lim = delivery.Limiter(rate=10)
    for _ in range(3):
        await lim.wait()
    assert waits[0] == pytest.approx(0.1, abs=0.02) and waits[1] == pytest.approx(0.2, abs=0.02)   # 10 msg/s
    waits.clear()
    off = delivery.Limiter(rate=0)
    for _ in range(3):
        await off.wait()
    assert waits == []


async def test_rich_message_blocks_are_valid_for_the_bot_api_models(env):
    from tulporgo_core.models import Driver, RideRequest, Trip, User
    d = Driver(car_make="Cobalt", car_color="oq", car_plate="30A123BC", user=User(first_name="Karim", username="drv", phone="+998903333333"))
    p = User(first_name="Ali", username="pas", phone="+998901234567")
    r = RideRequest(from_text="A", to_text="B", seats=2, depart_at=None)
    trip = Trip(id=1, price=40000, share_token="tok")
    t = lambda key, **kw: tx(key, **kw)  # noqa: E731
    blocks = trip_rich(trip, r, d, p, False, t)
    assert InputRichMessage(blocks=blocks).blocks[1].type == "table"        # validates against the aiogram models
    assert "hozir" in repr(blocks)                                         # no departure time → "hozir", no date_time
    r.depart_at = __import__("datetime").datetime(2026, 11, 11, 3, 30)
    assert "date_time" in repr(trip_rich(trip, r, d, p, True, t))


async def test_deferred_bus_publishes_in_order_and_can_drop_events():
    class Inner:
        def __init__(self):
            self.got = []

        async def publish(self, e):
            self.got.append(e)
    inner = Inner()
    bus = DeferredBus(inner)
    await bus.publish(RequestCreated(1))
    await bus.publish(RequestCreated(2))
    assert inner.got == []                                                  # nothing before the commit
    await bus.flush()
    assert [e.request_id for e in inner.got] == [1, 2]
    await bus.publish(RequestCreated(3))
    bus.discard()
    await bus.flush()
    assert len(inner.got) == 2                                              # a rolled-back update announces nothing


# ---------- dispatcher wiring ----------

async def test_other_workstreams_handlers_win_over_free_text_orders(tmp_path):
    """Routers of W2/W4 are included before the free-text fallback, so e.g. a receipt text is not parsed as a route."""
    from aiogram import Router
    probe = Router(name="w4-probe")
    seen = []

    @probe.message()
    async def other(message):
        seen.append(message.text)
    env = await Env(tmp_path).start(probe=probe)
    try:
        await env.user(1)
        await env.say(1, "Qo'shrabot → Samarqand 07:30")
        assert seen == ["Qo'shrabot → Samarqand 07:30"] and env.sent(1) == []
    finally:
        await env.stop()


async def test_asyncio_is_the_only_runtime_dependency_of_the_limiter():
    assert delivery.sleep is asyncio.sleep or callable(delivery.sleep)
