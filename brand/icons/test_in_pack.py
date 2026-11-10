"""Temporarily add the concept icons (+ one head emoji) to tulporgo_emoji_by_tulporgobot so they can be shown
in real bot messages, and remove them again. No new set is created (createNewStickerSet is rate limited, see
MUAMMOLAR #26). Added ids are recorded in test_ids.json; `remove` deletes exactly those, nothing else.
Usage: python test_in_pack.py add | remove | status
"""
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "content", "prototype"))
from send_variants import owner_chat  # noqa: E402
from create_sticker_sets import call  # noqa: E402  (waits retry_after on 429 up to TG_MAX_WAIT, never hammers)
from icons import ICONS  # noqa: E402

SET = "tulporgo_emoji_by_tulporgobot"
REC = os.path.join(HERE, "test_ids.json")
HEAD = ("head-01", "👋", os.path.join(ROOT, "brand", "mascot", "poses", "vector", "telegram", "emoji_head_tgs", "09-01-salomlashadi.tgs"), "animated")


def add():
    owner = owner_chat()
    rec = json.load(open(REC, encoding="utf-8")) if os.path.exists(REC) else {}
    items = [(n, alt, os.path.join(HERE, "png100", n + ".png"), "static") for n, (alt, _) in ICONS.items()] + [HEAD]
    for name, alt, path, fmt in items:
        if name in rec:
            continue
        before = {s["file_unique_id"] for s in call("getStickerSet", {"name": SET})["stickers"]}
        call("addStickerToSet", {"user_id": owner, "name": SET, "sticker": json.dumps(
            {"sticker": "attach://f0", "format": fmt, "emoji_list": [alt]}, ensure_ascii=False)}, {"f0": path})
        new = [s for s in call("getStickerSet", {"name": SET})["stickers"] if s["file_unique_id"] not in before]
        assert len(new) == 1, f"{name}: expected 1 new sticker, got {len(new)}"
        rec[name] = {"custom_emoji_id": new[0]["custom_emoji_id"], "file_unique_id": new[0]["file_unique_id"], "alt": alt}
        json.dump(rec, open(REC, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print("added", name, rec[name]["custom_emoji_id"], flush=True)
        time.sleep(2)


def remove():
    rec = json.load(open(REC, encoding="utf-8"))
    st = {s["file_unique_id"]: s["file_id"] for s in call("getStickerSet", {"name": SET})["stickers"]}
    for name, r in list(rec.items()):
        if r["file_unique_id"] in st:
            call("deleteStickerFromSet", {"sticker": st[r["file_unique_id"]]})
            print("removed", name, flush=True)
            time.sleep(2)
        del rec[name]
        json.dump(rec, open(REC, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def replace_tgs():
    """Swap the recorded static PNG icons for the animated vector TGS (tgs/<name>.tgs), in place; record new ids."""
    owner = owner_chat()
    rec = json.load(open(REC, encoding="utf-8"))
    for name in ICONS:
        r = rec.get(name)
        if not r or r.get("format") == "animated":
            continue
        cur = {s["file_unique_id"]: s for s in call("getStickerSet", {"name": SET})["stickers"]}
        old = cur[r["file_unique_id"]]
        call("replaceStickerInSet", {"user_id": owner, "name": SET, "old_sticker": old["file_id"], "sticker": json.dumps(
            {"sticker": "attach://f0", "format": "animated", "emoji_list": [r["alt"]]}, ensure_ascii=False)},
             {"f0": os.path.join(HERE, "tgs", name + ".tgs")})
        new = [s for s in call("getStickerSet", {"name": SET})["stickers"] if s["file_unique_id"] not in cur]
        assert len(new) == 1 and new[0]["is_animated"], f"{name}: replace not confirmed"
        rec[name] = dict(r, custom_emoji_id=new[0]["custom_emoji_id"], file_unique_id=new[0]["file_unique_id"], format="animated")
        json.dump(rec, open(REC, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print("tgs", name, new[0]["custom_emoji_id"], flush=True)
        time.sleep(8)


def status():
    n = len(call("getStickerSet", {"name": SET})["stickers"])
    rec = json.load(open(REC, encoding="utf-8")) if os.path.exists(REC) else {}
    print(SET, "stickers:", n, "| test items recorded:", len(rec), "| expected base 51 ->", "OK" if n == 51 + len(rec) else "MISMATCH")


if __name__ == "__main__":
    {"add": add, "remove": remove, "status": status, "replace-tgs": replace_tgs}[sys.argv[1]]()
