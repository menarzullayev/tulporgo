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
| CI (GitHub Actions): ruff, tests on SQLite + PostgreSQL (+ MySQL, non-blocking), secret scan, brand tests on Windows, Mini App build | 🔄 | `.github/workflows/ci.yml` — first run pending |
| Workstream briefs `docs/goals/W1–W4.md` + shared contracts (bot context middleware, API deps, router slots) | ✅ | |

## Phase 1 — parallel build (agents in worktrees)

| Workstream | Status | Branch | Notes |
|---|---|---|---|
| W1 bot — passenger, driver, admin, KPI report | ⏳ | | |
| W2 userbot — consent, encrypted sessions, safe scheduler | ⏳ | | |
| W3 Mini App + API | ⏳ | | |
| W4 payments + referral | ⏳ | | |

## Phase 2 — integration

| Item | Status | Notes |
|---|---|---|
| Merge, end-to-end tests | ⏳ | |
| Docker Compose (bot, userbot, api, miniapp, PostgreSQL, Redis, proxy), backups + restore test | ⏳ | |
| Deploy scripts for the Uzbekistan VPS | ⏳ | |
| Deploy to VPS, retire PC stub | ⛔ | needs a VPS bought by the owner (money) |

## Other

| Item | Status | Notes |
|---|---|---|
| ToS + privacy drafts (uz/ru), userbot consent text | ⏳ | lawyer review ⛔ owner |
| Click / Payme live keys | ⛔ | merchant contract needs YATT/MChJ; sandbox integration is in scope |

## Log

- 2026-11-10 — goal set; PROGRESS.md created.
- 2026-11-10 — Phase 0 core landed (models, services, migrations, places data, i18n, emoji, contracts).
- 2026-11-10 — incident: a push went out although the secret scan reported 5 findings (scan output was piped
  through `tail`, hiding its exit code). Findings were only placeholder numbers (+998 90 123 45 67) — no real
  data. Fixed: placeholder rule + negative test, pre-commit hook blocks commits on findings.
- 2026-11-10 — owner to confirm: `stars_rate_uzs` (so'm per Telegram Star, default 165) before live Stars.
