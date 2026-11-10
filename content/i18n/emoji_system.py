"""Decision 39: the TulporGo emoji system. Texts keep standard emoji as placeholders; this maps each one to its role.

  interface (buttons, 1-2-3, lists) -> TulporGo icons            (brand/icons, concept v1)
  emotion   (greeting)              -> tulpor head emoji          (Reactions)
  accent    (max 1 per message)     -> Telegram official animated emoji (RestrictedEmoji "Animated Emoji")
Ids: icons + head are the test entries in tulporgo_emoji (brand/icons/test_ids.json) until the dedicated
tulporgo_icons / tulporgo_reactions packs exist; accents are resolved from RestrictedEmoji and cached.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
TEST_IDS = os.path.join(ROOT, "brand", "icons", "test_ids.json")
ACCENT_CACHE = os.path.join(HERE, "build", "accent_ids.json")

INTERFACE = {"🚕": "taxi", "🤝": "driver", "💬": "chat", "✅": "check", "🛡": "shield", "1️⃣": "n1", "2️⃣": "n2",
             "3️⃣": "n3", "📢": "megaphone", "📣": "megaphone", "❓": "question", "💳": "card", "📍": "pin",
             "⭐": "star", "🕐": "clock"}
EMOTION = {"👋": "head-01"}
ACCENT = ("🚀", "🎉", "⏳", "🔥")
MAX_ACCENTS = 1


def norm(e):
    return (e or "").replace("️", "")


def accents_in(text):
    """Accent emoji occurrences in a text (each counts; repeated accents count every time)."""
    t = norm(text)
    return [a for a in ACCENT for _ in range(t.count(norm(a)))]


def resolve_accents(call):
    """Look the accents up in Telegram's official animated emoji set once; cache the ids."""
    if os.path.exists(ACCENT_CACHE):
        return json.load(open(ACCENT_CACHE, encoding="utf-8"))
    st = call("getStickerSet", {"name": "RestrictedEmoji"})["stickers"]
    ids = {}
    for a in ACCENT:
        hit = next((s for s in st if norm(s.get("emoji")) == norm(a)), None)
        if hit:
            ids[a] = hit["custom_emoji_id"]
    os.makedirs(os.path.dirname(ACCENT_CACHE), exist_ok=True)
    json.dump(ids, open(ACCENT_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return ids


def build_map(call):
    """{standard emoji: custom_emoji_id} for every role that has an id today."""
    test = json.load(open(TEST_IDS, encoding="utf-8"))
    m = {std: test[name]["custom_emoji_id"] for std, name in {**INTERFACE, **EMOTION}.items() if name in test}
    m.update(resolve_accents(call))
    return m
