"""Show stage-2 visuals to the owner through @tulporgobot, as they will look in Telegram:
avatar sheet, the channel welcome (image + approved text + buttons with TulporGo icons), and the pinned carousel as a
rich slideshow (decision 37) with the approved pinned text. Nothing is published anywhere else.
Usage: python send_stage2.py
"""
import json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
I18N = ROOT / "content" / "i18n"
sys.path.insert(0, str(I18N))
sys.argv = ["send_stage2", "uz_new", f"--map={I18N / 'build' / 'emoji_map.json'}"]
import send_preview as sp  # noqa: E402  (loads texts, emoji map, Bot API helpers)
from send_preview import call, owner_chat  # noqa: E402

cid = owner_chat()
sp.load_emoji()
call("sendMessage", {"chat_id": cid, "parse_mode": "HTML", "text": sp.deco(
    "<b>2-bosqich: vizuallar — QORALAMA</b>\n1) avatarlar, 2) kanal welcome, 3) «Bu yerdan boshlang» karuseli.\n\n"
    "<b>Yangi imkoniyatlar:</b>\n"
    "✅ Bot avatari API orqali qo'yiladi (setMyProfilePhoto, Bot API 9.4) — BotFather'siz.\n"
    "✅ Kanal Welcome Message rasm + matn + tugma bilan (2026-08).\n"
    "✅ Karusel — Rich slideshow: rasmlar, matn va tugmalar bitta postda (10.1).")})
call("sendPhoto", {"chat_id": cid, "parse_mode": "HTML", "caption":
    "<b>① Avatarlar</b> (doira, 160 / 48 / 32 px, oq va qora ro'yxatda)\n"
    "bot — sariq fon, qora belgi · kanal — qora · haydovchilar — qora + rul\n"
    "Savol-javob: <b>chat</b> (oq, 31-qaror) yoki <b>chat-ring</b> (oq + sariq halqa — oq ro'yxatda yo'qolmaydi)"},
    {"photo": str(HERE / "avatars-preview.png")})
item = sp.B["channel.welcome"]
sp.send(cid, sp.deco("<b>② Kanal: Welcome Message</b>\n\n" + sp.chat_text("channel.welcome")), item, lang="uz_new",
        photo=str(HERE / "out" / "welcome-channel.png"))

# ③ carousel: upload frames once to get file_ids, remove the upload album, send the rich slideshow
frames = [str(HERE / "out" / "carousel" / f"f{i}.png") for i in range(1, 5)]
media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(4)]
up = call("sendMediaGroup", {"chat_id": cid, "media": json.dumps(media)}, {f"p{i}": frames[i] for i in range(4)})
fids = [m["photo"][-1]["file_id"] for m in up]
for m in up:
    call("deleteMessage", {"chat_id": cid, "message_id": m["message_id"]})
pinned = sp.B["channel.pinned"]["text"]
first, rest = pinned["uz_new"].split("\n", 1)
btns = [{"text": b["labels"]["uz_new"], "url": b["url"]} for b in item["buttons"]]
rich = {"blocks": [
    {"type": "heading", "size": 2, "text": first.replace("👇", "").strip()},
    {"type": "slideshow", "blocks": [{"type": "photo", "photo": {"type": "photo", "media": f}} for f in fids]},
    {"type": "paragraph", "text": rest},
    {"type": "expandable_blockquote", "text": pinned["ru"]},
    {"type": "buttons", "buttons": btns}]}
call("sendMessage", {"chat_id": cid, "text": "③ Qadalgan post: «Bu yerdan boshlang» — rasmlarni suring 👇"})
m = call("sendRichMessage", {"chat_id": cid, "rich_message": rich})
print("stage 2 sent; slideshow message", m["message_id"])
