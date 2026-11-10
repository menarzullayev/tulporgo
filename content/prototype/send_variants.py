"""Send rendered prototype images to the owner via @tulporgobot.

Usage: python send_variants.py "<intro text>" <png> "<label>" [<png> "<label>" ...]
Chat id comes from the latest /start in getUpdates (or the cached .secrets/owner_chat_id).
"""
import json, os, sys, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
SECRETS = os.path.join(HERE, "..", "..", ".secrets")
env = dict(l.strip().split("=", 1) for l in open(os.path.join(SECRETS, "bot.env")) if "=" in l)
API = "https://api.telegram.org/bot" + env["TULPORGO_BOT_TOKEN"]


def call(method, fields=None, files=None):
    if files:
        b = uuid.uuid4().hex
        body = b""
        for k, v in (fields or {}).items():
            body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, path in files.items():
            body += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\n'
                     "Content-Type: application/octet-stream\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
        body += f"--{b}--\r\n".encode()
        req = urllib.request.Request(f"{API}/{method}", data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request(f"{API}/{method}", data=json.dumps(fields or {}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    if not d.get("ok"):
        raise SystemExit(f"{method} failed: {d}")
    return d["result"]


def owner_chat():
    """Cached owner chat id first: since 2026-11-10 bot/coming_soon.py long-polls getUpdates all the time, and a second
    getUpdates call from here would get 409 Conflict. getUpdates is only used when there is no cache yet."""
    cache = os.path.join(SECRETS, "owner_chat_id")
    if os.path.exists(cache):
        return int(open(cache).read().strip())
    ups = [u for u in call("getUpdates") if u.get("message", {}).get("text", "").startswith("/start")]
    if ups:
        cid = ups[-1]["message"]["chat"]["id"]
        open(cache, "w").write(str(cid))
        return cid
    if os.path.exists(cache):
        return int(open(cache).read().strip())
    sys.exit("No owner chat: press /start in @tulporgobot first.")


if __name__ == "__main__":
    intro, rest = sys.argv[1], sys.argv[2:]
    if not rest or len(rest) % 2:
        sys.exit("pairs of <png> <label> required")
    cid = owner_chat()
    call("sendMessage", {"chat_id": cid, "text": intro})
    for path, label in zip(rest[::2], rest[1::2]):
        m = call("sendPhoto", {"chat_id": cid, "caption": label}, {"photo": path})
        print(os.path.basename(path), "->", m["message_id"])
