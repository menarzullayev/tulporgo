# TulporGo

Telegram-native taxi service for Uzbekistan (bot + Mini App + driver userbots), launching in Samarqand
(Qo'shrabot). Passengers post a route, drivers send offers with price and car, the passenger picks one.

- Bot: [@tulporgobot](https://t.me/tulporgobot) · Channel: [@tulporgo](https://t.me/tulporgo) · Q&A: [@tulporgo_chat](https://t.me/tulporgo_chat)
- Status: brand, Telegram presence and content pipeline are done; the product is being built — see [`GOAL.md`](GOAL.md).

## Repository map

| Path | What |
|---|---|
| `GOAL.md` | Build goal: definition of done, architecture, phases, workstreams |
| `QARORLAR.md` | Decision log (Uzbek) — the source of truth for product decisions |
| `HANDOFF.md` | Current state and hand-off notes for the next agent |
| `TELEGRAM-YANGILIKLAR.md`, `TELEGRAM-REJA.md` | Telegram / Bot API changes and the Telegram setup plan (Uzbek) |
| `bot/` | Temporary «coming soon» responder for @tulporgobot (replaced by the real bot) |
| `content/i18n/` | Approved Telegram texts in 5 languages + Uzbek script converter |
| `brand/` | Brand pipeline scripts and final assets (rights reserved, see `BRAND.md`) |
| `tools/` | Repository tooling (secret scan) |

## Development

Python 3.12+. Tests live next to the code:

```bash
python -m pytest -q content/i18n content/prototype bot brand/mascot/poses/vector brand/icons tools
```

Never commit secrets: `.secrets/`, `*.env`, Telegram session strings and chat access hashes are ignored, and
`python tools/secret_scan.py` must pass before every push.

## License

Code: [GNU AGPL-3.0](LICENSE). Brand (name, mascot, logo, stickers, emoji, artwork): all rights reserved — see
[`BRAND.md`](BRAND.md).
