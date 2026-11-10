import copy, json, pathlib

import pytest

from apply_bot_profile import apply, plan

BUILT = json.load(open(pathlib.Path(__file__).parent / "build" / "telegram_texts.json", encoding="utf-8"))


def test_language_mapping():
    w = plan(BUILT)
    assert set(w) == {"", "uz", "ru", "en"}
    assert w[""]["description"] == w["uz"]["description"] == BUILT["bot.description"]["text"]["uz_new"]
    assert w["ru"]["short_description"] == BUILT["bot.short_description"]["text"]["ru"]
    assert w[""]["name"] == "TulporGo" and "name" not in w["ru"]


def test_driver_commands_not_in_public_menu():
    cmds = [c["command"] for c in plan(BUILT)["uz"]["commands"]]
    assert cmds == ["start", "qatnovlarim", "til", "yordam"]


def test_over_limit_refused_before_any_api_call():
    # negative: a too-long short description must stop the run before Telegram is touched
    b = copy.deepcopy(BUILT)
    b["bot.short_description"]["text"]["ru"] = "x" * 121
    with pytest.raises(ValueError, match="ru.short_description"):
        plan(b)


def test_bad_command_refused():
    b = copy.deepcopy(BUILT)
    b["bot.cmd.til"]["command"] = "Til"
    with pytest.raises(ValueError, match="bad command"):
        plan(b)


def test_only_differences_are_written(tmp_path, monkeypatch):
    # negative for idempotency: fields already equal must not be re-sent
    want = plan(BUILT)
    sent = []

    def call(method, params=None, files=None):
        lang = (params or {}).get("language_code", "")
        if method == "getMyName":
            return {"name": "TulporGo"}
        if method == "getMyShortDescription":
            return {"short_description": want[lang]["short_description"]}
        if method == "getMyDescription":
            return {"description": "old"}
        if method == "getMyCommands":
            return want[lang]["commands"]
        sent.append((method, lang))
        return True

    monkeypatch.setattr("apply_bot_profile.HERE", tmp_path)
    monkeypatch.setattr("time.sleep", lambda s: None)
    _, changed = apply(call, want)
    assert sorted(changed) == ["default.description", "en.description", "ru.description", "uz.description"]
    assert {m for m, _ in sent} == {"setMyDescription"}
