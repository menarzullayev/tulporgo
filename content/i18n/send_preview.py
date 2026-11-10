"""Send the stage-1 text drafts to the owner through @tulporgobot, rendered as they will look in Telegram:
styled buttons, TulporGo custom emoji on buttons and in text (bot owner has Premium, Bot API 9.4),
the Russian part in an expandable quote. Buttons are inert (no bot code yet).
Usage: python send_preview.py [uz_new|uz_latn|uz_cyrl]   (default uz_new)
"""
import html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "content", "prototype"))
from send_variants import call, owner_chat  # noqa: E402

V = os.path.join(ROOT, "brand", "mascot", "poses", "vector")
NAMES = [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]
B = json.load(open(os.path.join(HERE, "build", "telegram_texts.json"), encoding="utf-8"))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
UZ = ARGS[0] if ARGS else "uz_new"
OPT = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
# --map=<json {standard emoji: custom_emoji_id}>: show a variant where standard emoji are replaced by custom ones
MAP = json.load(open(OPT["map"], encoding="utf-8")) if "map" in OPT else {}
EMOJI = {}


def deco(h):
    """Replace standard emoji (longest first, with or without U+FE0F) by the mapped custom emoji."""
    for std in sorted(MAP, key=len, reverse=True):
        for form in {std, std.replace("️", ""), std + "️"}:
            if form and form in h and not form.isascii():
                h = h.replace(form, f'<tg-emoji emoji-id="{MAP[std]}">{std}</tg-emoji>')
    return h


def load_emoji():
    st = call("getStickerSet", {"name": "tulporgo_emoji_by_tulporgobot"})["stickers"]
    EMOJI.update({n: s["custom_emoji_id"] for n, s in zip(NAMES, st)})


def esc(t):
    return html.escape(t, quote=False)


def tg_emoji(pose, fallback):
    return f'<tg-emoji emoji-id="{EMOJI[pose]}">{fallback}</tg-emoji>' if pose in EMOJI else fallback


def kb(item, lang, icons=True):
    rows = []
    for b in item["buttons"]:
        btn = {"text": b["labels"][lang]}
        btn.update({"url": b["url"]} if "url" in b else {"callback_data": "preview"})
        if "style" in b:
            btn["style"] = b["style"]
        if icons and MAP.get(b.get("fallback")):
            btn["icon_custom_emoji_id"] = MAP[b["fallback"]]
        elif icons and b.get("icon") in EMOJI:
            btn["icon_custom_emoji_id"] = EMOJI[b["icon"]]
        elif b.get("fallback"):
            btn["text"] = b["fallback"] + " " + btn["text"]
        rows.append([btn])
    return {"inline_keyboard": rows}


def chat_text(key):
    t = B[key]["text"]
    return f"{esc(t['uz_new'])}\n\n<blockquote expandable>{esc(t['ru'])}</blockquote>"


def send(cid, text, item=None, lang=UZ, photo=None):
    fields = {"chat_id": cid, "parse_mode": "HTML"}
    for icons in (True, False):
        markup = kb(item, lang, icons) if item and item.get("buttons") else None
        try:
            if photo:
                f = dict(fields, caption=text, **({"reply_markup": json.dumps(markup)} if markup else {}))
                return call("sendPhoto", f, {"photo": photo})["message_id"], icons
            f = dict(fields, text=text, **({"reply_markup": markup} if markup else {}))
            return call("sendMessage", f)["message_id"], icons
        except SystemExit as e:
            if not icons:
                raise
            print("custom emoji rejected, retrying without:", str(e)[:160])


def send_variant(cid, label):
    """The messages that carry emoji, with MAP applied (profile/description fields are plain text: no custom emoji)."""
    t = lambda k: B[k]["text"][UZ]
    out = [send(cid, f"<b>{esc(label)}</b>\nSalomlashuv, «tez orada», kanal, savol-javob va haydovçilar xabarlari. "
                     "Bot profili va tavsiflarda custom emoji ishlamaydi (Telegram faqat oddiy matn qabul qiladi).")]
    out.append(send(cid, deco("<b>③ Salomlashuv</b>\n\n" + esc(t("bot.start"))), B["bot.start"]))
    out.append(send(cid, deco("<b>«Tez orada» javobi</b>\n\n" + esc(t("bot.coming_soon"))), B["bot.coming_soon"]))
    photo = os.path.join(ROOT, "brand", "mascot", "poses", "09-01-salomlashadi.png")
    out.append(send(cid, deco("<b>④ Kanal: Welcome Message</b>\n\n" + chat_text("channel.welcome")),
                    B["channel.welcome"], lang="uz_new", photo=photo))
    out.append(send(cid, deco("<b>⑤ Savol-javob guruhi</b>\n\n" + chat_text("chat.welcome")), B["chat.welcome"], lang="uz_new"))
    out.append(send(cid, deco("<b>⑥ Haydovçilar guruhi</b>\n\n" + chat_text("drivers.welcome")), B["drivers.welcome"], lang="uz_new"))
    return out


if __name__ == "__main__":
    load_emoji()
    cid = owner_chat()
    if MAP:
        print("sent:", send_variant(cid, OPT.get("label", "Variant")))
        sys.exit(0)
    t = lambda k, lang=UZ: B[k]["text"][lang]
    sent = []
    sent.append(send(cid, "<b>1-bosqich: matnlar — QORALAMA</b>\nQuyida 6 ta namuna: bot profili, til tanlash, "
                          "salomlashuv, kanal, savol-javob guruhi, haydovchilar guruhi. Tugmalar hozircha ishlamaydi. "
                          f"O'zbekcha qism: <b>{UZ}</b>."))
    cmds = "\n".join(f"/{B[k]['command']} — {esc(t(k))}" + ("  <i>(haydovçilar)</i>" if B[k].get("drivers") else "")
                     for k in B if k.startswith("bot.cmd."))
    sent.append(send(cid, "<b>① Bot profili</b>\n\n"
                          f"<b>Nom:</b> {esc(t('bot.name'))}\n\n<b>Qisqa tavsif</b> (profil va ulashishda):\n{esc(t('bot.short_description'))}\n\n"
                          f"<b>Tavsif</b> (bo'sh chatda, Start'dan oldin):\n{esc(t('bot.description'))}\n\n"
                          f"<b>Menyu tugmasi:</b> {esc(t('bot.menu_button'))}\n\n<b>Buyruqlar:</b>\n{cmds}"))
    picker = {"buttons": [dict(labels={UZ: label}, callback_data=code) for code, label in
                          [("uz_new", "Özbekça"), ("uz_latn", "Oʻzbekcha"), ("uz_cyrl", "Ўзбекча"), ("ru", "Русский"), ("en", "English")]]}
    sent.append(send(cid, "<b>② Til tanlash</b> (birinchi /start)\n\nTilni tanlang · Выберите язык · Choose language", picker))
    start = esc(t("bot.start")).replace("👋", tg_emoji("09-01-salomlashadi", "👋"), 1)
    sent.append(send(cid, "<b>③ Salomlashuv</b> (til tanlangandan keyin)\n\n" + start, B["bot.start"]))
    photo = os.path.join(ROOT, "brand", "mascot", "poses", "09-01-salomlashadi.png")
    sent.append(send(cid, "<b>④ Kanal: yangi obunachiga Welcome Message</b>\n\n" + chat_text("channel.welcome"),
                     B["channel.welcome"], lang="uz_new", photo=photo))
    sent.append(send(cid, "<b>⑤ Savol-javob guruhi: welcome + qoidalar</b>\n\n" + chat_text("chat.welcome") + "\n\n"
                          + chat_text("chat.rules"), B["chat.welcome"], lang="uz_new"))
    sent.append(send(cid, "<b>⑥ Haydovchilar guruhi: welcome</b>\n\n" + chat_text("drivers.welcome"),
                     B["drivers.welcome"], lang="uz_new"))
    sent.append(send(cid, "<b>Tavsiflar</b> (profil «Haqida» qismi)\n\n"
                          f"<b>Kanal:</b>\n{esc(t('channel.description', 'composed'))}\n\n"
                          f"<b>Savol-javob:</b>\n{esc(t('chat.description', 'composed'))}\n\n"
                          f"<b>Haydovchilar:</b>\n{esc(t('drivers.description', 'composed'))}"))
    print("sent:", [(m, "custom-emoji" if ic else "fallback") for m, ic in sent])
