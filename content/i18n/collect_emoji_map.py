"""Variant B: take the owner's own favourite custom emoji (sent to @tulporgobot in one message, in ROLES order),
write build/variant_b_map.json and render the preview messages with them.
  python collect_emoji_map.py ask              -> bot asks the owner (lists the roles)
  python collect_emoji_map.py wait <seconds>   -> waits for the reply, builds the map, sends variant B
The newest owner message with >= 3 custom emoji, sent after the ask, is used; emoji are taken in order.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "prototype"))
from send_variants import call, owner_chat  # noqa: E402

# (shown to the owner, standard emoji in our texts/buttons that it replaces)
ROLES = [("👋 salom", ["👋"]), ("🚕 taksi", ["🚕"]), ("🤝 haydovchi", ["🤝"]), ("💬 taklif/chat", ["💬"]),
         ("✅ tasdiq", ["✅"]), ("🛡 xavfsizlik", ["🛡"]), ("🚀 tez orada", ["🚀"]), ("1️⃣", ["1️⃣"]), ("2️⃣", ["2️⃣"]),
         ("3️⃣", ["3️⃣"]), ("📣 e'lon/kanal", ["📣", "📢"]), ("❓ savol", ["❓"]), ("💳 obuna/to'lov", ["💳"])]
STATE = os.path.join(HERE, "build", "variant_b_state.json")
MAP = os.path.join(HERE, "build", "variant_b_map.json")


def ask():
    cid = owner_chat()
    lines = "\n".join(f"{i}. {r}" for i, (r, _) in enumerate(ROLES, 1))
    m = call("sendMessage", {"chat_id": cid, "parse_mode": "HTML", "text":
        "<b>B variant uchun emoji'laringiz</b>\n\nHisobingizdagi yoqqan custom emoji'lardan quyidagi tartibda "
        f"<b>bitta xabarda</b> {len(ROLES)} ta yuboring (oraliqsiz ham bo'ladi):\n\n{lines}\n\n"
        "Kam yuborsangiz, qolganlari oddiy emoji bo'lib qoladi."})
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump({"asked_at": m["date"]}, open(STATE, "w"))
    print("asked, message", m["message_id"])


def find_reply(since):
    owner = owner_chat()
    best = None
    for u in call("getUpdates", {"limit": 100}):
        m = u.get("message") or {}
        if m.get("from", {}).get("id") != owner or m.get("date", 0) < since:
            continue
        ids = [e["custom_emoji_id"] for e in m.get("entities", []) if e["type"] == "custom_emoji"]
        if len(ids) >= 3:
            best = ids
    return best


def build(ids):
    m = {}
    for (role, keys), cid in zip(ROLES, ids):
        for k in keys:
            m[k] = cid
    json.dump(m, open(MAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return m


def wait(seconds):
    since = json.load(open(STATE))["asked_at"]
    end = time.time() + seconds
    while time.time() < end:
        ids = find_reply(since)
        if ids:
            m = build(ids)
            print(f"got {len(ids)} custom emoji, mapped {len(m)} keys")
            subprocess.run([sys.executable, os.path.join(HERE, "send_preview.py"), "uz_new", f"--map={MAP}",
                            "--label=B variant — hisobingizdagi emoji'lar"], check=True,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            return 0
        time.sleep(20)
    print("no reply within", seconds, "s")
    return 2


if __name__ == "__main__":
    if sys.argv[1] == "ask":
        ask()
    else:
        sys.exit(wait(int(sys.argv[2])))
