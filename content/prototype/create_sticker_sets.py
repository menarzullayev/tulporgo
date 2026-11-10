"""Create the TulporGo sticker sets owned by Saidakbar aka, via @tulporgobot (Bot API createNewStickerSet).

  tulporgo_by_<bot>        static stickers   telegram/sticker/*.webp
  tulporgo_anim_by_<bot>   video stickers    telegram/video/*.webm
  tulporgo_emoji_by_<bot>  custom emoji      telegram/emoji/*.png   (no ground shadow)

Idempotent: an existing set only gets the stickers it is missing. Creation sends at most 50 stickers,
the rest go through addStickerToSet. Prints t.me/addstickers / t.me/addemoji links.
createNewStickerSet is limited to one attempt per set per TG_CREATE_COOLDOWN_H (20 h), see attempt_guard.py.
Usage: python create_sticker_sets.py [static|video|emoji ...]
       python create_sticker_sets.py emoji-tgs [names...]   (swap emoji set to vector TGS in place)
       python create_sticker_sets.py replace static|video <names...>   (re-upload changed files in place)
"""
import json, os, sys, time, urllib.error
from send_variants import call as _call, owner_chat
import attempt_guard


def call(method, fields=None, files=None):
    """send_variants.call, but a Telegram 400 becomes SystemExit with the API description."""
    for _ in range(5):
        try:
            return _call(method, fields, files)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            wait = json.loads(body).get("parameters", {}).get("retry_after") if e.code == 429 else None
            if wait is None or wait > MAX_WAIT:  # long flood wait: stop instead of hammering the API
                raise SystemExit(f"{method} failed: {e.code} {body}")
            print(f"  {method}: 429, waiting {wait}s", flush=True)
            time.sleep(wait + 1)
    raise SystemExit(f"{method} failed: too many 429 retries")

MAX_WAIT = int(os.environ.get("TG_MAX_WAIT", "60"))   # seconds of 429 retry_after we accept
PACE = float(os.environ.get("TG_PACE", "0"))          # pause between replace calls

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, "..", "..", "brand", "mascot", "poses", "vector")
T = os.path.join(V, "telegram")
NAMES = [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]

EMOJI = {
    "01": "👋", "02": "👉", "03": "🚀", "04": "👈", "05": "📱", "06": "📲", "07": "🤝", "08": "👍", "09": "🤔",
    "10": "🗺", "11": "🧳", "12": "🧺", "13": "☔", "14": "😎", "15": "😴", "16": "🛡", "17": "🎉", "18": "👋",
    "19": "🚕", "20": "🤸", "21": "🌷", "22": "🌙", "23": "🕌", "24": "🇺🇿", "25": "🎄", "26": "⛄", "27": "🌸",
    "28": "🍂", "29": "🎒", "30": "💐", "31": "🎂", "32": "🍈", "33": "😮", "34": "😢", "35": "😳", "36": "😠",
    "37": "❤", "37t": "🙏", "38": "😂", "39": "😩", "40": "😱", "41": "🤩", "42": "🙇", "43": "🧽", "44": "⛽",
    "45": "🔧", "46": "⏳", "47": "🚪", "48": "👜", "49": "🧮", "50": "📦",
}

SETS = {
    "static": ("tulporgo", "TulporGo", "sticker", ".webp", "static", "regular"),
    "video": ("tulporgo_anim", "TulporGo — animatsiya", "video", ".webm", "video", "regular"),
    "emoji": ("tulporgo_emoji", "TulporGo emoji", "emoji", ".png", "static", "custom_emoji"),
    # head close-ups (vector TGS), only the emotion/gesture poses listed in head_set.txt
    "reactions": ("tulporgo_reactions", "TulporGo Reactions", "emoji_head_tgs", ".tgs", "animated", "custom_emoji"),
}
HEAD_NAMES = [l.strip() for l in open(os.path.join(V, "head_set.txt")) if l.strip() and not l.startswith("#")]


def emoji_for(n):
    return EMOJI[n.split("-")[1]]


def get_set(name):
    try:
        return call("getStickerSet", {"name": name})
    except SystemExit as e:
        if "STICKERSET_INVALID" in str(e) or "not found" in str(e).lower():
            return None
        raise


def make(kind, owner, bot):
    base, title, sub, ext, fmt, stype = SETS[kind]
    name = f"{base}_by_{bot}"
    names = HEAD_NAMES if kind == "reactions" else NAMES
    files = [(n, os.path.join(T, sub, n + ext)) for n in names]
    existing = get_set(name)
    have = len(existing["stickers"]) if existing else 0
    todo = files[have:]
    if not existing:
        try:
            print(name, "create attempt recorded at", attempt_guard.claim(name), flush=True)
        except attempt_guard.Refused as e:
            raise SystemExit(f"createNewStickerSet not sent: {e}")
        first, todo = todo[:50], todo[50:]
        stickers = [{"sticker": f"attach://f{i}", "format": fmt, "emoji_list": [emoji_for(n)]} for i, (n, _) in enumerate(first)]
        call("createNewStickerSet", {"user_id": owner, "name": name, "title": title, "sticker_type": stype,
                                     "stickers": json.dumps(stickers, ensure_ascii=False)},
             {f"f{i}": p for i, (_, p) in enumerate(first)})
        print(name, "created with", len(first))
    for n, p in todo:
        call("addStickerToSet", {"user_id": owner, "name": name,
                                 "sticker": json.dumps({"sticker": "attach://f0", "format": fmt, "emoji_list": [emoji_for(n)]},
                                                       ensure_ascii=False)}, {"f0": p})
    s = call("getStickerSet", {"name": name})
    link = ("https://t.me/addemoji/" if stype == "custom_emoji" else "https://t.me/addstickers/") + name
    print(name, "stickers:", len(s["stickers"]), "/", len(names), link)
    return len(s["stickers"]) == len(names), link


def replace_with_tgs(owner, bot, only=None):
    """Swap every sticker of the custom-emoji set for its vector TGS (telegram/emoji_tgs/), in place:
    replaceStickerInSet keeps the position and the set link. `only`: list of names to replace."""
    name = f"{SETS['emoji'][0]}_by_{bot}"
    s = call("getStickerSet", {"name": name})
    assert len(s["stickers"]) == len(NAMES), "set and names.txt differ"
    done = 0
    for st, n in zip(s["stickers"], NAMES):
        if only and n not in only:
            continue
        if st.get("is_animated"):
            continue                                   # already TGS (re-run safe)
        call("replaceStickerInSet", {"user_id": owner, "name": name, "old_sticker": st["file_id"],
                                     "sticker": json.dumps({"sticker": "attach://f0", "format": "animated",
                                                            "emoji_list": [emoji_for(n)]}, ensure_ascii=False)},
             {"f0": os.path.join(T, "emoji_tgs", n + ".tgs")})
        done += 1
        time.sleep(PACE)
    s = call("getStickerSet", {"name": name})
    tgs = sum(1 for x in s["stickers"] if x.get("is_animated"))
    print(name, "replaced", done, "| TGS now", tgs, "/", len(s["stickers"]))
    return tgs == len(NAMES)


def replace_files(kind, owner, bot, only):
    """Replace the stickers of `only` (pose names) in the static/video set with the current files from
    telegram/<sub>/, in place (position, emoji and set link stay). Refuses if the set's emoji order does not
    match names.txt, i.e. the position -> pose mapping can't be trusted. Returns {name: new file_unique_id}."""
    base, _, sub, ext, fmt, _ = SETS[kind]
    name = f"{base}_by_{bot}"
    s = call("getStickerSet", {"name": name})
    got = [st.get("emoji") for st in s["stickers"]]
    want = [emoji_for(n) for n in NAMES]
    if [e and e.replace("️", "") for e in got] != [e.replace("️", "") for e in want]:
        raise SystemExit(f"{name}: sticker order differs from names.txt, nothing replaced")
    unknown = [n for n in only if n not in NAMES]
    if unknown:
        raise SystemExit(f"unknown names: {unknown}")
    done = {}
    for st, n in zip(s["stickers"], NAMES):
        if n not in only:
            continue
        call("replaceStickerInSet", {"user_id": owner, "name": name, "old_sticker": st["file_id"],
                                     "sticker": json.dumps({"sticker": "attach://f0", "format": fmt,
                                                            "emoji_list": [emoji_for(n)]}, ensure_ascii=False)},
             {"f0": os.path.join(T, sub, n + ext)})
        done[n] = st["file_unique_id"]
        print(name, "replaced", n, flush=True)
        time.sleep(PACE)
    after = call("getStickerSet", {"name": name})["stickers"]
    new = {n: st["file_unique_id"] for st, n in zip(after, NAMES) if n in done}
    changed = sum(new[n] != done[n] for n in done)
    print(name, "replaced", len(done), "| file changed", changed, "| stickers", len(after), "/", len(NAMES))
    return len(after) == len(NAMES) and changed == len(only)


if __name__ == "__main__":
    owner = owner_chat()
    bot = call("getMe")["username"]
    if sys.argv[1:2] == ["replace"]:                   # replace static|video <names...>
        sys.exit(0 if replace_files(sys.argv[2], owner, bot, sys.argv[3:]) else 14)
    if sys.argv[1:2] == ["emoji-tgs"]:
        sys.exit(0 if replace_with_tgs(owner, bot, sys.argv[2:] or None) else 14)
    assert len(EMOJI) == len(NAMES) and all(n.split("-")[1] in EMOJI for n in NAMES), "emoji map incomplete"
    ok = True
    for k in sys.argv[1:] or ["static", "video", "emoji"]:
        good, _ = make(k, owner, bot)
        ok &= good
    sys.exit(0 if ok else 14)
