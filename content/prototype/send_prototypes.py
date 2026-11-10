"""Send the 3 prototype posts (4:5, 1:1, 16:9) to the owner's private chat via @tulporgobot.

Reads TULPORGO_BOT_TOKEN from ../../.secrets/bot.env. The chat id is taken from the latest /start in getUpdates.
"""
import json, os, sys, urllib.request, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
env = dict(l.strip().split("=", 1) for l in open(os.path.join(HERE, "..", "..", ".secrets", "bot.env")) if "=" in l)
API = "https://api.telegram.org/bot" + env["TULPORGO_BOT_TOKEN"]


def call(method, fields=None, files=None):
    if files:
        b = uuid.uuid4().hex
        body = b""
        for k, v in (fields or {}).items():
            body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, path in files.items():
            body += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\n'
                     f"Content-Type: image/jpeg\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
        body += f"--{b}--\r\n".encode()
        req = urllib.request.Request(f"{API}/{method}", data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request(f"{API}/{method}", data=json.dumps(fields or {}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    if not d.get("ok"):
        raise SystemExit(f"{method} failed: {d}")
    return d["result"]


ups = [u for u in call("getUpdates") if u.get("message", {}).get("text", "").startswith("/start")]
if not ups:
    sys.exit("No /start found in getUpdates — press /start in @tulporgobot first.")
chat_id = ups[-1]["message"]["chat"]["id"]

CAPTION = ("<b>Qöşrabot — Samarqand: taksini bot orqali toping</b>\n\n"
           "Yönalişni yozing — haydovçilar taklif yuboradi.\n"
           "Narxni haydovçi bilan özingiz kelişasiz.\n"
           "Ayol yölovçilar uçun alohida belgi bor.\n\n"
           "<blockquote expandable>Напишите маршрут — водители пришлют предложения. "
           "Цену договариваетесь с водителем сами. Для женщин-пассажиров есть отдельная отметка.</blockquote>")
KB = json.dumps({"inline_keyboard": [[
    {"text": "🚕 Taksi çaqiriş", "url": "https://t.me/tulporgobot?start=taxi"},
    {"text": "Haydovçi böliş", "url": "https://t.me/tulporgobot?start=driver"}]]})

call("sendMessage", {"chat_id": chat_id, "text": "TulporGo · post prototiplari (3 ta o'lcham). Bu sinov xabarlari, tugmalar hali ishlamaydi."})
for key, label in (("4x5", "4:5 portret · 1080×1350"), ("1x1", "1:1 kvadrat · 1280×1280"), ("16x9", "16:9 gorizontal · 1280×720")):
    call("sendMessage", {"chat_id": chat_id, "text": f"▼ {label}"})
    m = call("sendPhoto", {"chat_id": chat_id, "caption": CAPTION, "parse_mode": "HTML", "reply_markup": KB},
             {"photo": os.path.join(HERE, f"sample-{key}.jpg")})
    ph = m["photo"][-1]
    print(key, "message_id", m["message_id"], "photo", f'{ph["width"]}x{ph["height"]}')
