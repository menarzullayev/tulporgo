"""Crypto, template and Telethon-wrapper units."""
import os
import types

import pytest
from tulporgo_core.config import Settings
from tulporgo_core.errors import DomainError
from tulporgo_userbot import client as client_mod
from tulporgo_userbot import crypto, template
from tulporgo_userbot.client import TelethonClient, can_write, make_telethon_factory
from tulporgo_userbot.config import DEVICE_MODEL, TelegramApiSettings
from tulporgo_userbot.errors import Invalid, NotConfigured
from userbot_fixtures import *  # noqa: F403 - pytest fixtures

# ------------------------------------------------------------------ crypto


def test_session_roundtrip_and_token_is_not_plain(settings):
    token = crypto.encrypt_session(settings, "SESSION-ABC")
    assert "SESSION-ABC" not in token and crypto.decrypt_session(settings, token) == "SESSION-ABC"


def test_missing_or_invalid_key_refuses_to_encrypt():
    with pytest.raises(NotConfigured) as e1:
        crypto.encrypt_session(Settings(userbot_encryption_key=""), "x")
    assert e1.value.code == "userbot_key_missing"
    with pytest.raises(NotConfigured) as e2:
        crypto.encrypt_session(Settings(userbot_encryption_key="not-a-fernet-key"), "x")
    assert e2.value.code == "userbot_key_invalid"


def test_wrong_key_and_tampered_token_do_not_decrypt(settings):
    token = crypto.encrypt_session(settings, "SESSION-ABC")
    other = settings.model_copy(update={"userbot_encryption_key": crypto.generate_key()})
    with pytest.raises(DomainError) as e:
        crypto.decrypt_session(other, token)
    assert e.value.code == "session_unreadable" and "SESSION-ABC" not in str(e.value) and token not in str(e.value)
    with pytest.raises(DomainError):
        crypto.decrypt_session(settings, token[:-4] + "AAAA")


# ------------------------------------------------------------------ template

def test_post_text_is_built_from_i18n_with_fixed_contact_line(settings):
    tpl = template.make_template("Samarqand", "Toshkent", "08:00", 3, "120 000")
    text = template.build_post_text(tpl, "uz_latn", settings)
    assert text.splitlines()[0] == "🚕 Samarqand → Toshkent"
    assert "120 000" in text and text.splitlines()[-1].startswith("📲 @tulporgobot orqali bog")
    assert "Samarkand" not in template.build_post_text(tpl, "ru", settings) and "Свяжитесь" in template.build_post_text(
        tpl, "ru", settings)


def test_price_line_omitted_when_negotiable(settings):
    text = template.build_post_text(template.make_template("A", "B", "08:00", 2, "-"), "uz_latn", settings)
    assert "so'm" not in text


@pytest.mark.parametrize("bad", ["@spam_bot", "https://evil.example", "t.me/joinchat", "www.x", "kanal.uz", "x.com/a",
                                 "a" * 61, "", "   ", "tg://resolve"])
def test_links_mentions_and_oversize_rejected(bad):
    with pytest.raises(Invalid):
        template.make_template(bad, "Toshkent", "08:00", 3)
    with pytest.raises(Invalid):
        template.make_template("Samarqand", "Toshkent", bad, 3)


@pytest.mark.parametrize("seats", [0, 9, "x", -1])
def test_bad_seats_rejected(seats):
    with pytest.raises(Invalid):
        template.make_template("A", "B", "08:00", seats)


@pytest.mark.parametrize("price", ["abc", "0", "-5", "999999999999"])
def test_bad_price_rejected(price):
    with pytest.raises(Invalid):
        template.make_template("A", "B", "08:00", 2, price)


def test_corrupt_stored_template_is_none_and_dumps_roundtrip():
    tpl = template.make_template("A", "B", "08:00", 2, 50000)
    assert template.loads(template.dumps(tpl)) == tpl
    for raw in (None, "", "{bad", '{"from_": "x"}', '{"from_":"@x","to":"b","time":"1","seats":1}'):
        assert template.loads(raw) is None


# ------------------------------------------------------------------ can_write / Telethon wrapper

def ent(**kw):
    return types.SimpleNamespace(**kw)


def rights(send=False):
    return types.SimpleNamespace(send_messages=send)


def test_can_write_rules():
    assert can_write(ent(default_banned_rights=rights(False)))
    assert not can_write(ent(default_banned_rights=rights(True)))                      # muted group
    assert not can_write(ent(left=True))
    assert not can_write(ent(kicked=True))
    assert not can_write(ent(deactivated=True))
    assert not can_write(ent(banned_rights=rights(True), default_banned_rights=rights(False)))   # personally muted
    assert can_write(ent(default_banned_rights=rights(True), admin_rights=object()))   # admins may write
    assert can_write(ent(default_banned_rights=rights(True), creator=True))


class FakeTelethon:
    """Records construction arguments; never touches the network."""
    last = None

    def __init__(self, session, api_id, api_hash, **kw):
        FakeTelethon.last = types.SimpleNamespace(session=session, api_id=api_id, api_hash=api_hash, kw=kw)
        self.calls = []
        self.fail_times = 0

    async def send_message(self, chat_id, text, **kw):
        self.calls.append((chat_id, text, kw))
        if self.fail_times:
            self.fail_times -= 1
            raise ValueError("Could not find the input entity")
        return types.SimpleNamespace(id=99)

    async def get_dialogs(self):
        self.calls.append("dialogs")


@pytest.fixture
def fake_telethon(monkeypatch):
    import telethon
    monkeypatch.setattr(telethon, "TelegramClient", FakeTelethon)
    return FakeTelethon


def valid_session_string() -> str:
    from telethon.crypto import AuthKey
    from telethon.sessions import StringSession
    ss = StringSession()
    ss.set_dc(2, "149.154.167.51", 443)
    ss.auth_key = AuthKey(os.urandom(256))
    return ss.save()


def test_real_client_never_sleeps_through_flood_waits(fake_telethon):
    sess = valid_session_string()
    TelethonClient(sess, 1, "hash")
    kw = fake_telethon.last.kw
    assert kw["flood_sleep_threshold"] == 0                     # FloodWaitError must always reach the scheduler
    assert kw["device_model"] == DEVICE_MODEL == "TulporGo (driver)"
    assert fake_telethon.last.session.save() == sess             # StringSession carries the decrypted session


async def test_send_primes_entity_cache_once_without_markup(fake_telethon):
    c = TelethonClient(None, 1, "h")
    c._client.fail_times = 1
    assert await c.send_message(-1001, "salom") == 99
    assert c._client.calls[1] == "dialogs" and c._client.calls[0][2]["parse_mode"] is None   # plain text only


async def test_send_does_not_loop_when_entity_stays_unknown(fake_telethon):
    c = TelethonClient(None, 1, "h")
    c._client.fail_times = 5
    with pytest.raises(ValueError):
        await c.send_message(-1, "x")
    assert [x for x in c._client.calls if x != "dialogs"].__len__() == 2      # one try + one retry, never more


def test_factory_requires_api_credentials(fake_telethon):
    with pytest.raises(NotConfigured):
        make_telethon_factory(TelegramApiSettings(telegram_api_id=0, telegram_api_hash=""))
    f = make_telethon_factory(TelegramApiSettings(telegram_api_id=5, telegram_api_hash="h"))
    assert isinstance(f(None), TelethonClient) and fake_telethon.last.api_id == 5
    assert client_mod.GroupInfo(1, "t").chat_id == 1


@pytest.mark.parametrize("lang", ["uz_latn", "ru", "en"])
def test_consent_text_has_the_eight_points_in_order(lang):
    from tulporgo_core.i18n import t
    text = t("userbot.risk", lang, min=45)
    pos = [text.find(f"{n}. ") for n in range(1, 9)]
    assert all(p >= 0 for p in pos) and pos == sorted(pos)
    assert "FloodWait" in text and "PEER_FLOOD" in text and "TulporGo (driver)" in text and "45" in text
    assert "9. " not in text and "{min}" not in text
