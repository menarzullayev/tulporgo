# TulporGo — build goal (v1)

Owner: Saidakbar aka. Agreed 2026-11-10 (decisions 42–53 in `QARORLAR.md`). No deadline (45): done means the
definition of done below is met and measured, not a date.

## 1. Definition of done (launch-ready MVP, Qo'shrabot → all Samarqand)

| Area | Done when (each item has an automated test or a recorded measurement) |
|---|---|
| Passenger | Order by **buttons** (district → mahalla, time, seats), by **free text** (`Qo'shrabot → Samarqand 07:30` parsed), from the **Mini App** map, and from any group via **Guest Mode** (47). Receives driver offers, can counter the price (7), picks one (6), gets a trip card (Rich Message, `date_time`), can share the trip (13), rates the driver |
| Driver | Registers (phone, car: make/colour/plate/photo); documents optional → "Tasdiqlangan" badge (12); sees requests, sends offers; free period on (44); referral link `?start=ref_…` with +7 days for both (52); member tags in the drivers group |
| Userbot | Driver connects own account after a risk-consent screen (8); session encrypted at rest, "Hisobni uzish" deletes it; driver picks groups; safe default 1 post / group / 30–60 min with jitter, FloodWait/PEER_FLOOD → stop + notify (48); limits adjustable with warning |
| Mini App | React + Telegram Mini App SDK on `tulporgo.uz` (domain-locked methods, Bot API 10.2): map, addresses, order form, profile, driver document upload; auth by Telegram `initData` |
| Payments | One provider interface: P2P card + manual check in Telegram, Telegram **Stars** (subscription, `BotSubscriptionUpdated`), **Click**, **Payme**, room for others (44). Free period is a feature flag; sandbox tests for every provider; live keys only after a merchant contract |
| Admin | In-Telegram admin panel for the family team (19): verify drivers, confirm P2P payments, handle complaints, blacklist (13) |
| Quality | CI green: lint, types, unit + integration tests on SQLite and PostgreSQL (MySQL optional job), secret scan; every new rule has a negative test |
| Ops | Docker Compose on a **VPS in Uzbekistan** (43): bot, userbot workers, API, PostgreSQL, Redis, reverse proxy + TLS; daily DB backup with a restore test; health checks; the PC stub (`bot/coming_soon.py`) retired |
| Legal | ToS + privacy policy drafts (uz/ru) reviewed by a lawyer (51); userbot consent text; personal data stays in Uzbekistan |
| KPI | Bot computes the 30/60-day KPIs (53) and sends Saidakbar aka a weekly report |

## 2. Architecture (monorepo)

```
packages/core/      domain model, services, SQLAlchemy 2 (async) models, Alembic migrations, Pydantic schemas,
                    event contracts. Dialect-agnostic: PostgreSQL in prod, SQLite in tests, MySQL optional (46)
apps/bot/           aiogram 3 — passenger, driver and admin flows. The ONLY process that receives bot updates
apps/userbot/       Telethon workers, one per connected driver session; scheduler with the safety limits
apps/api/           FastAPI — Mini App backend, payment webhooks (Click/Payme), Stars receipts
apps/miniapp/       React + Telegram Mini App SDK
infra/              docker-compose, proxy, backups, deploy scripts
docs/               OpenAPI contract, ADRs, workstream goals (docs/goals/W*.md)
brand/ content/     existing assets — brand rights reserved (50), see BRAND.md
```
Services talk through `packages/core` (shared DB + services) and Redis events
(`request.created`, `offer.created`, `offer.accepted`, `payment.confirmed`, `userbot.post_failed`).

## 3. Phases

| Phase | Who | Output | Gate to next phase |
|---|---|---|---|
| **0 — Foundation** | Claude (this session) | git + public GitHub repo, monorepo skeleton, `packages/core` domain model + migrations + tests, OpenAPI contract skeleton, CI (lint/types/tests/secret scan), LICENSE (AGPL-3.0), BRAND.md, `docs/goals/W1–W4.md` | CI green on SQLite + PostgreSQL; secret scan clean; Saidakbar aka confirms what stays private (see §5) |
| **1 — Parallel build** | 4 agents, each in its own worktree, own goal + tests | W1 bot · W2 userbot · W3 Mini App + API · W4 payments + referral | Each workstream's goal checks pass in CI; no change to `packages/core` without a reviewed PR |
| **2 — Integration** | Claude | merged main, end-to-end tests (passenger ↔ driver ↔ payment), staging on the Uzbekistan VPS | Full flow passes on staging; restore-from-backup tested |
| **3 — Pilot** | Saidakbar aka + family drivers | Qo'shrabot pilot, KPI reports, legal review | KPI tracking works; lawyer OK |
| **4 — Launch** | Saidakbar aka | ads, drivers via referral (49) | — |

## 4. Telegram features to use (from `TELEGRAM-YANGILIKLAR.md`, Bot API 10.4)

Guest Mode (orders from any group) · Rich Messages (trip card, tariff table) · ephemeral messages + commands (group
menus) · `date_time` entity (departure time in every user's zone) · member tags (driver status, "Elchi") · join-request
guard + Mini App (drivers group screening) · custom emoji (decision 39) · colored buttons · topics in the bot chat
(one topic per trip) · Login with Telegram (tulporgo.uz) · `BotSubscriptionUpdated` (Stars subscriptions) ·
Widgets (10.4, private chats; aiogram 3.31 supports up to 10.3 → raw HTTP for 10.4 features).

## 5. Public repo rules (46, 50)

- Never committed: `.secrets/`, `*.env`, session strings, owner/driver personal data, chat access hashes.
  Secret scan runs in CI and as a pre-commit hook; the first push happens only after a clean full-history scan.
- Internal documents (decisions, hand-off, problems log, plans, naming research) are public by decision 54.
- Brand: only final deliverables are committed (avatars, icons, emoji/sticker exports, pipeline scripts); pipeline
  intermediates and `.ai` sources stay local — the scripts regenerate them.
- Code: AGPL-3.0. Brand (name, mascot, logo, stickers, emoji): all rights reserved (`BRAND.md`).

## 6. Workstream briefs (Phase 1)

Each agent gets `docs/goals/W<n>.md`: scope, owned folders, the core interfaces it may use, acceptance tests, and
"done = CI green + demo recorded". Agents never edit another workstream's folder or `packages/core` directly —
core changes go through a PR that Claude reviews.
