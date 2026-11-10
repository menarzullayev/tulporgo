"""Record the custom_emoji_id of every emoji in the two dedicated packs (created 2026-11-11 via @Stickers from Saidakbar
aka's account): tulporgo_icons (14 interface icons) and tulporgo_reactions (24 tulpor heads). Read-only Bot API calls
(getStickerSet); the result goes to brand/icons/pack_ids.json, which content/i18n/emoji_system.py uses.

    python brand/icons/pack_ids.py           # fetch, check the order and the emoji, write pack_ids.json
Refuses to write when a pack has a different size or order than the files it was built from.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
OUT = os.path.join(HERE, "pack_ids.json")
ICONS = ("taxi", "driver", "check", "pin", "shield", "chat", "question", "megaphone", "card", "star", "clock",
         "n1", "n2", "n3")                                   # upload order on 2026-11-11
ICON_EMOJI = {"taxi": "🚕", "driver": "🤝", "check": "✅", "pin": "📍", "shield": "🛡", "chat": "💬", "question": "❓",
              "megaphone": "📢", "card": "💳", "star": "⭐", "clock": "🕐", "n1": "1", "n2": "2", "n3": "3"}
HEADS = [l.strip() for l in open(os.path.join(ROOT, "brand", "mascot", "poses", "vector", "head_set.txt"),
                                 encoding="utf-8") if l.strip() and not l.startswith("#")]


def norm(e: str) -> str:
    return (e or "").replace("️", "").replace("⃣", "")


def get_set(token: str, name: str) -> list[dict]:
    url = f"https://api.telegram.org/bot{token}/getStickerSet?name={name}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)["result"]["stickers"]


def build(icons: list[dict], heads: list[dict]) -> dict:
    if len(icons) != len(ICONS) or len(heads) != len(HEADS):
        raise SystemExit(f"unexpected pack size: icons {len(icons)}/{len(ICONS)}, heads {len(heads)}/{len(HEADS)}")
    for name, st in zip(ICONS, icons):
        if norm(st["emoji"]) != norm(ICON_EMOJI[name]):
            raise SystemExit(f"icon order mismatch at {name}: pack has {st['emoji']}")
    return {"icons": {n: s["custom_emoji_id"] for n, s in zip(ICONS, icons)},
            "reactions": {n: s["custom_emoji_id"] for n, s in zip(HEADS, heads)},
            "packs": {"icons": "https://t.me/addemoji/tulporgo_icons",
                      "reactions": "https://t.me/addemoji/tulporgo_reactions"}}


def main() -> int:
    env = dict(l.strip().split("=", 1) for l in open(os.path.join(ROOT, ".secrets", "bot.env")) if "=" in l)
    token = env["TULPORGO_BOT_TOKEN"]
    data = build(get_set(token, "tulporgo_icons"), get_set(token, "tulporgo_reactions"))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"pack_ids.json: {len(data['icons'])} icons, {len(data['reactions'])} heads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
