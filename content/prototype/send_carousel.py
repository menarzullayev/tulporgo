"""Send the 4-frame carousel to the owner in 3 ways: (1) album, (2) rich slideshow, (3) rich collage."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_variants import call, owner_chat, HERE

F = [os.path.join(HERE, "carousel", f"f{i}.png") for i in range(1, 5)]
UZ_TITLE = "Taksini qanday topasiz? 3 qadam"
UZ_LINES = ["1. Yönalişni yozing: qayerdan, qayerga va qaçon.",
            "2. Haydovçilar narx va maşina bilan taklif yuboradi.",
            "3. Özingiz tanlaysiz va narxni kelişasiz."]
RU = ("1. Напишите маршрут: откуда, куда и когда. 2. Водители пришлют предложения с ценой и машиной. "
      "3. Вы сами выбираете и договариваетесь о цене.")
BTN_TAXI = {"text": "🚕 Taksi çaqiriş", "url": "https://t.me/tulporgobot?start=taxi"}
BTN_DRV = {"text": "Haydovçi böliş", "url": "https://t.me/tulporgobot?start=driver"}

cid = owner_chat()
call("sendMessage", {"chat_id": cid, "text": "Karusel: 3 xil usul. Har birini telefonda varaqlab ko'ring."})

# 1) Album: caption on the first item; albums cannot carry buttons -> buttons in a follow-up message
call("sendMessage", {"chat_id": cid, "text": "▼ 1-usul · Albom (oddiy Telegram albomi)"})
caption = f"<b>{UZ_TITLE}</b>\n\n" + "\n".join(UZ_LINES) + f"\n\n<blockquote expandable>{RU}</blockquote>"
media = [{"type": "photo", "media": f"attach://p{i}", **({"caption": caption, "parse_mode": "HTML"} if i == 0 else {})} for i in range(4)]
msgs = call("sendMediaGroup", {"chat_id": cid, "media": json.dumps(media)}, {f"p{i}": F[i] for i in range(4)})
file_ids = [m["photo"][-1]["file_id"] for m in msgs]
call("sendMessage", {"chat_id": cid, "text": "👇 Albomga tugma qo'shib bo'lmaydi, shuning uçun alohida xabar:",
                     "reply_markup": {"inline_keyboard": [[BTN_TAXI, BTN_DRV]]}})


def rich(kind):
    blocks = [
        {"type": "heading", "size": 2, "text": UZ_TITLE},
        {"type": kind, "blocks": [{"type": "photo", "photo": {"type": "photo", "media": fid}} for fid in file_ids]},
        *[{"type": "paragraph", "text": l} for l in UZ_LINES],
        {"type": "expandable_blockquote", "text": RU},
        {"type": "buttons", "buttons": [BTN_TAXI, BTN_DRV]},
    ]
    return {"blocks": blocks}


for n, kind, label in ((2, "slideshow", "Rich post · slideshow (varaqlanadigan, tugmalar post içida)"),
                       (3, "collage", "Rich post · collage (4 ta rasm bir panjarada, tugmalar post içida)")):
    call("sendMessage", {"chat_id": cid, "text": f"▼ {n}-usul · {label}"})
    try:
        m = call("sendRichMessage", {"chat_id": cid, "rich_message": rich(kind)})
        print(kind, "ok message_id", m["message_id"])
    except SystemExit as e:
        print(kind, "FAILED:", e)
        call("sendMessage", {"chat_id": cid, "text": f"{n}-usul yuborilmadi: {str(e)[:300]}"})
print("album ok", len(msgs), "photos")
