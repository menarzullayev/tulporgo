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
| W1 bot — passenger, driver, admin, KPI report | 🔄 | worktree agent | started 2026-11-10 |
| W2 userbot — consent, encrypted sessions, safe scheduler | ✅ | merged (4a47717) | consent screen = `docs/legal/userbot-consent.uz.md`; Mini App login API (code + 2FA, 5 attempts, never stored/logged); Fernet sessions; groups by plan; scheduler 45 min + jitter, daily cap, FloodWait/PeerFlood/ban handling without retries; `/elon`; worker `python -m tulporgo_userbot`; 167 tests. Assumption: 5-minute absolute floor even after risk acknowledgement. Gaps: pending login lives in API memory (1 API process); real Telethon client only stub-tested |
| W3 Mini App + API | 🔄 | worktree agent | started 2026-11-10 |
| W4 payments + referral | ✅ | merged (7dad311) | P2P (admin review), Stars (invoice, pre-checkout, recurring link, refund), Click SHOP API, Payme Merchant API (6 methods), other-gateway base class, `/obuna`, `/terms`, `/paysupport`, terms confirmation, 3-day reminders, API checkout + webhooks; 566 payment tests. Gaps: sandbox consoles of Click/Payme not run yet; reminder de-dup in memory; Payme fiscal `detail` not sent |

## Phase 2 — integration

| Item | Status | Notes |
|---|---|---|
| Merge, end-to-end tests | ⏳ | |
| Type checking in CI (GOAL §1 Quality: "lint, types") | ⏳ | after all merges, so `pyproject.toml` / `uv.lock` do not conflict with the workstreams |
| OpenAPI contract file `docs/openapi.json` + CI check that it is current | ⏳ | after W3 merge |
| Telegram features of GOAL §4 (Guest Mode, Rich Messages, `date_time`, member tags, join-request guard, topics, colored buttons, custom emoji) | ⏳ | checklist against the merged bot |
| Docker Compose (bot, userbot, api, miniapp, PostgreSQL, Redis, proxy), backups + restore test | 🔄 | `deploy/` — postgres, redis, migrate, api, backup verified locally (Docker 29.8); restore test OK + negative tests; proxy/bot/userbot start after the merge |
| Deploy scripts for the Uzbekistan VPS | ✅ | `deploy/scripts/` (bootstrap-vps, deploy with backup + health + revision check + rollback hint, restore, restore-test); runbook `docs/DEPLOY.md` |
| Deploy to VPS, retire PC stub | ⛔ | needs a VPS bought by the owner (money) |

## Other

| Item | Status | Notes |
|---|---|---|
| ToS + privacy drafts (uz/ru), userbot consent text | ✅ | `docs/legal/` (6 texts + questions for the lawyer); lawyer review ⛔ owner |
| TulporGo app at my.telegram.org (`TULPORGO_TELEGRAM_API_ID` / `_HASH`) for drivers' logins | ⛔ | owner registers the app (needs his phone + code) |
| Click / Payme live keys | ⛔ | merchant contract needs YATT/MChJ; sandbox integration is in scope |
| Bot "Ma'lumotlarim": export + delete own data (privacy policy §8) | 🔄 | core service `services/privacy.py` ✅ (6 tests); bot button after W1 merge |
| Public pages for the final legal texts (`tulporgo.uz/legal/...`) | ⏳ | after lawyer review |
| Driver document photos: Telegram storage chat vs localisation (art. 27-1) | ⛔ | question for the lawyer + owner (`docs/legal/README.md` §3) |
| Off-server backup copy inside Uzbekistan | ⛔ | owner chooses the second location (`docs/DEPLOY.md`) |

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
