# TulporGo — build progress

Goal: implement everything in `GOAL.md` (set by Saidakbar aka 2026-11-10 via `/goal`). **Closed by Saidakbar aka on
2026-11-10**: everything Claude can do is done (e0da05f, CI 6/6 green); the ⛔ items below are his. Status is updated here as
work lands. Legend: ✅ done · 🔄 in progress · ⏳ pending · ⛔ blocked on the owner (cannot be done by Claude).

## Phase 0 — foundation (Claude)

| Item | Status | Notes |
|---|---|---|
| Public repo, LICENSE (AGPL-3.0), BRAND.md, README, `.gitignore`, secret scan | ✅ | https://github.com/menarzullayev/tulporgo |
| Python workspace (uv, Python 3.13) + test config | ✅ | `pyproject.toml`, `uv.lock`; groups dev / brand; extra mysql |
| `packages/core`: config, DB, models, migrations (PostgreSQL + SQLite, MySQL optional) | ✅ | Alembic 0001 initial, 0002 trip topics, 0003 driver documents + models-vs-migrations check; green on SQLite, PostgreSQL 17, MySQL 8.4 |
| `packages/core`: services (users, drivers, requests, offers, trips, ratings, complaints, referral, billing, KPI, pricing), route parser, places, events, i18n (5 languages), emoji (decision 39) | ✅ | 56 core tests |
| Places data: Uzbekistan regions, Samarqand districts + mahallas | ✅ | 14 regions, 206 districts/cities (MHOBT codes), 1 080 / 1 102 Samarqand mahallas (data.egov.uz + kenjebaev/regions), Russian aliases; 22 mahallas missing in every source — see `data/SOURCES.md` |
| API contract | ✅ | `docs/goals/W3.md` (endpoints), FastAPI app factory + Mini App initData auth (`apps/api/tulporgo_api/deps.py`) |
| CI (GitHub Actions): ruff, mypy, tests on SQLite + PostgreSQL (+ MySQL, non-blocking), secret scan, brand tests on Windows, Mini App build | ✅ | `.github/workflows/ci.yml`; all 6 jobs green incl. MySQL (651edb8) |
| Workstream briefs `docs/goals/W1–W4.md` + shared contracts (bot context middleware, API deps, router slots) | ✅ | |

## Phase 1 — parallel build (agents in worktrees)

| Workstream | Status | Branch | Notes |
|---|---|---|---|
| W1 bot — passenger, driver, admin, KPI report | ✅ | merged (94bc3bf) | start/language/deep links, order by buttons + free text + Mini App + Guest Mode, driver notifications (rate-limited), offers/counter, trip card (Rich Message + `date_time`), share, rating, complaints, driver onboarding + documents + referral, admin panel, jobs (expiry, weekly KPI Mon 09:00, member tags), `/qatnovlarim`; 160 tests |
| W2 userbot — consent, encrypted sessions, safe scheduler | ✅ | merged (4a47717) | consent screen = `docs/legal/userbot-consent.uz.md`; Mini App login API (code + 2FA, 5 attempts, never stored/logged); Fernet sessions; groups by plan; scheduler 45 min + jitter, daily cap, FloodWait/PeerFlood/ban handling without retries; `/elon`; worker `python -m tulporgo_userbot`; 167 tests. Assumption: 5-minute absolute floor even after risk acknowledgement. Gaps: pending login lives in API memory (1 API process); real Telethon client only stub-tested |
| W3 Mini App + API | ✅ | merged (c1444c1) | API: me, places, requests, offers, trips, public share, driver register + documents (storage chat `file_id`); Mini App: order + map, offers, trips, profile, driver docs, userbot login, subscription, share page; 123 pytest + 159 vitest |
| W4 payments + referral | ✅ | merged (7dad311) | P2P (admin review), Stars (invoice, pre-checkout, recurring link, refund), Click SHOP API, Payme Merchant API (6 methods), other-gateway base class, `/obuna`, `/terms`, `/paysupport`, terms confirmation, 3-day reminders, API checkout + webhooks; 566 payment tests. Gaps: sandbox consoles of Click/Payme not run yet; reminder de-dup in memory; Payme fiscal `detail` not sent |

## Phase 2 — integration

| Item | Status | Notes |
|---|---|---|
| Merge, end-to-end tests | ✅ | all 4 merged; `tests/e2e`: Mini App order → bot → driver offer → accept → trip → rate → share (no contacts); Click prepare/complete with forged-signature and replay negatives. Integration gaps found and fixed: payment jobs not started by the bot; Mini App checkout contract; `uv.lock` was git-ignored; duplicate test module name |
| Type checking in CI (GOAL §1 Quality: "lint, types") | ✅ | `uv run mypy` clean on 99 files, CI step in `lint-and-scan`; 4 real crashes on inline-mode / inaccessible messages and sender-less contacts found and guarded (+19 tests) |
| OpenAPI contract file `docs/openapi.json` + CI check that it is current | ✅ | `tulporgo_api.export_openapi`, `tests/contract` (stale file fails) |
| Telegram features of GOAL §4 | ✅ | decision 55 (approved 2026-11-10): ON by default — `TULPORGO_EPHEMERAL_GROUP`, `TULPORGO_WIDGETS` (raw `sendWidget`, accepted by Telegram production and seen rendered in Telegram Desktop), Guest Mode (BotFather Guest Chat Mode enabled, `supports_guest_queries=true`), Login with Telegram (active once `TULPORGO_LOGIN_CLIENT_SECRET` is set). **OFF: trip topics** (`TULPORGO_TRIP_TOPICS=false`, decision 59 — BotFather's Threaded Mode adds a fee to Telegram Stars purchases; code and migration 0002 kept). Also on: Rich Messages, `date_time`, member tags, colored buttons, custom emoji, `BotSubscriptionUpdated`, join-request guard. Each can be switched off; old clients get the plain card |
| Docker Compose (bot, userbot, api, miniapp, PostgreSQL, Redis, proxy), backups + restore test | ✅ | verified locally over HTTPS: API health 200, Mini App at `/app/` (SPA routes), `/` → bot, HSTS/nosniff, no-auth API 401; bot/userbot images import; restore test + negatives. Bug found by running: Caddy did not start with an empty `email` (fixed). Bot/userbot not started locally (one poller per token) |
| Deploy scripts for the Uzbekistan VPS | ✅ | `deploy/scripts/` (bootstrap-vps, deploy with backup + health + revision check + rollback hint, restore, restore-test); runbook `docs/DEPLOY.md` |
| Deploy rehearsal: unchanged `deploy/scripts/deploy.sh` on a fresh clone of the public repo | ✅ | first run failed at `migrate` (empty `KEY=` lines of `.env.example` → int/date parse errors) — fixed in cb71f17 with tests that load `.env.example`; second run: deploy OK, health 200, revision check ok, Mini App 200, restore test OK |
| Deploy to VPS, retire PC stub | ⛔ | needs a VPS bought by the owner (money) |

## Other

| Item | Status | Notes |
|---|---|---|
| ToS + privacy drafts (uz/ru), userbot consent text | ✅ | `docs/legal/` (6 texts + questions for the lawyer); lawyer review ⛔ owner |
| TulporGo app at my.telegram.org (`TULPORGO_TELEGRAM_API_ID` / `_HASH`) for drivers' logins | ✅ | decision 60: the account's existing (unused) app renamed to TulporGo / `tulporgo`; owner copies `api_id` + `api_hash` into the server `.env` at deploy |
| Click / Payme live keys | ⛔ | merchant contract needs YATT/MChJ; sandbox integration is in scope |
| Bot "Ma'lumotlarim": export + delete own data (privacy policy §8) | ✅ | Mini App profile card → `?start=malumotlarim` deep link → bot screen; `/malumotlarim`: JSON export, delete after confirmation; refused during a trip; userbot logged out on Telegram's side first (core 6 + bot 5 tests) |
| Public pages for the legal texts (`tulporgo.uz/legal/terms|privacy|userbot-consent?lang=uz|ru`) | ✅ | served by the API from `docs/legal` (Caddy `/legal/*`), raw HTML escaped, only 3 documents, mobile-checked (375 px, no horizontal scroll); the bot's `/terms` link lands here. Still the DRAFT texts with the banner — lawyer ⛔ |
| Driver document photos: Telegram storage chat vs localisation (art. 27-1) | ✅ | decision 57: Fernet-encrypted copy in the database on the Uzbek server (migration 0003, magic-byte check, 10 MB cap) + Telegram copy; admin can fetch the server copy; deleted on rejection and on data deletion; 24 tests |
| Off-site backup copy | ✅ | decision 58: monthly dump, 1 copy; `offsite` service encrypts here and copies to Cloudflare R2 (1 copy); verified with an S3-compatible stand-in and against the real bucket (decision 62: account "TulporGo", private bucket `tulporgo-backup`, bucket-scoped token; keys in `.secrets/r2.env`); R2 abroad → lawyer question |

## Log

- 2026-11-10 — goal set; PROGRESS.md created.
- 2026-11-10 — Phase 0 core landed (models, services, migrations, places data, i18n, emoji, contracts).
- 2026-11-10 — incident: a push went out although the secret scan reported 5 findings (scan output was piped
  through `tail`, hiding its exit code). Findings were only placeholder numbers (+998 90 123 45 67) — no real
  data. Fixed: placeholder rule + negative test, pre-commit hook blocks commits on findings.
- 2026-11-10 — owner to confirm: `stars_rate_uzs` (so'm per Telegram Star, default 165) before live Stars.
- 2026-11-10 — CI first runs: (1) `hashFiles()` in a job-level `if` is invalid → moved to steps; (2) `brand/icons/test_in_pack.py`
  (a CLI tool) was collected by pytest and needed `.secrets/` → excluded via `conftest.py`; (3) MySQL refused the 0001
  downgrade (error 1553) → downgrade drops tables only. Core suite: SQLite ✅, PostgreSQL 17 ✅, MySQL 8.4 ✅ (local).
- 2026-11-10 — Phase 1 started: 4 agents in worktrees (W1–W4).
- 2026-11-10 — `deploy/` stack + `tulporgo_core.manage` (migrate / seed-places / check); restore test proven locally.
- 2026-11-10 — legal drafts uz/ru in `docs/legal/`; Telegram Stars rules (`/terms`, `/paysupport`) sent to W4.
- 2026-11-10 — W4 merged; full suite 646 passed, ruff clean, secret scan 0. Core fix from W4: Cyrillic converter broke words ending in o/g/y (`"" in APOS` is always true).
- 2026-11-10 — W2 merged; full suite 815 passed, ruff clean, secret scan 0.
- 2026-11-10 — W1 and W3 merged; integration fixes; `/malumotlarim`; e2e tests; OpenAPI file; join-request guard;
  full Docker stack verified over HTTPS. Full suite 1 110 pytest + 159 vitest, CI green. Telegram check: Bot API 10.4,
  blog 2026-08-25 — nothing newer than `TELEGRAM-YANGILIKLAR.md`.
- 2026-11-10 — goal build complete: mypy clean (CI step), 1 129 pytest + 159 vitest, GitHub CI 6/6 green (e93704e).
  Everything left is ⛔ owner-side (see tables). Owner notified in chat and via @tulporgobot.
- 2026-11-10 — deploy rehearsal on a fresh clone found and fixed the `.env.example` crash; GOAL §4 Telegram features being built behind flags (default off).
- 2026-11-10 — GOAL §4 features merged behind flags; Login with Telegram (OIDC) merged; full suite 1 213 pytest + 176 vitest, mypy clean on 106 files.
- 2026-11-10 — final: CI 6/6 green with no error annotations (14cc793); GOAL.md items done or ⛔ owner-only.
- 2026-11-10 — owner approval flow started (CLAUDE.md rule 4): sample trip widget sent to Saidakbar aka via @tulporgobot
  with the real `sendWidget` (accepted by Telegram production, message 183). Topics: `getMe.has_topics_enabled=false` →
  owner enables topics for the bot in BotFather before `TULPORGO_TRIP_TOPICS=true`. Ephemeral and Login need a group /
  the BotFather client secret to demo.
- 2026-11-10 — decision 55: Saidakbar aka approved the GOAL §4 features; defaults switched ON (tests: defaults on, each switch off, all three together in one trip).
- 2026-11-10 — decisions 56–59: Stars 165 so'm confirmed; documents server+Telegram; backups monthly, 1 copy, encrypted copy to R2 (built + verified); BotFather: Threaded Mode NOT enabled (it adds a fee to Stars purchases) → trip topics off, Guest Chat Mode enabled (`supports_guest_queries=true`).
- 2026-11-10 — decision 57 merged (documents encrypted on the server + Telegram); privacy policy §5/§6 updated; full suite 1 257 passed.
- 2026-11-10 — MySQL: PyMySQL 1.2 broke aiomysql's bytes escaping (encrypted documents) → `pymysql<1.2` in the mysql extra + guard test; CI 6/6 green incl. MySQL (651edb8).
- 2026-11-10 — PROGRESS rows corrected (topics OFF per decision 59; CI incl. MySQL green); public legal pages built.
- 2026-11-10 — **goal closed by Saidakbar aka.** Open, owner-only: VPS purchase + deploy, lawyer review, Click/Payme merchant contract, my.telegram.org app, Cloudflare R2 keys, BotFather Login Widget client secret.
- 2026-11-10 — my.telegram.org: existing app renamed TulporGo/`tulporgo` (decision 60), verified after reload.
- 2026-11-10 — userbot API credentials stored by Saidakbar aka in `.secrets/telegram_app.env` (git-ignored); format ok and accepted by Telegram (`auth.exportLoginToken` → LoginToken, no code sent, nothing saved).
- 2026-11-11 — Eskiz: DNS zone for tulporgo.uz created (zone 14116, NS ns1–ns4.eskiz.uz); Eskiz default records removed (ftp, webmail, mail A → 45.138.159.4, MX). `www` CNAME → tulporgo.uz kept. Blocked by the permission guard (DNS changes) — left for Saidakbar aka: delete the default apex A 45.138.159.4, SPF → `v=spf1 -all`, DMARC → `v=DMARC1; p=reject`, add CAA `0 issue "letsencrypt.org"`, WHOIS → hide; apex A → VPS IP after purchase.
- 2026-11-11 — Eskiz: with Saidakbar aka's permission the remaining steps were done — default apex A deleted, SPF `v=spf1 -all`, DMARC `v=DMARC1; p=reject`, CAA `0 issue "letsencrypt.org"`, WHOIS contacts hidden. Verified from outside (ns1.eskiz.uz and 1.1.1.1 give the same answers; whois.cctld.uz shows `not.defined.` contacts). Only open item: apex A → VPS IP after purchase.
- 2026-11-11 — Cloudflare (decision 62): separate account "TulporGo" created by Saidakbar aka, R2 enabled; private bucket `tulporgo-backup` (EEUR, no r2.dev, no domain, no CORS); token `tulporgo-offsite` = Object Read & Write on that bucket only, keys written by Saidakbar aka into `.secrets/r2.env`. Live check with the real `offsite` code: encrypted upload (TGB1, no PGDMP marker), list, decrypt to the original, delete — all passed; negative: the token cannot list or create buckets (AccessDenied). Left: copy into `deploy/.env` on the VPS, IP filter on the token.
- 2026-11-11 — decision 63: the nine agent-chosen rules confirmed by Saidakbar aka; one change built: a rejected document's server copy is kept 7 days (`delete_after`, migration 0004, `rejected_documents_keep_days`), purged by an hourly bot job; a new upload clears the mark; privacy deletion still removes at once. Tests incl. negatives (one minute early → nothing purged; old handler fails the new test). Privacy policy uz/ru updated. Decision 64: official email `info@tulporgo.uz` (mail service not chosen yet).
- 2026-11-11 — email (decision 64): Zoho Mail Forever Free in its own Zoho account (the first sign-up landed in RankWant's org, whose one free domain is taken); org TulporGo, login `admin@tulporgo.uz`, alias `info@tulporgo.uz` ("TulporGo"). Eskiz DNS: Zoho verification + SPF `include:zohomail.com -all` in the apex TXT set, MX mx/mx2/mx3.zoho.com 10/20/50, DKIM `zmail._domainkey`; checked on ns1/ns2.eskiz.uz and 1.1.1.1, Zoho "All the records have been verified successfully", mx.zoho.com answers on port 25. `info@tulporgo.uz` written into the privacy policy and terms (uz/ru). Left: 2FA in Zoho (owner), a two-way test mail.
- 2026-11-11 — email: two-way test confirmed by Saidakbar aka (mail.ru → info@tulporgo.uz received, reply arrived). Left for the owner: 2FA in Zoho, password into a password manager.
- 2026-11-11 — Login with Telegram ready: BotFather mini app → Login Widget (not in the chat menu); Redirect URI `https://tulporgo.uz/api/auth/telegram/callback` only, Trusted Origins / Native Login empty, RS256; client id 9198136695 = bot id; secret in `.secrets/telegram_login.env` (owner). Telegram's auth page accepts the registered URI and refuses another host and `www.` (negative). One real login before the site exists (redirect could not load, the code was taken from the address): the project's `OidcClient` exchanged it with the secret (Basic auth + PKCE) and verified the id_token (JWKS signature, iss, aud, exp, nonce); a different nonce is refused. The callback uses the `id` claim, present in the real token. TELEGRAM-YANGILIKLAR.md checked 2026-11-11 (Bot API 10.4, no new post).
- 2026-11-11 — decision 65: the site login also asks for `telegram:bot_access` (Saidakbar aka: "Ha, qo'sh"), so @tulporgobot can send trip notices to people who never opened it; `TULPORGO_LOGIN_BOT_ACCESS` (default true) switches it off. Tests: default scope `openid profile telegram:bot_access`, switched off → `openid profile` (negative); the new test fails on the old route. Privacy policy uz/ru: a row for site login (profile photo not stored; revoke by blocking the bot).
- 2026-11-11 — decision 66: the site login also asks for the Telegram-verified phone (`phone` scope, Saidakbar aka). The `phone_number` claim goes through the same `set_phone` (Uzbek mobiles, normalised) only when the user has no number; `phone_number_verified=false` is ignored; a foreign number still logs in, no number kept; `TULPORGO_LOGIN_PHONE` (default true) switches it off. 8 tests incl. 5 negatives; the store and scope tests fail on the old route. Privacy policy uz/ru updated.
