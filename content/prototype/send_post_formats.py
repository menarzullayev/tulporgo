"""Decision 32 details: send one channel post to the owner in three formats, so the post format is chosen on a phone.

  1 Klassik      — sendPhoto + caption + expandable Russian block + buttons (every client, every chat)
  2 Rich         — sendRichMessage: photo, heading, lines, expandable Russian block, buttons inside the post
  3 Rich+jadval  — the same for tabular content (driver tariffs, decision 10), with a table block

Facts only from QARORLAR.md (9, 10, 12, 13, 44). Text in the new Uzbek Latin alphabet (decision 29).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from send_variants import HERE, call, owner_chat  # noqa: E402

IMG_PASSENGER = os.path.join(HERE, "text-variants", "C-pastki-plashka.png")
IMG_DRIVER = os.path.join(HERE, "text-variants", "B-tepada-sarlavha.png")

TITLE = "Qöşrabot → Samarqand: taksi endi botda"
LINES = ["📍 Yönalişni yozasiz — haydovçilar narx bilan taklif yuboradi.",
         "🚗 Haydovçi, maşina va reyting oldindan körinadi.",
         "🛡 Qatnovni yaqinlaringizga ulaşa olasiz."]
NOTE = "Yölovçilar uçun bepul."
RU = ("Кошрабад → Самарканд: такси теперь в боте. Напишите маршрут — водители пришлют предложения с ценой. "
      "Водитель, машина и рейтинг видны заранее. Поездкой можно поделиться с близкими. Для пассажиров бесплатно.")
TAXI = {"text": "🚕 Taksi çaqiriş", "url": "https://t.me/tulporgobot?start=taxi", "style": "primary"}
DRIVER = {"text": "Haydovçi böliş", "url": "https://t.me/tulporgobot?start=driver"}

D_TITLE = "Haydovçilar uçun tariflar"
D_ROWS = [("Tarif", "Narx / oy", "Nima beradi"),
          ("Asosiy", "29 000 söm", "Yölovçi sörovlari, takliflar"),
          ("Pro", "59 000 söm", "+ avto-e'lon, 15 guruhgaça"),
          ("Biznes", "99 000 söm", "Çeksiz guruh, ustuvorlik")]
D_LINES = ["Birinçi 7 kun — bepul sinov.", "Işga tuşiş davrida birinçi 1–2 oy hamma uçun bepul."]
D_RU = ("Тарифы для водителей: Базовый 29 000 сум/мес, Pro 59 000 сум/мес (+ автообъявления, до 15 групп), "
        "Бизнес 99 000 сум/мес (без ограничения групп, приоритет). Первые 7 дней — бесплатно; на старте первые "
        "1–2 месяца бесплатно для всех.")


def caption() -> str:
    return (f"<b>{TITLE}</b>\n\n" + "\n".join(LINES) + f"\n\n<i>{NOTE}</i>\n\n"
            f"<blockquote expandable>{RU}</blockquote>")


def cell(text, header=False):
    return {"text": {"type": "bold", "text": text} if header else text, "align": "left", "valign": "middle",
            **({"is_header": True} if header else {})}


cid = owner_chat()
if "--no-intro" not in sys.argv:
    call("sendMessage", {"chat_id": cid, "text": "Post formati (32-qaror): bitta post, 3 xil ko'rinish. Telefonda ko'ring, "
                         "tugmalarni bosib, ruscha blokni ochib ko'ring. Raqam bilan javob bering: 1, 2 yoki 3."})

call("sendMessage", {"chat_id": cid, "text": "▼ 1 · Klassik: rasm + izoh + tugmalar (eski ilovalarda ham bir xil)"})
m1 = call("sendPhoto", {"chat_id": cid, "caption": caption(), "parse_mode": "HTML",
                        "reply_markup": json.dumps({"inline_keyboard": [[TAXI, DRIVER]]})},
                        {"photo": IMG_PASSENGER})
photo_id = m1["photo"][-1]["file_id"]

call("sendMessage", {"chat_id": cid, "text": "▼ 2 · Rich: sarlavha, rasm, matn va tugmalar bitta post ichida "
                                             "(karusel postlari bilan bir xil uslub, 37-qaror)"})
call("sendRichMessage", {"chat_id": cid, "rich_message": {"blocks": [
    {"type": "photo", "photo": {"type": "photo", "media": photo_id}},
    {"type": "heading", "size": 2, "text": TITLE},
    *[{"type": "paragraph", "text": line} for line in LINES],
    {"type": "footer", "text": NOTE},
    {"type": "expandable_blockquote", "text": RU},
    {"type": "buttons", "buttons": [TAXI, DRIVER]},
]}})

call("sendMessage", {"chat_id": cid, "text": "▼ 3 · Rich + jadval: ma'lumot postlari uchun (tariflar, yo'nalishlar)"})
m3 = call("sendPhoto", {"chat_id": cid, "caption": "(rasm yuklash uchun yordamchi xabar)"}, {"photo": IMG_DRIVER})
call("deleteMessage", {"chat_id": cid, "message_id": m3["message_id"]})
call("sendRichMessage", {"chat_id": cid, "rich_message": {"blocks": [
    {"type": "heading", "size": 2, "text": D_TITLE},
    {"type": "photo", "photo": {"type": "photo", "media": m3["photo"][-1]["file_id"]}},
    {"type": "table", "is_bordered": True, "is_striped": True,
     "cells": [[cell(c, header=(i == 0)) for c in row] for i, row in enumerate(D_ROWS)]},
    *[{"type": "paragraph", "text": line} for line in D_LINES],
    {"type": "expandable_blockquote", "text": D_RU},
    {"type": "buttons", "buttons": [{**DRIVER, "style": "primary"}]},
]}})
print("sent 3 formats")
