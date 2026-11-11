# TulporGo — Maxfiylik siyosati

> **QORALAMA, 2026-11-10.** Yurist tekshiruvidan o'tmagan va kuchga kirmagan (51-qaror).
> `[yurist: …]` belgili joylar yurist bilan aniqlanadi va to'ldiriladi.

## 1. Kim va qaysi qonun asosida

1.1. Shaxsga doir ma'lumotlaringizni `[yurist: Operator — F.I.Sh. yoki yuridik shaxs, STIR, manzil]` («Operator»)
TulporGo servisi (@tulporgobot, Mini App, avto-e'lon) orqali qayta ishlaydi.

1.2. Asos: O'zbekiston Respublikasining «Shaxsga doir ma'lumotlar to'g'risida»gi Qonuni (O'RQ-547, 2019-yil
2-iyul) va unga kiritilgan o'zgartishlar `[yurist: tekshirish; ma'lumotlar bazasini davlat reyestrida ro'yxatdan
o'tkazish talabi]`.

## 2. Qanday ma'lumotlar yig'iladi

| Kimdan | Ma'lumot | Qayerdan |
|---|---|---|
| Hammadan | Telegram ID, ism, username, interfeys tili | Telegram avtomatik yuboradi |
| Hammadan | Telefon raqami | siz «Kontaktni yuborish» tugmasini bossangiz |
| Saytdan Telegram orqali kirganlardan | Telegram ID, ism, username (profil rasmi saqlanmaydi); @tulporgobot sizga qatnov xabarlarini yuborishiga ruxsat — agar Telegram oynasida rozi bo'lsangiz (65-qaror). Ruxsatni botni bloklab bekor qilasiz | Telegram'ning kirish oynasi, siz tasdiqlaganda |
| Yo'lovchidan | Ayol yo'lovchi belgisi | ixtiyoriy, o'zingiz belgilaysiz |
| Yo'lovchidan | So'rov: qayerdan, qayerga (tuman, mahalla yoki xaritada o'zingiz tanlagan nuqta), vaqt, odam soni, izoh | siz kiritasiz |
| Hammadan | Takliflar, narxlar, qatnovlar holati, baholar, izohlar, shikoyatlar | Servisdagi harakatlaringiz |
| Haydovchidan | Avtomobil rusumi, rangi, davlat raqami, rasmi; uy hududi | siz kiritasiz |
| Haydovchidan | Haydovchilik guvohnomasi va texnik pasport rasmlari | «Tasdiqlangan» belgisi uchun yuborsangiz |
| Haydovchidan | Obuna, to'lovlar: summa, usul, holat, to'lov tizimidagi tranzaksiya raqami; P2P chek rasmi | to'lov paytida |
| Haydovchidan (avto-e'lon) | Telegram sessiyasi (shifrlangan), Telegram hisob ID, tanlangan guruhlar, yuborilgan e'lonlar jurnali, cheklov holati | hisobingizni ulasangiz |

**Yig'ilmaydi:** karta raqami va CVV (ular Click, Payme yoki Telegram tomonida kiritiladi), Telegram login kodi va
ikki bosqichli parol (faqat kirish paytida ishlatiladi, saqlanmaydi va loglarga yozilmaydi), joriy joylashuvingiz
(faqat o'zingiz tanlagan nuqtalar), shaxsiy yozishmalaringiz.

Server loglarida texnik ma'lumotlar (so'rov vaqti, IP manzil) qisqa muddat — log fayllari almashguncha saqlanadi.

## 3. Nima uchun

- so'rovingizni mos haydovchilarga yetkazish va takliflarni ko'rsatish;
- xavfsizlik: haydovchini tasdiqlash, reyting, shikoyatlar, qora ro'yxat, qatnovni ulashish;
- haydovchi obunasi va to'lovlarni hisobga olish;
- haydovchining avto-e'lonlarini u tanlagan guruhlarga yuborish;
- Servisni yaxshilash uchun umumlashtirilgan statistika (shaxsni aniqlamaydigan ko'rinishda);
- qonun talablarini bajarish.

## 4. Ma'lumotlarni kim ko'radi

- **Haydovchilar** — yo'lovchi so'rovini: yo'nalish, vaqt, odam soni, izoh, ayol yo'lovchi belgisi.
- **Yo'lovchi** — taklif bergan haydovchining ismi, avtomobili (rusum, rang, davlat raqami, rasm), reytingi va
  «Tasdiqlangan» belgisi.
- **Qatnov tomonlari** — taklif qabul qilingandan keyin haydovchi va yo'lovchi bir-birining ismini, telefon raqamini
  (agar ulashilgan bo'lsa) va Telegram username'ini ko'radi — faqat o'sha qatnovning kartasida.
- **Ulashish havolasini ochgan kishi** — yo'nalish, avtomobil, haydovchining ismi, qatnov holati. Telefon raqami yo'q.
- **Operator va uning topshirig'i bilan ishlaydigan shaxslar** — hujjatlarni tekshirish, shikoyat va to'lovlarni
  ko'rib chiqish uchun.
- **To'lov tizimlari** (Click, Payme, Telegram Stars) — faqat to'lovni bajarish uchun zarur ma'lumot.
- **Telegram** — Servis Telegram ichida ishlaydi; xabarlar Telegram serverlari orqali o'tadi va Telegram'ning
  maxfiylik siyosatiga bo'ysunadi.
- **Davlat organlari** — faqat qonunda belgilangan hollarda va tartibda.

Ma'lumotlaringiz sotilmaydi va reklama uchun uchinchi shaxslarga berilmaydi.

## 5. Qayerda saqlanadi

O'zbekiston fuqarolarining shaxsga doir ma'lumotlari **O'zbekiston hududidagi serverda** saqlanadi (43-qaror).

Haydovchi hujjatlari (guvohnoma, texpasport) rasmlari O'zbekistondagi serverda **shifrlangan** holda saqlanadi;
tekshiruv qulayligi uchun nusxasi Telegram'ning yopiq chatida ham turadi (57-qaror). Hujjat rad etilsa, server
nusxasi 7 kun saqlanadi (e'tiroz yoki qayta ko'rib chiqish uchun), so'ng avtomatik o'chiriladi (63-qaror).
Ma'lumotlarni o'chirishni so'rasangiz, server nusxasi darhol o'chiriladi.

Oylik zaxira nusxa serverda shifrlanib, Cloudflare R2'ga ham ko'chiriladi; shifr kaliti O'zbekistonda qoladi
(58-qaror). `[yurist: Telegram nusxasi va shifrlangan xorijiy zaxira lokalizatsiya talabiga mosmi]`

## 6. Qancha saqlanadi

- Hisob ma'lumotlari — hisob faol ekan; o'chirish so'ralsa — `[yurist: N]` kun ichida o'chiriladi.
- Zaxira nusxa — oyiga bitta, faqat oxirgisi saqlanadi (serverda va shifrlangan holda R2'da).
- Avto-e'lon sessiyasi — «Hisobni uzish» bosilganda darhol o'chiriladi.
- To'lov yozuvlari — `[yurist: buxgalteriya va soliq qonunchiligidagi muddat]`.
- Shikoyat va bloklash yozuvlari — `[yurist: muddat]` (qayta ro'yxatdan o'tib qoidani chetlab o'tishning oldini olish uchun).

## 7. Qanday himoya qilinadi

- sayt va API faqat HTTPS orqali;
- avto-e'lon sessiyalari shifrlangan holda saqlanadi, kalit alohida turadi;
- serverga kirish cheklangan, xavfsizlik yangilanishlari avtomatik o'rnatiladi;
- kunlik zaxira nusxa olinadi va tiklanishi muntazam tekshiriladi.

## 8. Sizning huquqlaringiz

Siz quyidagilarni so'rashingiz mumkin:

- qanday ma'lumotingiz saqlanayotganini bilish va nusxasini olish;
- noto'g'ri ma'lumotni tuzatish;
- ma'lumotlaringizni o'chirish va rozilikni qaytarib olish (bunda Servisdan foydalanish to'xtaydi);
- avto-e'lonni istalgan vaqtda «Hisobni uzish» orqali to'xtatish.

So'rovni bot orqali yuboring: botdagi `/malumotlarim` buyrug'i (yuklab olish va o'chirish) yoki
info@tulporgo.uz (pochta manzili: `[yurist: pochta manzili]`). Javob muddati — `[yurist: N]` kun.

## 9. Bolalar

`[yurist: yosh chegarasi va ota-ona roziligi tartibi]`.

## 10. O'zgarishlar

Siyosat o'zgarsa, yangi matn bot va @tulporgo kanalida e'lon qilinadi.

## 11. Aloqa

- Bot: [@tulporgobot](https://t.me/tulporgobot)
- Email: info@tulporgo.uz
- `[yurist: Operator manzili]`
