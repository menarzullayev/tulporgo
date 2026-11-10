# Vektor bosqichi: duch kelingan muammolar va holati (2026-11-09)

Natija: 51 ta poza (50 + 37t) → `ai/*.ai`, `svg/*.svg`, `png/*.png` (1024 px, shaffof fon, bir xil oq stiker hoshiya).
Yakuniy tekshiruv `check_final.py`: 51/51 OK (magenta yo'q, burchaklar shaffof, hoshiya bor, chetga tegmaydi, to'ldirish 94%).

## Ish jarayonida topilgan va TUZATILGAN muammolar

| # | Muammo | Sabab | Tuzatish | Test |
|---|---|---|---|---|
| 1 | Manba fayllar 2 xil o'lchamda (895 va 927 px) | ChatGPT'dan turli vaqtda olingan | Hammasi 895 px ga keltirildi (`src/`) | — |
| 2 | PowerShell skript ishlamadi | Tizimda `ExecutionPolicy` taqiq | Har chaqiruvda `-ExecutionPolicy Bypass` (tizim sozlamasi o'zgartirilmadi) | — |
| 3 | 51 tadan faqat 6 tasi trace qilindi | bash massivi PowerShell `[string[]]` ga bitta qator bo'lib uzatildi; batch.txt BOM bilan yozildi | Nomlar vergul bilan uzatiladi, BOM'siz UTF-8 | Quvurda "trace soni = 51" tekshiruvi, aks holda to'xtaydi |
| 4 | Ko'rinmas oq-kulrang halqa (soya) hoshiya atrofida | Trace soyani alohida shakl qildi | Halqa olib tashlandi; keyin butunlay yangi hoshiya usuliga o'tildi | — |
| 5 | Gradient fonli pozalarda (31, 50) fon qoldi | Fon rangi bitta burchakdan olinardi | Fon chetning 8 nuqtasidan olinadi | `test_clean_bg.py` (gradient + salbiy) |
| 6 | Fon mayda "orol"larga bo'linib, qoldiq dog'lar qoldi | Shakl bo'yicha ajratish ishonchsiz | **Yangi usul:** trace'dan oldin tashqi fon magentaga bo'yaladi, keyin faqat magenta o'chiriladi (`prep_src.py`, `drop_magenta.py`) | `test_prep_src.py`, `test_drop_magenta.py` |
| 7 | Fondagi shovqin dog'lari bo'yalmadi | JPEG shovqini | Median filtr + niqobni yopish (closing) | `test_prep_src.py` |
| 8 | Oq fonli pozalarda asl oq hoshiya fon bilan qo'shilib ketdi | Oq fon va oq hoshiya farqlanmaydi | Asl hoshiya ataylab olib tashlanadi, **hammasiga bir xil yangi hoshiya** qo'shiladi (Offset Path 14 pt) | `test_prep_src.py` (qora kontur ichini saqlash) |
| 9 | Eksport "ERR Object is invalid" ko'rsatdi | Log yopilgan hujjatga murojaat qildi (fayllar aslida yozilgan) | Log tuzatildi | — |
| 10 | Solishtirish eski PNG'ni "OK" dedi | Fayl sanasi tekshirilmagan | STALE tekshiruvi qo'shildi | — |
| 11 | Tasodifiy Illustrator xatosi `PARM` (24, 45, 50) | Illustrator ichki xatosi, takrorlanmaydi | Yetishmagan fayllar avtomatik qayta ishlanadi | Quvurda retry |
| 12 | 28, 32: hoshiya kanvas chetida kesildi | Rasm chetga tegib turardi | Hamma poza kanvasning 94% iga sig'diriladi va markazlanadi | `check_final.py` (+ salbiy test) |
| 13 | 11, 44, 45, 47 boshqalardan kichik | Qayta chizilganda ko'p joy qoldirilgan | 12-banddagi normallashtirish bir xil o'lcham berdi | `check_final.py` (fill 94%) |
| 14 | Masshtablashdan keyin piksel solishtirish ma'nosiz bo'ldi | Rasm siljidi | `compare.py` o'rniga `check_final.py` | salbiy test |
| 15 | Fon jarayonida eski skript ishga tushib ketdi | Fayl yangilanishi rad etilgan, men tekshirmay ishga tushirdim | To'xtatildi, fayllar to'g'ridan-to'g'ri qayta tekshirildi | magenta/sana/hoshiya tekshiruvi 51/51 |

## A–G: 2-bosqich tuzatishlari (2026-11-09, pipeline v3) — HAMMASI YOPILDI

| # | Muammo | Tuzatish | O'lchov | Test |
|---|---|---|---|---|
| A | Och detallar fon bilan o'chgan (23, 25, 26, 31) | `prep_overrides.txt`: shu pozalar uchun fon chegarasi 40 → 12 | 25, 26 qor parchalari, 23 masjid silueti qaytdi. 31 nafas izi oq bo'lgani uchun oq hoshiya ichida deyarli ko'rinmaydi (vizual tekshiruv) | `test_low_threshold_keeps_light_detail` (salbiy: 40 da yo'qoladi) |
| B | Konfetti/qor alohida hoshiya orolchalari | Hoshiya = vektor "closing": birlashtirish → +38 pt → yana birlashtirish → −24 pt | Orollar: oldin 12 pozada 2–9 ta → **51/51 da 1 ta** | `check_final.py` islands ≤ 4 (+ salbiy test; eski natija 4 ta pozada yiqildi) |
| C | Oyoq ostidagi soya | Emoji uchun `svg_ns/`, `png_ns/` varianti: past 18% dagi tekis, kulrang/binafsha shakllar o'chiriladi | 47 pozada 1–10 ta soya shakli o'chirildi; qor/o'tlar saqlandi (vizual tekshiruv) | `check_final.py --dir png_ns` 51/51 |
| D | To'lqinli kontur, ko'p shakl, katta SVG | Trace sozlamalari `24,90,75,8` → `24,50,50,25`; SVG aniqligi 0.1 | Shakllar ~22% kam; SVG jami 11 MB → 6.8 MB; aniqlik farqi o'rtacha 5.0/255 | `compare_trace.py` |
| E | Brend palitrasi yo'q | `brand_snap.py`: model sheet 09 ranglariga yaqin (≤26) ranglar aniq brend rangiga | Personaj ranglari 2660 xil → 13 ta aniq brend rangi; yashil/qizil/binafsha o'zgarmaydi | `test_brand_snap.py` (2 ta salbiy) |
| F | Telegram talablari | `telegram_export.py` → `telegram/`: sticker 512 WEBP+PNG, emoji 100 PNG (soyasiz), video 512 WEBM, video emoji 100 WEBM (2 s "sakrash" animatsiyasi) | `telegram_check.py` 51/51; eng katta: stiker 276 KB (≤512), video 140 KB (≤256), video emoji 20 KB (≤64) | `test_telegram.py` (3 ta salbiy) |
| G | Huquqiy tekshiruv | `brand/mascot/HUQUQIY-TEKSHIRUV.md`: yuristga savollar, MKTU sinflari, dalillar ro'yxati, manbalar | — (yurist bilan tekshirish Saidakbar aka tomonida) | — |

### 2-bosqichda yangi chiqqan muammolar (tuzatildi)

| # | Muammo | Sabab | Tuzatish |
|---|---|---|---|
| 16 | Birinchi v3 ishga tushirishda hoshiya umuman chiqmadi (border 0–5/8) | Offset effekti qo'yilgandan keyin obyekt qayta tanlanmadi — `expandStyle` effektni qo'llamadi | Har effektdan keyin qayta tanlash; yangi tekshiruv buni ushladi |
| 17 | Hoshiya orolchalari birlashmadi | Offset har bo'lakka alohida qo'llandi | Kattalashtirishdan keyin Pathfinder Add |
| 18 | Binafsharang soya (11) qoldi | Soya rangi to'yinganligi chegarasi 22 juda tor | Chegara 40 ga kengaytirildi, qor saqlanishi vizual tekshirildi |
| 19 | Eksport kirish va chiqish fayli bir xil edi (`svg/`) | Qayta eksportda hoshiya ikki marta qo'shilishi mumkin edi | Toza fayllar `clean/` ga, natija `svg/` ga |
| 20 | PIL flood fill chegarasi kanallar yig'indisi ekan | Test noto'g'ri rang bilan yozilgan edi | Test tuzatildi, izoh qo'shildi |

## Hali ham ochiq (avtomatlashtirib bo'lmaydi)

- D: kontur to'liq tekis emas — bosma/katta format (bilbord, merch) uchun asosiy 5–10 pozani dizayner qo'lda qayta chizishi kerak.
- Emoji 100 px: murakkab pozalar (21, 22, 25, 32, 45) kichik o'lchamda o'qilishi qiyin — emoji paketi uchun oddiy pozalarni tanlash tavsiya.
- TGS (Lottie) animatsiya qilinmadi — WEBM tanlandi; vektor TGS kerak bo'lsa alohida bosqich.
- Telegram paketlari yaratildi (2026-11-09, Saidakbar aka tasdig'i bilan): `tulporgo_by_tulporgobot`, `tulporgo_anim_by_tulporgobot`, `tulporgo_emoji_by_tulporgobot` — har birida 51 ta. Skript: `content/prototype/create_sticker_sets.py`.

Skriptlar: `prep_src.py` (+`prep_overrides.txt`), `trace_poses.jsx`, `compare_trace.py`, `drop_magenta.py`, `brand_snap.py`, `export_poses.jsx`, `check_final.py`, `telegram_export.py`, `telegram_check.py`, `pipeline.sh`, `reexport.sh`, `run.ps1`; testlar `test_*.py`.

## Emoji sifati: vektor TGS (2026-11-09, Saidakbar aka tanlovi: B — butun tana)

Muammo: custom emoji 100×100 PNG edi — katta ko'rinishda ~190 fizik px ga cho'zilib xira bo'ldi.
Yechim: emoji paketi **vektor TGS** ga o'tkazildi (Telegram o'zi chizadi, har o'lchamda tiniq), havola o'zgarmadi
(`replaceStickerInSet`, joyida almashtirish).

| Qadam | Skript | Natija |
|---|---|---|
| SVG → Lottie | `lottie_convert.py` (python-lottie 0.7.2) | 51 ta |
| Hajm | `tgs_optimize.py`: bir xil rangli yo'llar bitta guruhga, koordinatalar butun songa (rang 3 xona) | 01: 28 → 17 KB, ko'zga farq yo'q |
| Murakkab 5 ta sahna (22, 25, 26, 27, 32) | `prep_emoji.py` (median 9, 64 rang) + trace `24,20,20,100` → `svg_em/` | 42–53 KB |
| Hoshiyadagi kichik teshiklar | `fill_holes.py` (SVG ichida, <2% teshiklar) | 13-pozadagi qora dog'lar yo'qoldi |
| Tekshiruv | `telegram_check.py` (TGS: 512 kanvas, 60 fps, ≤3 s, ≤64 KB) | 51/51, eng kattasi 63 KB |

### Shu bosqichda topilgan xatolar

| # | Muammo | Sabab | Tuzatish | Test |
|---|---|---|---|---|
| 21 | TGS ranglari buzildi (sariq → och sariq, oq) | Butun songa yaxlitlash 0–1 oralig'idagi ranglarga ham tegdi | Rang `c` doim 3 xona | `test_colours_survive_integer_rounding` |
| 22 | 13-pozada hoshiya ichida qora dog'lar | Hoshiyada kichik teshiklar; Illustrator'da o'chirish SVG eksportga yetmadi | `fill_holes.py` SVG faylning o'zida | `test_fill_holes.py` (katta ochiqlik saqlanadi — salbiy) |
| 23 | "ns" eksporti `_em` papkaga yozildi | ExtendScript ichma-ich ternary (`a ? b : c ? d : e`) ni noto'g'ri hisoblaydi | if/else | qo'lda o'lchandi (papka vaqti) |
| 24 | Bir qatordagi izoh `paint(border)`ni o'chirib qo'ydi — hoshiya oq bo'lmadi | Tahrirda `//` izoh buyruqlar bilan bir qatorda qoldi | Izoh alohida qatorga | `check_final` + vizual |
| 25 | Bot API 429 (275 s) | Ko'p ketma-ket `replaceStickerInSet` | 60 s dan uzun kutishda to'xtaydi; davomi `TG_MAX_WAIT`/`TG_PACE` bilan sekin | — |

Cheklov: TGS faqat Telegram ilovalarida; 5 ta murakkab sahna soddalashtirilgan trace'dan (mayda tekstura kamroq).

## TulporGo Reactions (bosh emoji, 2-paket) — YOPILDI 2026-11-11

| # | Muammo | Sabab | Holat |
|---|---|---|---|
| 26 | `createNewStickerSet` doim `429 retry after 301` (2026-11-09 22:20 dan 2026-11-10 04:08 gacha 6 urinish) | Bot bir kunda 3 ta yangi paket yaratgan; `retry_after` har safar aynan 301 — kunlik yaratish limiti bo'lishi ehtimoli | Yaratilmadi. 24 TGS tayyor: `telegram/emoji_head_tgs/`. Keyingi urinish: ertasi kun, bitta, `TG_MAX_WAIT=0`. 2026-11-10: ikki urinish bir vaqtda ketmasligi uchun `attempt_guard.py` qo'shildi — har urinish `create_attempts.json` ga oldindan yoziladi, 20 soat ichida ikkinchisi rad etiladi (`test_attempt_guard.py`, 9 test). **2026-11-11 00:30: 7-urinish ham `429 retry after 301`** — 3 paket yaratilganidan 24 soatdan ko'p o'tgan bo'lsa ham; demak oddiy kunlik limit emas. 10:00 dagi rejalashtirilgan vazifa planlashtiruvchida yo'q edi (fayl bor, ro'yxatda yo'q). **Yechim (2026-11-11 00:54):** @Stickers orqali Saidakbar aka hisobidan yaratildi — `tulporgo_reactions`, 24 animatsiyali emoji, Bot API bilan tekshirildi: https://t.me/addemoji/tulporgo_reactions |

## Statik va video stikerlardagi hoshiya teshiklari (2026-11-10) — YOPILDI

| # | Muammo | Sabab | Tuzatish | O'lchov | Test |
|---|---|---|---|---|---|
| 27 | Statik va video paketda 10 ta pozada oq hoshiya ichida qora dog'lar (13, 17, 18, 24, 26, 27, 31, 38, 42, 44) | `png/` Illustrator rastri `fill_holes.py` dan oldin eksport qilingan; `fill_holes` faqat TGS manbasi (`svg_ns/`, `svg_em/`) ga qo'llangan edi | `png_holes.py`: chetga tegmaydigan, shaffof (alpha < 128) va noshaffof maydonning 2 % idan kichik joy — teshik; teshik va uning 3 px chekkasi oq ustiga kompozitsiya qilinadi, tashqi fonga tegilmaydi. `telegram_export.py` uni har eksportda qo'llaydi; `telegram_check.py` sticker PNG/WEBP da teshik bo'lsa yiqiladi | Teshiklar 15 → 0 (1024 px). O'zgargan piksellar faqat teshik zonasida (zonadan tashqarida 0). 40, 47 dagi katta ochiqliklar saqlandi. Telegram'dan qayta yuklab olingan 10+10 faylda teshik 0. Ikkala paket 51/51, `replaceStickerInSet` bilan joyida | `test_png_holes.py` (8, 4 tasi salbiy, mutatsiya bilan tekshirildi), `test_telegram.py::test_border_hole_fails_and_export_fill_passes` |
| 28 | `fill_holes.py` `svg/` da yiqildi: `RuntimeError: Could not compute Path.point(0.0025)` | `svg/09-13` da nol uzunlikdagi subpath (bitta nuqta); `svgpathtools` unda nuqta hisoblay olmaydi | Bunday subpath maydoni 0 deb olinadi | 22 ta `svg/` faylida dry-run o'tdi | `test_fill_holes.py::test_zero_length_subpath_does_not_crash` (tuzatishsiz yiqiladi) |

Asl fayllar: `telegram/_before_holes_2026-11-10/` (qaytarish kerak bo'lsa: `create_sticker_sets.py replace static|video <names>` shu fayllar bilan). Ko'rib chiqish: `poses/review/holes-before-after.png`.
`svg_ns/09-10` da `fill_holes` bo'yicha yana 1 ta teshik bor, lekin `png_ns/` rastrida ko'rinmaydi (art ostida) — chora shart emas.

## TulporGo belgilari: vektor TGS + animatsiya (2026-11-10) — YOPILDI

| # | Muammo | Sabab | Tuzatish | Test |
|---|---|---|---|---|
| 29 | Belgilar 100 px statik PNG edi — kattalashtirganda xira, harakatsiz | Konsept tez ko'rsatish uchun rastr qilingan | `brand/icons/icons_tgs.py`: vektor TGS, 60 fps, 3 s loop, 0,4–1,3 KB; raqamlar Arial Black konturidan path (Text taqiqlangan) | `test_icons_tgs.py` (32) |
| 30 | Pin kadr ichida yuqoriga chiqib, kesilib turardi | Guruh transformida `p` anchor (12, 19.5) ga nisbatan emas, markazga nisbatan berilgan | `p` qiymatlari anchor'dan hisoblandi | kadrlar varag'i `brand/icons/review-frames.png` |
| 31 | Birinchi kadrda ✓ bo'sh, raqamlar kichik, megafon to'lqini yo'q | Animatsiya 0-kadrdan boshlangan; quvvat tejash rejimida Telegram faqat 0-kadrni ko'rsatadi | Qoida: 0-kadr = dam holati = oxirgi kadr; harakat 1-kadrdan | `loop_problems()` + 3 ta salbiy test |
| 32 | `replaceStickerInSet` 10 tadan keyin `HTTP Error 429: Too Many Requests` | Ketma-ket tez almashtirish (2 s pauza) | `create_sticker_sets.call` (retry_after kutadi, `TG_MAX_WAIT`) + 8 s pauza; qolgan 4 tasi shu bilan o'tdi | — |
| 33 | Rasmiy TGS taqiqlari tekshirilmas edi | `check_tgs` faqat kanvas/fps/hajmni ko'rardi | `tgs_forbidden()`: 14 taqiq (text, mask, effect, image, solid, 3D, merge, star, gradient stroke, repeater, expression, time remap/stretch, auto-orient); 89 ta TGS'ning hammasi toza | `test_telegram.py` (har taqiq salbiy) |
