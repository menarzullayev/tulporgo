# TulporGo — build progress

Goal: implement everything in `GOAL.md` (set by Saidakbar aka 2026-11-10 via `/goal`). Status is updated here as
work lands. Legend: ✅ done · 🔄 in progress · ⏳ pending · ⛔ blocked on the owner (cannot be done by Claude).

## Phase 0 — foundation (Claude)

| Item | Status | Notes |
|---|---|---|
| Public repo, LICENSE (AGPL-3.0), BRAND.md, README, `.gitignore`, secret scan | ✅ | https://github.com/menarzullayev/tulporgo |
| Python workspace (uv, Python 3.13) + test config | 🔄 | |
| `packages/core`: config, DB, models, migrations (PostgreSQL + SQLite, MySQL optional) | ⏳ | |
| `packages/core`: services (users, drivers, requests, offers, trips, ratings, complaints, referral, billing, KPI, pricing), route parser, places, events | ⏳ | |
| Places data: Uzbekistan regions, Samarqand districts + mahallas | 🔄 | dataset from `QARORLAR` (1 063 mahalla) not found on disk — research agent looking for official open data |
| API contract (OpenAPI) | ⏳ | |
| CI (GitHub Actions): ruff, tests on SQLite + PostgreSQL, secret scan, Mini App build | ⏳ | |
| Workstream briefs `docs/goals/W1–W4.md` | ⏳ | |

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
