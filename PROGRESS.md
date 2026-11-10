# TulporGo — build progress

Goal: implement everything in `GOAL.md` (set by Saidakbar aka 2026-11-10 via `/goal`). Status is updated here as
work lands. Legend: ✅ done · 🔄 in progress · ⏳ pending · ⛔ blocked on the owner (cannot be done by Claude).

## Phase 0 — foundation (Claude)

| Item | Status | Notes |
|---|---|---|
| Public repo, LICENSE (AGPL-3.0), BRAND.md, README, `.gitignore`, secret scan | ✅ | https://github.com/menarzullayev/tulporgo |
| Python workspace (uv, Python 3.13) + test config | ✅ | `pyproject.toml`, `uv.lock`; groups dev / brand; extra mysql |
| `packages/core`: config, DB, models, migrations (PostgreSQL + SQLite, MySQL optional) | ✅ | Alembic 0001 + models-vs-migrations check; suite green on SQLite and PostgreSQL 17 |
| `packages/core`: services (users, drivers, requests, offers, trips, ratings, complaints, referral, billing, KPI, pricing), route parser, places, events, i18n (5 languages), emoji (decision 39) | ✅ | 56 core tests |
| Places data: Uzbekistan regions, Samarqand districts + mahallas | ✅ | 14 regions, 206 districts/cities (MHOBT codes), 1 080 / 1 102 Samarqand mahallas (data.egov.uz + kenjebaev/regions), Russian aliases; 22 mahallas missing in every source — see `data/SOURCES.md` |
| API contract | ✅ | `docs/goals/W3.md` (endpoints), FastAPI app factory + Mini App initData auth (`apps/api/tulporgo_api/deps.py`) |
| CI (GitHub Actions): ruff, tests on SQLite + PostgreSQL (+ MySQL, non-blocking), secret scan, brand tests on Windows, Mini App build | ✅ | `.github/workflows/ci.yml`; first runs exposed 3 issues, all fixed (see log); MySQL suite green locally on 8.4 |
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
| Telegram features of GOAL §4 | ✅ | all implemented and **ON by default (decision 55, approved 2026-11-10)**: `TULPORGO_TRIP_TOPICS` (topic per trip, migration 0002; skipped automatically until topics are enabled in BotFather), `TULPORGO_EPHEMERAL_GROUP`, `TULPORGO_WIDGETS` (raw `sendWidget`, accepted by Telegram production), Login with Telegram (active once `TULPORGO_LOGIN_CLIENT_SECRET` is set). Also on: Guest Mode, Rich Messages, `date_time`, member tags, colored buttons, custom emoji, `BotSubscriptionUpdated`, join-request guard. Each can be switched off; old clients get the plain card |
| Docker Compose (bot, userbot, api, miniapp, PostgreSQL, Redis, proxy), backups + restore test | ✅ | verified locally over HTTPS: API health 200, Mini App at `/app/` (SPA routes), `/` → bot, HSTS/nosniff, no-auth API 401; bot/userbot images import; restore test + negatives. Bug found by running: Caddy did not start with an empty `email` (fixed). Bot/userbot not started locally (one poller per token) |
| Deploy scripts for the Uzbekistan VPS | ✅ | `deploy/scripts/` (bootstrap-vps, deploy with backup + health + revision check + rollback hint, restore, restore-test); runbook `docs/DEPLOY.md` |
| Deploy rehearsal: unchanged `deploy/scripts/deploy.sh` on a fresh clone of the public repo | ✅ | first run failed at `migrate` (empty `KEY=` lines of `.env.example` → int/date parse errors) — fixed in cb71f17 with tests that load `.env.example`; second run: deploy OK, health 200, revision check ok, Mini App 200, restore test OK |
| Deploy to VPS, retire PC stub | ⛔ | needs a VPS bought by the owner (money) |

## Other

| Item | Status | Notes |
|---|---|---|
| ToS + privacy drafts (uz/ru), userbot consent text | ✅ | `docs/legal/` (6 texts + questions for the lawyer); lawyer review ⛔ owner |
| TulporGo app at my.telegram.org (`TULPORGO_TELEGRAM_API_ID` / `_HASH`) for drivers' logins | ⛔ | owner registers the app (needs his phone + code) |
| Click / Payme live keys | ⛔ | merchant contract needs YATT/MChJ; sandbox integration is in scope |
| Bot "Ma'lumotlarim": export + delete own data (privacy policy §8) | ✅ | Mini App profile card → `?start=malumotlarim` deep link → bot screen; `/malumotlarim`: JSON export, delete after confirmation; refused during a trip; userbot logged out on Telegram's side first (core 6 + bot 5 tests) |
| Public pages for the final legal texts (`tulporgo.uz/legal/...`) | ⏳ | after lawyer review |
| Driver document photos: Telegram storage chat vs localisation (art. 27-1) | ✅ | decision 57: Fernet-encrypted copy in the database on the Uzbek server (migration 0003, magic-byte check, 10 MB cap) + Telegram copy; admin can fetch the server copy; deleted on rejection and on data deletion; 24 tests |
| Off-site backup copy | ✅ | decision 58: monthly dump, 1 copy; `offsite` service encrypts here and copies to Cloudflare R2 (1 copy); verified with an S3-compatible stand-in; R2 account + keys ⛔ owner; R2 abroad → lawyer question |

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
