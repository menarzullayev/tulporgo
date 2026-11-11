# Telegram va Bot API: oxirgi 1 yil (2025-11 … 2026-11) va TulporGo uchun foydasi

**Tekshirilgan: 2026-11-11.** Eng yangi versiya: **Bot API 10.4 (2026-11-09)** (2026-11-11 da ham shu; blogda yangi post yo'q).
Manbalar (hammasi rasmiy):
- https://core.telegram.org/bots/api-changelog — Bot API 9.3 … 10.4
- https://core.telegram.org/bots/api — maydon va metod nomlari shu yerdan tekshirildi
- https://telegram.org/blog — 10 ta post (2025-11-19 … 2026-08-25); 2026-11-10 holatida undan keyingi post yo'q

Kutubxonalar (PyPI, 2026-11-11): `aiogram` 3.31.0 (2026-08-26) — **Bot API 10.3 gacha**, 10.4 (Widgets, TON) hali yo'q;
`telethon` 1.45.0 (2026-09-10).

Yangilash tartibi va doimiy qoida: `CLAUDE.md` → "Telegram ishlari".

---

## 1. Xronologiya

| Sana | Bot API | Telegram ilovasi (blog) | Asosiy narsa |
|---|---|---|---|
| 2025-11-19 | — | Live Stories, Repeated Messages, Gift Auctions | Jonli efir Stories'da (RTMP/OBS), takrorlanuvchi rejalashtirilgan xabarlar |
| 2025-12-12 | — | Passkeys, Gift Purchase Offers | Passkey bilan kirish, Stories'ga audio |
| 2025-12-31 | **9.3** | — | Bot shaxsiy chatida **topic'lar**, `sendMessageDraft`, sovg'alar, paid media 25 000 Stars |
| 2026-01-03 | — | AI Summaries, New Design | Kanal postlarining **AI xulosasi**, iOS Liquid Glass |
| 2026-02-09 | **9.4** | Android Redesign, Group Ownership, **Colored Bot Buttons** | **Rangli va emoji tugmalar**, botga `setMyProfilePhoto`, guruh egaligi avtomatik o'tishi |
| 2026-03-01 | **9.5** | **Member Tags**, Login with Telegram, Date Formatting | Guruh a'zolariga teg, `date_time` entity, streaming hammaga |
| 2026-03-31 / 04-03 | **9.6** | AI Editor, **Mighty Polls**, Live Photos, Managed Bots | So'rovnomalar kuchaydi, bot boshqa botlarni yaratadi |
| 2026-05-07 / 05-08 | **10.0** | **Guest AI Bots**, Bot-to-Bot, Chat Automation | Mehmon bot, so'rovnomani obunachi/mamlakatga cheklash |
| 2026-06-11 | **10.1** | Watch apps, **Rich Text for Bots**, **AI Guardians** | Rich Messages, qo'shilish so'rovini bot Mini App orqali tekshiradi |
| 2026-07-14 | **10.2** | **Communities**, Rich Text Editor, **Ephemeral Messages** | Hamjamiyat, faqat bitta odamga ko'rinadigan bot xabari |
| 2026-08-24 / 08-25 | **10.3** | **Welcome Messages**, **Buttons in Messages**, Signed Gifts | Yangi a'zoga salom xabari, matn ichida tugmalar |
| 2026-11-09 | **10.4** | (blog posti yo'q) | **HTML Widgets** (faqat shaxsiy chat), TON hamyon, `bank_card_number` entity, ikkinchi bot username |

---

## 2. TulporGo uchun: qayerda nima ishlatiladi

### 2.1 Bot (@tulporgobot) — profil va interfeys

| Funksiya | Versiya | Shart / cheklov | TulporGo'da |
|---|---|---|---|
| Nom, tavsif, qisqa tavsif **har til uchun** (`setMyName`, `setMyDescription`, `setMyShortDescription`, `language_code`) | eski | — | 5 til (16-qaror): profil har foydalanuvchiga o'z tilida |
| Bot avatari API orqali (`setMyProfilePhoto`, `removeMyProfilePhoto`) | 9.4 | — | 02 belgi sariq fonda (31-qaror) — skript bilan, BotFather'siz |
| Buyruqlar menyusi har til va har chat turi uchun (`setMyCommands` + `scope`) | eski | — | Yo'lovchi va haydovchi uchun alohida menyu |
| Menyu tugmasi → Mini App (`setChatMenuButton`) | eski | — | "Taksi chaqirish" tugmasi Mini App'ni ochadi |
| **Rangli tugmalar** (`style`: `primary` ko'k, `success` yashil, `danger` qizil) | 9.4 | Sariq rang yo'q | Asosiy harakat `primary`, "Tasdiqlash" `success`, "Bekor qilish" `danger` |
| **Tugmada custom emoji** (`icon_custom_emoji_id`) + bot xabarida custom emoji | 9.4 (+ Mini App `BottomButton.iconCustomEmojiId` 9.5) | Bot egasi **Premium** bo'lishi kerak (@menarzullayev — Premium ✔); shaxsiy chat, guruh, superguruh — **kanalda emas** | O'zimizning `tulporgo_emoji` paketimiz tugmalar va xabarlarda — brend har joyda. **2026-11-10 sinaldi:** @tulporgobot `style` + `icon_custom_emoji_id` + `<tg-emoji>` bilan 8 xabar yubordi, API qabul qildi |
| O'chirilgan tugma (`DisabledButton`, `disabled`) | 10.3 | — | "Haydovchi topilmoqda…" holatida bosilmaydigan tugma |
| **Rich Messages** (`sendRichMessage`): jadval, yig'iladigan bo'lim, sarlavha, ichki rasm, karusel, matn ichida tugmalar, hujjat bloki | 10.1–10.3 | 32 768 belgi; ~8 000 dan keyin "Show More" | Qatnov kartochkasi: yo'nalish, vaqt, narx, mashina jadvali; tarif jadvali |
| **Ephemeral messages** (faqat bitta odamga ko'rinadi) | 10.2–10.4 | Guruhlarda; 10.4 dan callback javobida ham | Guruhda menyu, xato, "e'loningiz yuborildi" — boshqalar ko'rmaydi |
| `date_time` entity | 9.5 | Har foydalanuvchining vaqt mintaqasida, kalendarga qo'shish | Jo'nash vaqti: "Ertaga 07:30" bosilsa eslatma qo'yiladi |
| `bank_card_number` entity | 10.4 | — | P2P obuna to'lovida karta raqami aniq ko'rinadi (11-qaror) |
| Bot shaxsiy chatida **topic'lar** (`has_topics_enabled`, `allows_users_to_create_topics`) | 9.3–9.4 | BotFather'da yoqiladi | "Qatnovlarim", "Obuna", "Yordam" — har qatnov alohida mavzu |
| Streaming javob (`sendMessageDraft`) | 9.3 / 9.5 | Hamma botlar | "Takliflar kelmoqda…" jonli yangilanadi |
| **Guest Mode** (`supports_guest_queries`, `answerGuestQuery`) | 10.0 | Bot faqat o'zi belgilangan xabarni ko'radi | Istalgan guruhda `@tulporgobot Qovunchi → Samarqand` |
| **HTML Widgets** (`sendWidget`) | 10.4 | **Faqat shaxsiy chat**, forward qilinmaydi, HTML ≤ 32 768 bayt (zlib ≤ 4 096); aiogram hali qo'llamaydi | Narx kalkulyatori yoki jonli qatnov holati — keyingi bosqich |
| Ikkinchi username (`…app`, `…ai`, `…agent`, `…game`) | 10.4 | Premium egasi, 2 tagacha bot | Masalan `@tulporgoapp` — band qilishni ko'rib chiqish |
| **Login with Telegram** | 2026-03 | Sayt uchun. OIDC (code + PKCE), `oauth.telegram.org`; UserInfo yo'q — hammasi `id_token` da. Sozlash faqat **BotFather mini-ilovasida** (chat menyusida yo'q): Login Widget → Redirect URIs (aniq moslik), Trusted Origins (faqat brauzer JS token so'rasa), Native Login (ilovalar), Advanced → imzo RS256 (EdDSA/ES256K `profile` ni o'chiradi). Scope'lar: `openid`, `profile`, **`phone`** (tasdiqlangan raqam), **`telegram:bot_access`** (login'dan keyin bot yoza oladi), `ton:wallet` | tulporgo.uz'da parolsiz kirish — **sozlandi va sinaldi 2026-11-11** (to'liq oqim, haqiqiy secret). Token endpoint noto'g'ri kodga secret'dan qat'i nazar `invalid_grant` beradi — secret'ni faqat haqiqiy kod bilan tekshirish mumkin |
| Chat Automation (business bot Premium'siz) | 10.0 | Faqat shaxsiy chatlar | Haydovchi profiliga ulanib, yo'lovchilarga avtomatik javob |

### 2.2 Kanal (@tulporgo)

| Funksiya | Versiya | Shart / cheklov | TulporGo'da |
|---|---|---|---|
| **Welcome Messages** | 2026-08 | Ega sozlaydi: profil → Edit → Welcome Message; bir nechta xabar, media, rich format. Bot admin `can_send_welcome_messages` bilan yubora oladi | Yangi obunachiga: maskot rasmi + "TulporGo nima" + "Botni ochish" tugmasi |
| **Buttons in Messages** | 10.3 | Bot yuboradi (kod kerak) | Postlar ichida "Taksi chaqirish", "Haydovchi bo'lish", "Narxni bilish" |
| **Rich Text Editor** | 2026-07 | **Faqat Premium** (@menarzullayev ✔) | Uzun post: jadval, ichki rasm, sarlavha |
| AI xulosa (o'quvchi uchun) | 2026-01 | Uzun postlarda | Birinchi qatorda asosiy fikr — xulosa to'g'ri chiqsin |
| **So'rovnomalar**: media, tavsif, faqat obunachilar yoki faqat O'zbekiston, statistika (100+ ovoz), Polls tab | 9.6 / 10.0 | — | "Qaysi yo'nalish kerak?", "Qaysi tarif?" — faqat UZ'dan |
| Takrorlanuvchi rejalashtirilgan xabarlar; ovozsiz rejalashtirish | 2025-11 / 2026-05 | — | Har payshanba "Juma bozor qatnovi" eslatmasi |
| Live Stories / jonli efir (RTMP) | 2025-11 | Kanal Stories boost bilan ochiladi | Ishga tushirish kuni jonli efir |
| Kanalga shaxsiy xabarlar, taklif qilingan postlar | 9.2 (2025-08, oyna oldidan) | — | Fikr va shikoyatlar kanal orqali |
| Boost darajalari: rang, emoji status, fon, guruh emoji paketi | eski | Boost soni kerak | Brend sariq rang, TulporGo emoji paketi |

### 2.3 Guruhlar (@tulporgo_chat va yopiq haydovchilar guruhi)

| Funksiya | Versiya | TulporGo'da |
|---|---|---|
| **Member Tags** (`setChatMemberTag`, `can_manage_tags`, `can_edit_tag`) | 9.5 | Haydovchilar guruhida "Tasdiqlangan", "Pro", tuman nomi — bot o'zi qo'yadi |
| **AI Guardian / Join Request Queries** (`answerChatJoinRequestQuery`, `sendChatJoinRequestWebApp`) | 10.1 | Yopiq guruhga qo'shilishdan oldin Mini App'da telefon, mashina, guvohnoma tekshiruvi (12-qaror) |
| Welcome Messages | 2026-08 | Savol-javob guruhida qoidalar + FAQ, faqat yangi a'zoga |
| Ephemeral messages + ephemeral buyruqlar | 10.2 | Guruh toza qoladi |
| Reaksiyalarni o'chirish (`deleteMessageReaction`, `deleteAllMessageReactions`) | 10.0 | Spam nazorati |
| Guruh egaligi: ega ketsa 1 haftadan keyin adminga o'tadi | 2026-02 | **Xavf**: adminlar ro'yxati faqat ishonchli odamlardan |

### 2.4 Hamjamiyat (Communities)

| Funksiya | Versiya | TulporGo'da |
|---|---|---|
| Bot + kanal + guruhlar bitta hamjamiyatda; chat Visible yoki **Hidden** | 10.2 | 30-qaror: haydovchilar guruhi Hidden |
| **Standart holatda istalgan a'zo chat qo'sha oladi** | 10.2 | **Albatta o'chirish kerak** (sozlamada cheklash) — aks holda begona chatlar qo'shiladi |
| `CommunityChatJoined`, `community` (`ChatFullInfo`) | 10.2–10.3 | Bot kim qaysi chatga hamjamiyat orqali kelganini biladi (analitika) |

---

## 3. Ikkinchi darajali (hozircha kerak emas)

Bot-to-bot, managed bots (9.6), custom AI styles, AI editor, Live/Motion photos, sovg'alar (auksion, crafting, signed,
offers), TON hamyon va NFT (10.4), chat share themes (10.4), smart-soat ilovalari, 350 mln GIF, passkeys,
Disable Sharing (Premium, faqat 1:1), document scanner.

## 4. Diqqat va cheklovlar

- **TGS rasmiy talablari** (core.telegram.org/stickers, 2026-11-10 o'qildi): 512×512, obyekt kanvasdan chiqmaydi, ≤ 3 s,
  loop, 60 FPS, ≤ 64 KB. Taqiqlangan: Auto-bezier keys, Expressions, Masks, Layer Effects, Images, Solids, Texts,
  3D Layers, Merge Paths, Star Shapes, Gradient Strokes, Repeaters, Time Stretching, Time Remapping, Auto-Oriented Layers.
  Avtomatik tekshiruv: `brand/mascot/poses/vector/telegram_check.py` → `tgs_forbidden()` (har taqiq uchun salbiy test).
- **Rasmiy vosita bor:** After Effects 2025 + Telegram'ning `Bodymovin-TG` plagini (`%APPDATA%\Adobe\CEP\extensions\com.telegram.bodymovin`,
  5.5.2) o'rnatilgan. Belgilar (`brand/icons/icons_tgs.py`) TGS'ni to'g'ridan-to'g'ri o'sha formatda yaratadi; murakkab
  qo'lda animatsiya (maskot) uchun AE + Bodymovin-TG ishlatiladi.

- **Custom emoji (2026-11-10 o'lchandi):** bot (egasi Premium) o'z paketimizdagi va Telegram'ning **rasmiy** paketlaridagi
  (`RestrictedEmoji` «Animated Emoji», 997 ta; `DuckEmoji`, `HandEmoji`… ) custom emoji'larni xabarda ishlata oladi —
  Telegram entity'larni saqladi (A 13/13, B 9/9). Bot profili, tavsif, kanal/guruh «Haqida» — oddiy matn, custom emoji yo'q.
  Butun tanali maskot emoji'si matnda ~20 px da o'qilmaydi (boshi 6–7 px) — matn ichida bosh emoji yoki oddiy belgi kerak.

- **Custom emoji rich message ichida (o'lchandi 2026-11-10, abramyan-promo):** Premium egali bot `<tg-emoji emoji-id="…">` ni `sendRichMessage` HTML'ida shaxsiy chatga yubora oladi (19 ta, ishladi). Paketni `getStickerSet` bilan topish mumkin: `sticker_type == "custom_emoji"`. Foydali paketlar: `RestrictedEmoji` (Telegram animatsion, 997), `ProgrammingEmoji` (Python, C++, Java, JS, Go, PHP, Rust, Kotlin… logolari), `FlagsEmoji`, `NewsEmoji`. Hujjat: Premium bo'lmagan foydalanuvchi forward qilsa, oddiy emojiga tushishi mumkin.
- **Rich message forward/copy (o'lchandi 2026-11-10, abramyan-promo):** bot yuborgan rich message'ni `copyMessage` nusxa qiladi, foydalanuvchi esa "muallifsiz" forward qila oladi — natija baribir rich (rasm, tugma, `<details>`, slayd-shou). Boshqa kanal egasi postni o'z kanaliga "Hide sender name" bilan qo'yishi mumkin. HTML: `<tg-button-row>`, `<tg-button type="url" style="primary">`, `<details>`, `<tg-slideshow>`; media `tg://photo?id=<id>` + `media` maydoni, bitta multipart so'rovda.

- **Eski ilovalar:** yangi funksiyani ko'rsata olmaydigan ilova "yangilang" degan placeholder chiqaradi (2026-08). Rich message,
  widget, rangli tugma uchun doim oddiy matnli zaxira yo'l bo'lsin — viloyatlarda eski ilova ko'p.
- **Widgets** hozircha faqat shaxsiy chatda; kanal va guruhda ishlamaydi.
- **Rangli tugmalarda sariq yo'q** — brend sarig'i tugmada emas, custom emoji va rasmlarda beriladi.
- Rich Text Editor (qo'lda yoziladigan post) — faqat Premium hisobdan; bot orqali rich message esa Premium talab qilmaydi.
- Welcome Message'ni ilovada **ega** sozlaydi; bot uchun alohida "set" metodi yo'q, faqat `can_send_welcome_messages` huquqi.
  **Userbot (MTProto) orqali esa mumkin (2026-11-10 aniqlandi):** Telegram Desktop `ephemeral.sendMessage(welcome=True,
  peer=<chat>, receiver_id=inputUserEmpty)` bilan qo'shadi, `ephemeral.editMessage` / `deleteWelcomeMessage` /
  `getWelcomeMessages` bilan boshqaradi; chigwell forkida `get/set/delete_welcome_message`. Chegara app config
  `ephemeral_welcome_messages_max` — @menarzullayev uchun **3** (o'lchandi). TulporGo kanali, savol guruhi va
  haydovchilar guruhida 1 tadan welcome bor.
- Custom emoji paket nomini tekshirish (`stickers.checkShortName`): band nomga `false` emas, `SHORT_NAME_OCCUPIED`
  xatosi qaytadi (o'lchandi). `tulporgo_emoji` nomi foydalanuvchi uchun bo'sh — bot paketi `_by_<bot>` qo'shimchali.
- Mini App metodlari faqat o'z domenidan (10.2, 2026-07-20 dan) — tulporgo.uz.
- Guest Mode yo'lovchi tomonda yordam beradi, lekin haydovchi e'lonlarini guruhlarga yuborish uchun userbot baribir kerak (8-qaror).
- Forum/topic (guruhlarda), Stories, verifikatsiya bo'yicha bu yilda katta o'zgarish yo'q (verifikatsiya tavsifi 10.4 da faqat tasdiqlovchi tashkilotlar uchun).
