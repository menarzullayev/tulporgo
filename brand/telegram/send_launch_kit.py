"""Stage 4 hand-off to the owner (things no Telegram tool can do: public links, Welcome Messages, Community).
Sends, through @tulporgobot, the step-by-step for the app and the approved welcome materials ready to copy
(text keeps the TulporGo custom emoji when copied by a Premium account). Nothing is posted to the new chats.
Usage: python send_launch_kit.py
"""
import pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
I18N = HERE.parent.parent / "content" / "i18n"
sys.path.insert(0, str(I18N))
sys.argv = ["send_launch_kit", "uz_new", f"--map={I18N / 'build' / 'emoji_map.json'}"]
import send_preview as sp  # noqa: E402
from send_preview import call, owner_chat  # noqa: E402

cid = owner_chat()
sp.load_emoji()
steps = (
    "<b>Kanal va guruhlar yaratildi (yopiq)</b> — chatlar ro'yxatingizda uchta «TulporGo»:\n"
    "• kanal (qora avatar) · • savol-javob (sariq halqa) · • haydovçilar (qora + rul)\n"
    "Avatar, «Haqida», @tulporgobot admin, a'zolar huquqlari — tayyor.\n\n"
    "<b>Siz ilovada qiladigan 3 ish:</b>\n\n"
    "1️⃣ <b>Ochiq havola</b> (shu payt ishga tushish bo'ladi):\n"
    "Kanal → Tahrirlash → Kanal turi → Ommaviy → <code>tulporgo</code>\n"
    "Savol-javob → Tahrirlash → Guruh turi → Ommaviy → <code>tulporgo_chat</code>\n"
    "Haydovçilar guruhi — yopiq qoladi.\n\n"
    "2️⃣ <b>Welcome Message</b> (har chat): Tahrirlash → Welcome Message → pastdagi 3 ta materialni nusxalab yuboring.\n\n"
    "3️⃣ <b>Hamjamiyat «TulporGo»</b>: bot, kanal, savol-javob — Visible; haydovçilar — <b>Hidden</b>. "
    "Sozlamada chat qo'shishni <b>faqat adminlarga</b> qoldiring (standartda istalgan a'zo qo'sha oladi).\n\n"
    "Tayyor bo'lgach yozing — Bot API orqali tekshirib beraman.")
call("sendMessage", {"chat_id": cid, "parse_mode": "HTML", "text": sp.deco(steps)})
sp.send(cid, sp.deco("<b>Material 1 — Kanal welcome</b> (rasm + matn)\n\n" + sp.chat_text("channel.welcome")),
        None, lang="uz_new", photo=str(HERE / "out" / "welcome-channel.png"))
sp.send(cid, sp.deco("<b>Material 2 — Savol-javob welcome</b>\n\n" + sp.chat_text("chat.welcome") + "\n\n" + sp.chat_text("chat.rules")))
sp.send(cid, sp.deco("<b>Material 3 — Haydovçilar welcome</b>\n\n" + sp.chat_text("drivers.welcome")))
print("launch kit sent")
