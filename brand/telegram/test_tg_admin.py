import json, pathlib

import pytest
from telethon import types

import tg_admin

I18N = pathlib.Path(__file__).resolve().parents[2] / "content" / "i18n" / "build"
TEXTS = json.load(open(I18N / "telegram_texts.json", encoding="utf-8"))
EMOJI = json.load(open(I18N / "emoji_map.json", encoding="utf-8"))


def test_welcome_payloads_carry_approved_text_emoji_and_collapsed_russian():
    p = tg_admin.welcome_payloads(TEXTS, EMOJI)
    assert set(p) == {"channel", "chat", "drivers"}
    msg, ents, photo = p["channel"]
    assert msg.startswith("Xuş kelibsiz!") and photo and photo.exists()
    assert any(isinstance(e, types.MessageEntityCustomEmoji) for e in ents)
    assert any(isinstance(e, types.MessageEntityBlockquote) and e.collapsed for e in ents)
    assert len(msg) <= 1024                                         # photo caption limit
    assert "Guruh qoidalari" in p["chat"][0] and p["chat"][2] is None


def test_no_raw_html_leaks_into_text():
    # negative: an unparsed tag would show up as literal text in the chat
    for msg, _, _ in tg_admin.welcome_payloads(TEXTS, EMOJI).values():
        assert "<" not in msg and "tg-emoji" not in msg and "&lt;" not in msg


def test_bot_rights_never_include_dangerous_rights():
    # negative: the bot must not be able to add admins or change chat info
    for r in tg_admin.RIGHTS.values():
        assert not r.get("add_admins") and not r.get("change_info") and r.get("manage_welcome_messages")


def test_secrets_never_printed(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(tg_admin, "ENV", tmp_path / ".env")
    tg_admin.write_env(tg_admin.ENV, {"TELEGRAM_API_HASH": "SECRET123", "TELEGRAM_SESSION_STRING": "1AbCdEf"})
    assert tg_admin.read_env(tg_admin.ENV)["TELEGRAM_API_HASH"] == "SECRET123"
    out = capsys.readouterr().out
    assert "SECRET123" not in out and "1AbCdEf" not in out


def test_flood_wait_stops_with_exit_3(capsys):
    class E:
        seconds = 600
    with pytest.raises(SystemExit) as ex:
        tg_admin.stop_on_flood(E())
    assert ex.value.code == 3 and "600" in capsys.readouterr().out
