# Workstream rules (Phase 1) — read before W1–W4

You are one of four agents building TulporGo in parallel, each in its own git worktree/branch. Claude (the lead)
merges and reviews. Read first: `GOAL.md`, `QARORLAR.md` (decisions, Uzbek), `CLAUDE.md` (incl. the Telegram rule),
`TELEGRAM-YANGILIKLAR.md` (Bot API 10.4 features), `packages/core/tulporgo_core/` (the domain you build on).

## Setup and checks
```bash
uv sync --all-groups          # Python 3.13 venv in .venv
uv run pytest -q              # whole Python suite (SQLite)
uv run ruff check packages apps
python tools/secret_scan.py   # also runs as a git pre-commit hook
```

## Ownership (no edits outside your folders)
| WS | Owns | Integration point it fills |
|---|---|---|
| W1 bot | `apps/bot/`, `packages/core/tulporgo_core/locales/bot.py` | `tulporgo_bot.handlers:router`, `setup()` |
| W2 userbot | `apps/userbot/`, `locales/userbot.py` | `tulporgo_userbot.bot:router`, `tulporgo_userbot.api:router`, `python -m tulporgo_userbot` |
| W3 API + Mini App | `apps/api/tulporgo_api/routes*`, `apps/miniapp/`, `locales/api.py` | `tulporgo_api.routes:router`, Mini App build |
| W4 payments | `packages/payments/`, `locales/payments.py` | `tulporgo_payments.bot:router`, `tulporgo_payments.api:router` |

`packages/core` is shared: prefer calling existing services. If you truly need a core change, keep it **additive**
(new function/field + migration + tests), never change an existing signature, and list it under "core changes" in
your final report. New DB fields need an Alembic migration in `packages/core/migrations/versions/` named
`00NN_<ws>_<what>.py` with `down_revision` = the current head (`0001`); the lead renumbers on merge.

## Contracts you rely on
- Bot handlers get `session, settings, bus, user, lang, t` (see `apps/bot/tulporgo_bot/context.py`).
- API routes use `tulporgo_api.deps`: `get_session`, `get_settings`, `get_bus`, `current_user` (Mini App
  `Authorization: tma <initData>`, HMAC-verified).
- Domain errors (`tulporgo_core.errors`) carry a stable `code`; the API maps them to JSON `{error, detail}`.
- Events (`tulporgo_core.events`) cross processes through Redis; handlers must be idempotent.
- Texts: `tulporgo_core.i18n.t(key, lang)`; write `uz` (current Latin, plain `'`), `ru`, `en` — the three Uzbek scripts
  are derived. Keys are prefixed with your area (`bot.`, `userbot.`, `api.`, `pay.`).
- Emoji (decision 39): write standard emoji in texts and pass messages through `tulporgo_core.emoji.decorate()` —
  TulporGo icons for structure, tulpor head for greeting, at most ONE animated accent per message.
- Buttons: `style` = `primary` / `success` / `danger` where meaningful (Bot API 9.4). Old clients must still work.

## Quality bar
- Tests for every handler/endpoint/job; **every rule has a negative test**. No network in tests (fake Telegram, fake
  providers, SQLite). Keep the full suite green.
- No secrets in code or tests; config through `tulporgo_core.config.Settings` (env `TULPORGO_*`).
- Product facts only from `QARORLAR.md` — never invent prices, promises, statistics.
- Conventional Commits, small commits, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Done = your goal's checklist met, full suite + ruff green, and a final report (≤ 300 words): what you built,
  files, test count, core changes, known gaps.
