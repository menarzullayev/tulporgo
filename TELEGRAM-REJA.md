# TulporGo: bot, kanal, guruhlar — professional sozlash rejasi

Tuzilgan: 2026-11-10. Asos: `QARORLAR.md` 26–38, `TELEGRAM-YANGILIKLAR.md` (Bot API 10.4 gacha).
Holat: 1–2-bosqichlar tasdiqlandi, 3-bosqich o'rnatildi, 4-bosqich bajarildi — kanal va savol-javob ochiq (2026-11-10); qolganlari **taklif** — har bo'lim Saidakbar aka tasdig'idan keyin bajariladi. Hech narsa hali e'lon qilinmagan.

## Asosiy g'oya: bitta yo'l (voronka)

```
Reklama / guruhdagi e'lon / do'st ulashdi
        ↓
@tulporgo kanali ── Welcome Message: "TulporGo nima" + [Botni ochish]
        ↓                                   ↓
@tulporgo_chat (savol-javob)          @tulporgobot ── [Taksi chaqirish] → Mini App
        ↓                                   ↓
         ←──── TulporGo hamjamiyati (bitta joyda hammasi) ────→
                                            ↓
                           Haydovchi: [Haydovchi bo'lish] → tekshiruv → yopiq guruh (Hidden)
```

Har joyda bir xil: nom **"TulporGo"** (28-qaror), 02 belgi, sariq #FFC72C / qora #111214 / oq,
09 maskot, o'zimizning emoji paketi. Har ekranda **bitta asosiy harakat**.

## 1. Bot @tulporgobot — "vitrina"

| Element | Taklif | Yangi imkoniyat |
|---|---|---|
| Avatar | 02 sariq fonda (31-qaror), 640×640, markazda, burchaklarda havo | `setMyProfilePhoto` (9.4) |
| Nom | "TulporGo" | — |
| Qisqa tavsif (profil, ulashishda) | 1 qator, 120 belgigacha: nima + kim uchun | har til uchun (5 til) |
| Tavsif (bo'sh chatda, /start dan oldin) | 3–4 qator: foyda → qanday ishlaydi → bepul | har til uchun |
| Menyu tugmasi | "Taksi chaqirish" → Mini App | `setChatMenuButton` |
| Buyruqlar | Yo'lovchi: /start, /qatnovlarim, /yordam. Haydovchi: + /elon, /obuna | `scope` bo'yicha alohida |
| Salomlashish (/start) | Maskot (01 salomlashadi) + 2 qator + 2 tugma: [Taksi chaqirish] `primary`, [Haydovchiman] | rangli tugma, custom emoji tugmada (Premium ✔) |
| Chat tuzilishi | Mavzular: "Qatnovlarim", "Obuna", "Yordam" | bot chatida topic'lar (9.3–9.4) |
| Qatnov kartochkasi | Jadval: yo'nalish, vaqt, narx, mashina; vaqt `date_time` | Rich Messages (10.1), `date_time` (9.5) |
| Guruhlarda | `@tulporgobot Qovunchi → Samarqand` | Guest Mode (10.0) |

**Muhim:** bot kodi hali yo'q. Kanal ochilsa, bot `/start` ga javob berishi shart, aks holda birinchi taassurot
buziladi. Variant: bot kodi tayyor bo'lguncha minimal "tez orada" javobi (maskot + "Kanalga obuna bo'ling").

## 2. Kanal @tulporgo — "jurnal"

| Element | Taklif | Yangi imkoniyat |
|---|---|---|
| Avatar | 02-dark qora fonda (31-qaror) | — |
| Tavsif | 2 qator + @tulporgobot havolasi | — |
| Welcome Message (faqat yangi obunachiga) | Maskot rasmi + "TulporGo nima" (3 qator) + [Botni ochish] [Haydovchi bo'lish] | Welcome Messages (2026-08) |
| Qadalgan post | "Bu yerdan boshlang": 3 qadam karusel (RM panorama, 37-qaror) | Rich slideshow |
| Post qolipi | 32–37-qarorlar: noyob rasm + sarlavha + yangi alifbo + ruscha yig'iladigan blok + tugmalar | Buttons in Messages (10.3) |
| Rubrikalar (haftalik ritm) | Du: yo'nalish xaritasi · Chor: haydovchi hikoyasi · Pay: "Juma bozor qatnovi" · Sha: so'rovnoma | Takrorlanuvchi rejalashtirish (2025-11) |
| So'rovnomalar | Faqat O'zbekistondan, rasm bilan | `country_codes`, poll media (10.0) |
| Ko'rinish | Boost bilan: sariq profil rangi, TulporGo emoji paketi | boost darajalari |

## 3. Savol-javob guruhi @tulporgo_chat — "qabulxona"

| Element | Taklif | Yangi imkoniyat |
|---|---|---|
| Avatar | 02 oq fonda (31-qaror) | — |
| Welcome Message | Qoidalar (5 qator) + FAQ tugmalari | Welcome Messages |
| Bot javoblari | Menyu va xatolar faqat so'raganga ko'rinadi | Ephemeral messages (10.2) |
| A'zo teglari | "Haydovchi", "Admin", "Yo'lovchi" | Member Tags (9.5) |
| Moderatsiya | Spam reaksiyalarini o'chirish, flood nazorati | `deleteAllMessageReactions` (10.0) |

## 4. Haydovchilar guruhi (username'siz, Hidden) — "ishxona"

| Element | Taklif | Yangi imkoniyat |
|---|---|---|
| Avatar | Qora fon + 02 + kichik rul belgisi (31-qaror) | — |
| Qo'shilish | So'rov → bot Mini App'da telefon, mashina, guvohnoma (12-qaror) → tasdiq | AI Guardian / Join Request Queries (10.1) |
| Teglar | "Tasdiqlangan", tarif (Asosiy/Pro/Biznes), tuman | Member Tags (9.5) |
| Bot xabarlari | "E'loningiz 12 guruhga yuborildi" — faqat o'ziga | Ephemeral |
| Xavf | Ega ketsa, egalik 1 haftada adminga o'tadi — adminlar faqat oila a'zolari (19-qaror) | — |

## 5. Hamjamiyat "TulporGo"

| Element | Taklif |
|---|---|
| Tarkib | Bot + kanal + savol-javob (Visible) + haydovchilar (Hidden) |
| Chat qo'shish | **Faqat adminlar** (standart holatda istalgan a'zo qo'sha oladi — o'chiriladi) |
| Ro'yxatda | Bitta element bo'lib ko'rinadi |

## 5a. Emoji tizimi — **qabul qilindi 2026-11-10 (39-qaror)**

| Qatlam | Qayerda | Nima bilan |
|---|---|---|
| Katta | Salomlashuv, bayram, muhim xabar | Stiker yoki yakka emoji (Telegram katta ko'rsatadi) |
| Hissiyot | Matn ichida, reaksiya | Tulpor **boshi** emoji (Reactions, 24 ta) |
| Interfeys | Tugma, 1-2-3, ro'yxat | **A**: TulporGo belgilari (`brand/icons/`, 14 ta konsept) yoki **B**: Telegram rasmiy «Animated Emoji» |

Qaror: A asos + xabarda ko'pi bilan 1 ta rasmiy animatsion urg'u (🚀 🎉 ⏳ 🔥) — `build_texts.py` tekshiradi.
Kod: `content/i18n/emoji_system.py` (rollar → id), `build/emoji_map.json`. Taqqoslash: `brand/mascot/poses/review/emoji-a-b-tavsiya.png`.
Sinov uchun 15 ta emoji `tulporgo_emoji_by_tulporgobot` ga **vaqtincha** qo'shilgan (51 → 66). `tulporgo_icons` paketi (va Reactions) yaratilgach — id'lar o'sha paketlarga
ko'chiriladi, keyin `python brand/icons/test_in_pack.py remove` (faqat shu 15 tasi o'chadi).

## 6. Bajarish tartibi (tavsiya)

| Bosqich | Nima | Kim | Tashqi e'lonmi |
|---|---|---|---|
| 1 | Matnlar: bot tavsiflari (5 til), kanal tavsifi, welcome matnlari, qoidalar — **2026-11-10 TASDIQLANDI (40-qaror)** (`content/i18n/`) | Claude qoralama → Saidakbar aka tasdiq | Yo'q |
| 2 | Vizuallar: 4 avatar, welcome rasmlari, qadalgan karusel — **2026-11-10 TASDIQLANDI (41-qaror)** (`brand/telegram/`: `avatars.py`, `visuals.py`, `send_stage2.py`) | Claude render → bot orqali ko'rsatish → tasdiq | Yo'q |
| 3 | Bot profili API orqali (avatar, tavsif, buyruqlar, menyu tugmasi) + minimal "tez orada" javob — **2026-11-10 O'RNATILDI**: avatar, nom, qisqa tavsif, tavsif (default/uz = yangi alifbo, ru, en), 4 buyruq; qayta o'qib tekshirildi (`content/i18n/apply_bot_profile.py`, zaxira `build/bot_profile_before.json`). **Qolgan:** menyu tugmasi (Mini App yo'q), «tez orada» javobi — **2026-11-10 ISHLAYAPTI** (`bot/coming_soon.py`, Windows vazifasi, /start → 2,1 s), haydovchi buyruqlari (bot kodi bilan) | Claude | Ha — bot ochiq profil |
| 4 | Kanal va 2 guruhni yaratish, avatar, tavsif, welcome, qoidalar — **2026-11-10 YARATILDI (yopiq)**: kanal -1004318662356, savol-javob -1003927240939, haydovchilar -1004314040452 (`brand/telegram/chats.json`); avatar, «Haqida», bot admin, a'zo huquqlari (teg/mavzu yopiq; haydovchilarda taklif yopiq) — Bot API bilan tekshirildi. 2026-11-10 `tg_admin.py` (alohida admin sessiya) bilan: Welcome Message ×3, Hamjamiyat (haydovchilar yashirin, chat qo'shish faqat adminlarga), **kanal ochiq: @tulporgo** — tekshirildi. **@tulporgo_chat ham ochiq** (limit sabab @rankwant_chat hozircha yopiq qilindi). 4-bosqich BAJARILDI | @menarzullayev hisobidan — ruxsat bilan | Ha |
| 5 | Hamjamiyatga birlashtirish, chat qo'shishni cheklash | Ega | Ha |
| 6 | Birinchi 3 post va qadalgan post — reklama boshlanmaguncha jim (e'lonsiz) | Tasdiq bilan | Ha |
