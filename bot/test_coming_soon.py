import json, pathlib

from coming_soon import Responder, lang_of, reply_payload

B = pathlib.Path(__file__).resolve().parents[1] / "content" / "i18n" / "build"
TEXTS = json.load(open(B / "telegram_texts.json", encoding="utf-8"))
EMOJI = json.load(open(B / "emoji_map.json", encoding="utf-8"))
T0 = 1_800_000_000


def msg(chat_type="private", date=T0 + 10, lang="uz", text="/start", cid=42):
    return {"update_id": 1, "message": {"date": date, "text": text, "chat": {"id": cid, "type": chat_type},
                                         "from": {"id": cid, "language_code": lang}}}


def test_start_gets_approved_text_button_and_emoji():
    (method, p), = Responder(TEXTS, EMOJI, T0).actions(msg(), T0 + 10)
    assert method == "sendMessage" and p["chat_id"] == 42
    assert p["text"].startswith("TulporGo tez orada işga tuşadi")
    assert '<tg-emoji emoji-id="' in p["text"]                                   # 🚀 accent (decision 39)
    btn = p["reply_markup"]["inline_keyboard"][0][0]
    assert btn["url"] == "https://t.me/tulporgo" and btn["text"] == "Kanalga ötiş" and btn.get("icon_custom_emoji_id")


def test_language_choice():
    assert lang_of({"language_code": "ru"}) == "ru" and lang_of({"language_code": "en-US"}) == "en"
    assert lang_of({"language_code": "uz"}) == "uz_new" and lang_of({}) == "uz_new" and lang_of({"language_code": "tr"}) == "uz_new"
    (_, p), = Responder(TEXTS, EMOJI, T0).actions(msg(lang="ru"), T0 + 10)
    assert p["text"].startswith("TulporGo скоро запустится")


def test_groups_and_channels_ignored():
    # negative: the bot is admin in the group/channel — it must never post the stub there
    r = Responder(TEXTS, EMOJI, T0)
    assert r.actions(msg("supergroup"), T0 + 10) == [] and r.actions(msg("channel"), T0 + 10) == []


def test_cooldown_stops_reply_loops():
    # negative: a user typing fast gets one reply per minute, not one per message
    r = Responder(TEXTS, EMOJI, T0, cooldown=60)
    assert len(r.actions(msg(), T0 + 10)) == 1
    assert r.actions(msg(), T0 + 30) == []
    assert len(r.actions(msg(), T0 + 75)) == 1
    assert len(r.actions(msg(cid=43), T0 + 31)) == 1                              # other users unaffected


def test_backlog_before_start_is_skipped():
    # negative: old pending updates (e.g. yesterday's /start) must not be answered on first run
    assert Responder(TEXTS, EMOJI, T0).actions(msg(date=T0 - 3600), T0 + 10) == []


def test_old_preview_buttons_get_answered():
    (method, p), = Responder(TEXTS, EMOJI, T0).actions({"update_id": 2, "callback_query": {"id": "q1"}}, T0)
    assert method == "answerCallbackQuery" and p["callback_query_id"] == "q1"


def test_lock_refuses_second_instance_and_frees_after_crash(tmp_path):
    # negative: a second instance must be refused while the first holds the lock; after the holder dies
    # (simulated crash / power cut: process killed, lock file left behind) a new instance must start
    import subprocess, sys, time
    from coming_soon import single_instance
    lock = tmp_path / "x.lock"
    holder = subprocess.Popen([sys.executable, "-c", (
        "import sys, time; sys.path.insert(0, r'%s'); from coming_soon import single_instance;"
        "h = single_instance(r'%s'); print('held' if h else 'no', flush=True); time.sleep(30)")
        % (pathlib.Path(__file__).parent, lock)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        assert single_instance(lock) is None
    finally:
        holder.kill()
        holder.wait()
    time.sleep(0.5)
    assert lock.exists()                                   # stale file stays...
    h = single_instance(lock)
    assert h is not None                                   # ...but does not block a new start
    h.close()


def test_no_pid_signalling_in_source():
    # negative: os.kill(pid, 0) kills the process on Windows — it must never come back
    src = (pathlib.Path(__file__).parent / "coming_soon.py").read_text(encoding="utf-8")
    assert "os.kill(" not in src and "execv" not in src


def test_payload_escapes_html():
    t = json.loads(json.dumps(TEXTS))
    t["bot.coming_soon"]["text"]["en"] = "a <b> & c"
    p = reply_payload(1, "en", t, {})
    assert p["text"] == "a &lt;b&gt; &amp; c"
