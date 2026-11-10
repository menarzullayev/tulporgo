"""deploy/.env.example is what a fresh server starts from (`cp .env.example .env`): every settings class must accept it.
Found by a deploy rehearsal on a clean clone: empty `KEY=` lines made int/date settings fail and `migrate` exit 1."""
from datetime import date
from pathlib import Path

import pytest
from tulporgo_bot.config import BotExtra
from tulporgo_core.config import Settings
from tulporgo_userbot.config import TelegramApiSettings

EXAMPLE = Path(__file__).resolve().parents[2] / "deploy" / ".env.example"
CLASSES = (Settings, BotExtra, TelegramApiSettings)


def _env_lines() -> dict[str, str]:
    out = {}
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


@pytest.fixture
def example_env(monkeypatch):
    for k, v in _env_lines().items():
        monkeypatch.setenv(k, v)


def test_example_has_empty_values_on_purpose():
    empties = [k for k, v in _env_lines().items() if v == ""]
    assert "TULPORGO_OWNER_CHAT_ID" in empties and "TULPORGO_FREE_PERIOD_UNTIL" in empties


@pytest.mark.parametrize("cls", CLASSES, ids=lambda c: c.__name__)
def test_every_settings_class_accepts_the_example(example_env, cls):
    cls(_env_file=None)                                   # must not raise


def test_empty_means_default_not_empty_string(example_env):
    s = Settings(_env_file=None)
    assert s.owner_chat_id is None and s.storage_chat_id is None and s.free_period_until is None
    assert s.trial_days == 7 and s.payme_test_mode is True
    assert TelegramApiSettings(_env_file=None).telegram_api_id == 0
    assert BotExtra(_env_file=None).drivers_group_id is None


def test_real_values_still_parse(monkeypatch):
    monkeypatch.setenv("TULPORGO_OWNER_CHAT_ID", "123")
    monkeypatch.setenv("TULPORGO_FREE_PERIOD_UNTIL", "2027-01-31")
    s = Settings(_env_file=None)
    assert s.owner_chat_id == 123 and s.free_period_until == date(2027, 1, 31)


def test_garbage_is_still_rejected(monkeypatch):
    # negative: ignoring EMPTY values must not hide a wrong value
    monkeypatch.setenv("TULPORGO_OWNER_CHAT_ID", "not-a-number")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
