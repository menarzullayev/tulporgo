# TulporGo Mini App

React 19 + TypeScript + Vite, Telegram Mini App SDK (`window.Telegram.WebApp`). Static output, served at
`settings.miniapp_url` (default `https://tulporgo.uz/app`); the HTTP API is on the same origin under `/api`.
Hash routing (`#/offers/5`, `#/share/<token>`), so no server-side rewrites are needed.

```bash
npm ci
npm test            # vitest (jsdom)
npm run build       # tsc + vite build -> dist/
npm run dev         # http://127.0.0.1:5173, proxies /api to 127.0.0.1:8000
npm run i18n        # regenerate src/i18n/*.json from tulporgo_core (npm run i18n:check = CI guard)
```

## Screens
Home (order form: place search or map pick, time, seats, note, women-only marker) - Offers (live refresh, accept,
counter price) - Trips / Trip (card, share, complete, cancel, rate) - Profile (language, marker, driver card,
referral link, subscription status) - Driver (registration + documents) - Userbot login (`#/userbot/login`: consent,
phone, code, 2FA password) - Subscription (plans from the API, hands over to `POST /api/payments/checkout`) -
public Share page (`#/share/<token>`, no sign-in).

## Notes
- Auth: `Authorization: tma <initData>` on every call except `GET /api/share/{token}`.
- Texts: written once in `packages/core/tulporgo_core/locales/api.py`; five languages are generated. Language
  self-names live in `src/i18n/index.tsx` on purpose. Values that must stay Latin (e.g. the plate example) are
  passed as `{placeholders}` because the Cyrillic converter would mangle them.
- Plain-browser development: set `VITE_DEV_INIT_DATA` to a signed initData string for a test bot token.
  `VITE_API_BASE` overrides the API base (default `/api`).
- Brand files in `public/` are produced by `scripts/make_assets.py` from the approved files under `brand/`.
- Map tiles: OpenStreetMap through Leaflet, no API key. Map taps snap to the nearest place via
  `GET /api/places/nearest` (needs place coordinates; until they are seeded the tapped point is kept as text).
- Userbot login assumes W2's endpoints: `POST /api/userbot/consent` (optional), `login/start {phone}`,
  `login/code {code}`, `login/password {password}`; a 2FA step is detected from `status`/`next`/`password_required`
  or an error code such as `password_needed`.
