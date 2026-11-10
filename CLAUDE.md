# TulporGo (taxi-bot) — agent qoidalari

Umumiy qoidalar: `C:\Users\nsn\.claude\CLAUDE.md` (murojaat "Saidakbar aka", til, tasdiq siyosati).
Ishni boshlashdan oldin: `HANDOFF.md` (holat va ochiq ishlar), `QARORLAR.md` (qarorlar jurnali, asosiy manba).
Ilova oynasidagi matn (pastki xulosa, savol, tugmalar, reja qadamlari) ham o'zbekcha.

## Telegram ishlari — doimiy qoida (2026-11-10, Saidakbar aka talabi)

Telegram har yili ko'p yangilanadi; TulporGo doim eng yangi imkoniyatlardan foydalanadi. Bilim fayli:
**`TELEGRAM-YANGILIKLAR.md`** (oxirgi 1 yil, TulporGo uchun qo'llanishi bilan).

**Qachon:** vazifa Telegram'ga tegsa — bot, kanal, guruh, hamjamiyat, Mini App, userbot, stiker/emoji, post,
Bot API, `aiogram`, `telethon`, BotFather, Telegram dizayni yoki marketingi.

**Har safar, ish boshida:**

1. `TELEGRAM-YANGILIKLAR.md` ni o'qi.
2. Yangilikni tekshir (2 buyruq, ~2 soniya):
   ```bash
   curl -s https://core.telegram.org/bots/api-changelog | grep -oE 'Bot API [0-9]+\.[0-9]+' | head -1
   curl -s https://telegram.org/blog | grep -oE 'class="dev_blog_card_date">[^<]*' | head -1
   ```
   Faylda yozilgan eng yangi versiya yoki blog sanasidan yangisi chiqqan bo'lsa: rasmiy manbadan
   (changelog, `core.telegram.org/bots/api`, blog posti) o'rganib, faylni yangila — xronologiya, tegishli
   jadval, "Tekshirilgan" sanasi. Saidakbar akaga 1–3 qatorda nima yangi ekanini ayt.
3. Rejada yoki javobda **"Yangi imkoniyatlar"** bloki: shu vazifaga mos 1–5 ta yangi funksiya, tavsiya
   qilingani birinchi, har biri bir qatorda (nima beradi + cheklovi). Mos narsa bo'lmasa — "yangi imkoniyat yo'q" deb bir qator.
4. Dizayn yoki UX'ni o'zgartiradigan yangi funksiya — Saidakbar aka tasdig'idan keyin. Avval ko'rsatib, keyin so'ra
   (render → @tulporgobot orqali yuborish, `content/prototype/send_variants.py`).
5. Kutubxona qo'llaydimi — tekshir (`aiogram` qaysi Bot API gacha, `telethon` qaysi layer). Qo'llamasa:
   to'g'ridan-to'g'ri HTTP chaqiruv yoki kutish — javobda ayt.
6. Eski ilovalar uchun zaxira: rich message, widget, rangli tugma ko'rinmasa ham asosiy harakat oddiy matn
   va oddiy tugma bilan bajarilsin.

**Xavfsizlik (o'zgarmaydi):** kanal yoki guruhga post, hamjamiyatga qo'shish, avatar yoki tavsifni o'zgartirish —
tashqi e'lon, avval tasdiq. Telegram foydalanuvchi hisoblarida `FloodWait` bo'lsa to'xta. WorkBuddy'ning
`~/.mcp-telegram/session` ga tegilmaydi. Bot token `.secrets/bot.env` — hech qachon chiqarilmaydi.
