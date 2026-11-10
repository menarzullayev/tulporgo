"""@tulporgobot «tez orada» stub — stage 3 of TELEGRAM-REJA.md, approved by Saidakbar aka 2026-11-10 ("Ha, qo'y").

Until the real bot (aiogram, decision 17) exists, answers /start (any deep link) and any private message with the
approved bot.coming_soon text (decision 40) in the user's language (ru / en, everyone else Uzbek new alphabet),
decision-39 emoji (TulporGo icon on the button, one animated accent) and a «Kanalga o'tish» button to @tulporgo.
  - private chats only; groups and channels are ignored
  - at most one reply per chat per COOLDOWN seconds (no spam loops)
  - updates older than the start of the process are skipped (no replies to a backlog)
  - single instance (lock file), long polling, back-off on network errors, honours 429 retry_after
  - stores no message text; the log has counts and errors only
Usage: pythonw coming_soon.py   (autostart: Task Scheduler "TulporGo coming-soon bot", see install_autostart.ps1)
"""
import html, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEXTS = ROOT / "content" / "i18n" / "build" / "telegram_texts.json"
EMOJI = ROOT / "content" / "i18n" / "build" / "emoji_map.json"
SECRETS = ROOT / ".secrets"
LOCK = HERE / "coming_soon.lock"
LOG = HERE / "coming_soon.log"
COOLDOWN = 60
LANG = {"ru": "ru", "en": "en"}


def lang_of(user):
    return LANG.get((user or {}).get("language_code", "")[:2], "uz_new")


def deco(h, emoji):
    for std in sorted(emoji, key=len, reverse=True):
        for form in {std, std.replace("️", ""), std + "️"}:
            if form and not form.isascii() and form in h:
                h = h.replace(form, f'<tg-emoji emoji-id="{emoji[std]}">{std}</tg-emoji>')
    return h


def reply_payload(chat_id, lang, texts, emoji):
    item = texts["bot.coming_soon"]
    text = deco(html.escape(item["text"][lang], quote=False), emoji)
    btn = item["buttons"][0]
    b = {"text": btn["labels"][lang], "url": btn["url"]}
    if emoji.get(btn.get("fallback")):
        b["icon_custom_emoji_id"] = emoji[btn["fallback"]]
    return {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[b]]}}


class Responder:
    """Pure decision logic (tested without network)."""

    def __init__(self, texts, emoji, started_at, cooldown=COOLDOWN):
        self.texts, self.emoji, self.started_at, self.cooldown = texts, emoji, started_at, cooldown
        self.last = {}

    def actions(self, update, now):
        """-> list of (method, params)."""
        if "callback_query" in update:
            q = update["callback_query"]
            return [("answerCallbackQuery", {"callback_query_id": q["id"], "text": "TulporGo tez orada ishga tushadi"})]
        m = update.get("message")
        if not m or m.get("chat", {}).get("type") != "private" or m.get("date", 0) < self.started_at:
            return []
        cid = m["chat"]["id"]
        if now - self.last.get(cid, -1e9) < self.cooldown:
            return []
        self.last[cid] = now
        return [("sendMessage", reply_payload(cid, lang_of(m.get("from")), self.texts, self.emoji))]


# ---------- network ----------
def api(token):
    base = f"https://api.telegram.org/bot{token}"

    def call(method, params=None, timeout=70):
        req = urllib.request.Request(f"{base}/{method}", data=json.dumps(params or {}).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            return json.loads(e.read().decode("utf-8", "replace") or "{}")
    return call


def log(line):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")


def single_instance(path=LOCK):
    """OS-level exclusive lock held for the life of the process; the OS drops it when the process dies, even on a
    power cut, so a leftover lock file is harmless. Returns the open handle (keep it) or None if another instance
    holds it. Never looks at PIDs: on Windows "signal 0" via os.kill TERMINATES that pid (2026-11-10 incident check)."""
    f = open(path, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def main():
    lock = single_instance()
    if lock is None:
        sys.exit("already running")
    token = dict(l.strip().split("=", 1) for l in open(SECRETS / "bot.env") if "=" in l)["TULPORGO_BOT_TOKEN"]
    call = api(token)
    texts = json.load(open(TEXTS, encoding="utf-8"))
    emoji = json.load(open(EMOJI, encoding="utf-8"))
    r = Responder(texts, emoji, started_at=int(time.time()) - 5)
    offset, delay, replies = None, 2, 0
    log("start")
    while True:                                           # network errors are retried here, never by re-exec
        try:
            res = call("getUpdates", {"timeout": 50, **({"offset": offset} if offset else {}),
                                      "allowed_updates": ["message", "callback_query"]})
            if not res.get("ok"):
                wait = (res.get("parameters") or {}).get("retry_after") or delay
                log(f"getUpdates error {res.get('error_code')}: {res.get('description')} — sleep {wait}s")
                time.sleep(wait)
                delay = min(delay * 2, 300)
                continue
            delay = 2
            for u in res["result"]:
                offset = u["update_id"] + 1
                for method, params in r.actions(u, time.time()):
                    out = call(method, params, timeout=30)
                    if not out.get("ok"):
                        log(f"{method} failed {out.get('error_code')}: {out.get('description')}")
                    elif method == "sendMessage":
                        replies += 1
                        if replies % 50 == 1:
                            log(f"replies so far: {replies}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            log(f"network: {type(e).__name__} — retry in {delay}s")
            time.sleep(delay)
            delay = min(delay * 2, 300)


if __name__ == "__main__":
    main()
