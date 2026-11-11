# Legal drafts (decision 51)

Claude drafts, a lawyer reviews before the public launch. **Nothing here is in force yet.**

| File | Uzbek | Russian |
|---|---|---|
| Terms of use | [terms.uz.md](terms.uz.md) | [terms.ru.md](terms.ru.md) |
| Privacy policy | [privacy.uz.md](privacy.uz.md) | [privacy.ru.md](privacy.ru.md) |
| Userbot consent screen (decisions 8, 48) | [userbot-consent.uz.md](userbot-consent.uz.md) | [userbot-consent.ru.md](userbot-consent.ru.md) |

Every product fact comes from `QARORLAR.md`. The owner answered the questions below on 2026-11-11 (decision 67)
and the answers are in the texts. The owner's full name and postal address are not in this public
repository: the texts keep `[ega: F.I.Sh.]` / `[ega: pochta manzili]` (ru: `[владелец: ФИО]` /
`[владелец: почтовый адрес]`) and the page fills them in from `TULPORGO_OPERATOR_NAME` / `_ADDRESS` on the
server (owner's copy: `.secrets/operator.env`; `tools/secret_scan.py` refuses a commit that contains them). PINFL
is not published. The texts stay drafts until a
licensed lawyer has read them.

## Questions for the lawyer (answered by the owner, see below)

1. **Operator.** There is no YATT or MChJ yet (decision 11). Who is the operator of the personal-data database and
   the party to the subscription payments until a legal entity exists?
2. **Personal data law** (ZRU-547, 2019): is registration of the database in the state register required, and what
   must the consent wording contain?
3. **Localisation (art. 27-1).** The database and backups are on a VPS in Uzbekistan (decision 43). Open point:
   driver document photos are currently stored in a private Telegram chat (only the `file_id` is kept) — is that
   acceptable, or must the files be stored encrypted on the Uzbek server instead?
4. **Intermediary status** (decision 15): wording that TulporGo is not a carrier; what drivers must hold for
   passenger transport (licence, permits, insurance) and how far the platform has to check it.
5. **Subscriptions:** refund terms, notice period for price changes, consumer-protection requirements; Telegram Stars
   rules require `/terms`, `/paysupport` and explicit acceptance of the terms before a purchase.
6. **Userbot:** liability wording when Telegram limits a driver's account.
7. Minimum age for passengers; retention periods for payment records, complaints and bans; response deadline for
   data-subject requests.
8. **Backups abroad (decision 58):** monthly database backups are also copied to Cloudflare R2 (outside Uzbekistan),
   encrypted on our server with the key kept in Uzbekistan. Is an encrypted copy abroad compatible with art. 27-1?
9. **Mailbox abroad (decision 64):** the contact address `info@tulporgo.uz` is hosted by Zoho Mail (servers outside
   Uzbekistan). Data-subject requests sent there contain personal data. Is that acceptable under art. 27-1, or must
   such requests be moved to the Uzbek server and deleted from the mailbox (a local mail host is the alternative)?

## Owner's answers (decision 67, 2026-11-11)

| # | Answer | In the texts |
|---|---|---|
| 1 | The founder (a natural person) is the operator; once an MChJ/YATT exists it becomes the operator. Payments go through third-party providers (Telegram Stars, Click, Payme) | terms 1.2, privacy 1.1 |
| 2 | The database is registered in the state register once the MChJ/YATT exists | privacy 1.2 |
| 3 | Driver documents stay in the private Telegram chat; the encrypted server copy (decision 57) stays too | privacy 5 |
| 4 | Information intermediary; the driver holds and answers for permits, licence and insurance | terms 5.1 |
| 5 | No refunds except where the law requires; price changes announced 7 days ahead; `/terms`, `/paysupport`, acceptance before a Stars purchase (built) | terms 6.7, 6.8 |
| 6 | The platform is not liable for Telegram limiting a driver's account; separate risk warning and consent (built: userbot consent screen) | terms 7.2, userbot consent |
| 7 | Minimum age 16 | terms 3.3, privacy 9 |
| 8 | Encrypted backups are kept in Cloudflare R2; the copies abroad are disclosed | privacy 5, 6 |
| 9 | Keep Zoho Mail | terms 14, privacy 8, 11 |
| — | Retention: payment records — statutory period; complaints — by law and the nature of the dispute; bans — while legally necessary. Data requests answered within 10 days (deletion through the bot is immediate) | privacy 6, 8 |

## To build before launch (tracked in PROGRESS.md)

- ~~Bot: "Ma'lumotlarim" — export and delete own data (privacy §8).~~ Done: `/malumotlarim`.
- ~~`/terms` and `/paysupport` commands, terms acceptance before payment (W4).~~ Done (`tulporgo_payments/bot.py`).
- ~~Public pages~~ Done: `https://tulporgo.uz/legal/<terms|privacy|userbot-consent>?lang=uz|ru` render these files; replace the drafts after review.
- ~~Compare §4 of the privacy policy ("who sees what") with the merged bot behaviour.~~ Done (trip card: name, phone, username).
