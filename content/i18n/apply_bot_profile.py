"""Stage 3 (TELEGRAM-REJA.md): set @tulporgobot's public profile from the approved texts (decision 40) and avatar
(decision 31/41). Approved by Saidakbar aka 2026-11-10 ("Ha, o'rnat").

  language_code ""  (default, everyone without a dedicated text) -> uz_new  (decision 40: profile Uzbek = new alphabet)
                "uz" -> uz_new,  "ru" -> ru,  "en" -> en
Sets: name (default only), short description, description, passenger commands (drivers' /elon /obuna wait for the bot
code), avatar (brand/telegram/out/bot.jpg, JPG as InputProfilePhotoStatic requires). Not set: menu button (no Mini
App yet). Only fields that differ are written; the previous values are saved to build/bot_profile_before.json;
everything is read back and compared at the end.
Usage: python apply_bot_profile.py [--dry-run]
"""
import json, os, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "content" / "prototype"))

LANGS = {"": "uz_new", "uz": "uz_new", "ru": "ru", "en": "en"}
AVATAR = ROOT / "brand" / "telegram" / "out" / "bot.jpg"
STATE = HERE / "build" / "bot_profile_state.json"
LIMITS = {"name": 64, "short_description": 120, "description": 512}


def plan(built):
    """Desired profile per language_code from build/telegram_texts.json. Raises on anything Telegram would reject."""
    want = {}
    for lang, variant in LANGS.items():
        w = {"short_description": built["bot.short_description"]["text"][variant],
             "description": built["bot.description"]["text"][variant],
             "commands": [{"command": v["command"], "description": v["text"][variant]}
                          for k, v in built.items() if k.startswith("bot.cmd.") and not v.get("drivers")]}
        if lang == "":
            w["name"] = built["bot.name"]["text"][variant]
        for field, limit in LIMITS.items():
            if field in w and not 0 < len(w[field]) <= limit:
                raise ValueError(f"{lang or 'default'}.{field}: length {len(w[field])} not in 1..{limit}")
        for c in w["commands"]:
            if not (1 <= len(c["command"]) <= 32 and c["command"].islower() and 1 <= len(c["description"]) <= 256):
                raise ValueError(f"{lang or 'default'}: bad command {c}")
        want[lang] = w
    return want


def read(call, lang):
    p = {"language_code": lang} if lang else {}
    out = {"short_description": call("getMyShortDescription", p)["short_description"],
           "description": call("getMyDescription", p)["description"],
           "commands": call("getMyCommands", p)}
    if not lang:
        out["name"] = call("getMyName", p)["name"]
    return out


def apply(call, want, dry=False):
    changed = []
    before = {lang: read(call, lang) for lang in want}
    (HERE / "build").mkdir(exist_ok=True)
    json.dump(before, open(HERE / "build" / "bot_profile_before.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    setters = {"name": ("setMyName", "name"), "short_description": ("setMyShortDescription", "short_description"),
               "description": ("setMyDescription", "description"), "commands": ("setMyCommands", "commands")}
    for lang, w in want.items():
        for field, value in w.items():
            if before[lang].get(field) == value:
                continue
            method, key = setters[field]
            params = {key: json.dumps(value, ensure_ascii=False) if field == "commands" else value}
            if lang:
                params["language_code"] = lang
            changed.append(f"{lang or 'default'}.{field}")
            if not dry:
                call(method, params)
                time.sleep(1)
    return before, changed


def set_avatar(call, dry=False):
    """Upload the avatar unless the bot's current first photo is the one this script uploaded last time."""
    me = call("getMe")
    photos = call("getUserProfilePhotos", {"user_id": me["id"], "limit": 1})
    current = photos["photos"][0][-1]["file_unique_id"] if photos["total_count"] else None
    state = json.load(open(STATE, encoding="utf-8")) if STATE.exists() else {}
    if current and state.get("avatar_file_unique_id") == current and state.get("avatar_size") == AVATAR.stat().st_size:
        return False, photos["total_count"]
    if dry:
        return True, photos["total_count"]
    call("setMyProfilePhoto", {"photo": json.dumps({"type": "static", "photo": "attach://p"})}, {"p": str(AVATAR)})
    time.sleep(2)
    photos = call("getUserProfilePhotos", {"user_id": me["id"], "limit": 1})
    state.update(avatar_file_unique_id=photos["photos"][0][-1]["file_unique_id"], avatar_size=AVATAR.stat().st_size)
    json.dump(state, open(STATE, "w", encoding="utf-8"), indent=1)
    return True, photos["total_count"]


def verify(call, want):
    problems = []
    for lang, w in want.items():
        got = read(call, lang)
        for field, value in w.items():
            if got.get(field) != value:
                problems.append(f"{lang or 'default'}.{field}: got {str(got.get(field))[:60]!r}")
    return problems


if __name__ == "__main__":
    from create_sticker_sets import call  # 429-aware (waits retry_after up to TG_MAX_WAIT)
    dry = "--dry-run" in sys.argv
    built = json.load(open(HERE / "build" / "telegram_texts.json", encoding="utf-8"))
    want = plan(built)
    before, changed = apply(call, want, dry)
    print(("would change" if dry else "changed"), len(changed), ":", ", ".join(changed) or "nothing")
    av, n = set_avatar(call, dry)
    print("avatar:", ("would upload" if dry else "uploaded") if av else "already set", "| profile photos:", n)
    if not dry:
        p = verify(call, want)
        print("verify:", "OK — all fields match" if not p else p)
        sys.exit(1 if p else 0)
