# Legal drafts (decision 51)

Claude drafts, a lawyer reviews before the public launch. **Nothing here is in force yet.**

| File | Uzbek | Russian |
|---|---|---|
| Terms of use | [terms.uz.md](terms.uz.md) | [terms.ru.md](terms.ru.md) |
| Privacy policy | [privacy.uz.md](privacy.uz.md) | [privacy.ru.md](privacy.ru.md) |
| Userbot consent screen (decisions 8, 48) | [userbot-consent.uz.md](userbot-consent.uz.md) | [userbot-consent.ru.md](userbot-consent.ru.md) |

Every product fact comes from `QARORLAR.md`. Places marked `[yurist: …]` / `[юрист: …]` are for the lawyer.

## Questions for the lawyer

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

## To build before launch (tracked in PROGRESS.md)

- ~~Bot: "Ma'lumotlarim" — export and delete own data (privacy §8).~~ Done: `/malumotlarim`.
- `/terms` and `/paysupport` commands, terms acceptance before payment (W4).
- ~~Public pages~~ Done: `https://tulporgo.uz/legal/<terms|privacy|userbot-consent>?lang=uz|ru` render these files; replace the drafts after review.
- ~~Compare §4 of the privacy policy ("who sees what") with the merged bot behaviour.~~ Done (trip card: name, phone, username).
