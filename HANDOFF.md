# TulporGo — agent handoff

Written 2026-11-10 by Claude (Opus) at the end of a long session. Read this first, then `QARORLAR.md`.
Everything below was measured on 2026-11-10 unless marked otherwise.

## 0. Who / how to work

- Owner: **Saidakbar aka**. Always address him exactly that way. Talk to him in **Uzbek (Latin)**; code,
  commands, paths, commit messages in English (Conventional Commits). Global rules:
  `C:\Users\nsn\.claude\CLAUDE.md` — read it.
- He wants: answer first, short tables, one line per step, 3–5 line summary at the end.
  Raw errors quoted verbatim + 1–2 Uzbek lines explaining them.
- **Show before asking.** Render the result and send it to him via @tulporgobot
  (`content/prototype/send_variants.py`) *before* any design question. Decisions one at a time
  (AskUserQuestion), recommended option first.
- Public asset names (pack titles, slugs) in **English**; offer 2–4 variants, keep "TulporGo".
- "Done" only after measuring. Every new check gets a **negative test**.
- Stop and ask before: deleting files/data, money, any outbound message/post to third parties.
  Sending review images/links to Saidakbar aka himself through his own bot is the normal workflow.
- Secrets: bot token in `.secrets/bot.env` (`TULPORGO_BOT_TOKEN`), owner chat id in
  `.secrets/owner_chat_id`. **Never print them.**
- Telegram user accounts: WorkBuddy's `~/.mcp-telegram/session` is **never** touched. On any
  FloodWait — stop, never hammer (his words: "akkauntga zarar yetmasin").
- Git repo, PUBLIC: https://github.com/menarzullayev/tulporgo (decisions 46, 54). Repo-local author email is the
  GitHub noreply address (personal email must never be in public commits). `python tools/secret_scan.py` before
  every push (also a pre-commit hook). CI: GitHub Actions (ruff, mypy, SQLite/PostgreSQL/MySQL tests, secret scan,
  Windows brand tests, Mini App). Windows 11, Git Bash + PowerShell.

## 1. Project in one paragraph

TulporGo = Telegram taxi service (bot + Mini App + driver userbots) for all of Uzbekistan, launching
in Samarqand (Qo'shrabot). Product/business decisions 1–20, brand 21–24, Telegram presence 25–38 are
in **`QARORLAR.md`** (source of truth, Uzbek). Telegram features worth using: `TELEGRAM-YANGILIKLAR.md`.
**No bot code exists yet** — all work so far is brand + mascot + content prototypes + sticker packs.

## 2. Map of the repo

| Path | What |
|---|---|
| `QARORLAR.md` | Decision log (#1–38), open tasks, KPI proposal |
| `CLAUDE.md` | Project agent rules — incl. the standing **Telegram rule**: check for new Telegram/Bot API changes at the start of any Telegram task and propose fitting features |
| `TELEGRAM-YANGILIKLAR.md` | Telegram/Bot API changes 2025-11…2026-11 (up to Bot API 10.4, 2026-11-09) and how we use them |
| `TELEGRAM-REJA.md` | Proposal: professional setup of bot, channel, groups, Community (stages 1–6), awaiting decisions |
| `naming/` | Brand-name research (`brend-nomlari-2.html`) |
| `brand/mascot/directions/` | 10 mascot directions, `vector/*-brand*` = brand-palette vectors; `palette_snap.py` (+tests) |
| `brand/mascot/chatgpt/` | Emblem (merch only now) |
| `brand/mascot/model-sheet/09-model-sheet-v1.png` | **Canon** for character 09 (chibi tulpor) |
| `brand/mascot/poses/*.png` | 51 approved/under-review poses (927 px raster, ChatGPT); list: `poses/INDEX.md` |
| `brand/mascot/poses/vector/` | Vector pipeline + all Telegram outputs (see §4) |
| `brand/mascot/poses/vector/MUAMMOLAR.md` | Every problem met in the vector/emoji work, cause, fix, how verified (#1–26) |
| `brand/mascot/HUQUQIY-TEKSHIRUV.md` | Legal checklist for AI-generated mascot (trademark), with sources |
| `content/mascot-poses.md` | Pose list / briefs |
| `content/prototype/` | Post image templates & senders: `text_variants.py` (5 text layouts A–E), `panorama_cues.py` (carousel RM panorama), `send_*.py`, **`send_variants.py`** (`call()`, `owner_chat()` Bot API helpers), **`create_sticker_sets.py`** (+ `attempt_guard.py`, `create_attempts.json`) |
| `content/i18n/` | Telegram texts (stage 1): `telegram_texts.py` (source: current Latin + ru + en), `alphabet.py` (→ new Latin / official current Latin / Cyrillic), `build_texts.py` (limits check → `build/telegram_texts.json`, `telegram-texts-review.md`), `send_preview.py` (render to owner via bot); tests 24 |
| `.claude/agents/` | `tulporgo-content-maker.md`, `tulporgo-media-engineer.md` (draft-only agents) |
| `.secrets/` | Token + owner chat id (gitignored) |

## 3. Current state (2026-11-10)

### Live Telegram sticker/emoji packs (owner: Saidakbar aka, created by @tulporgobot)

| Set | Type | Content | Link |
|---|---|---|---|
| `tulporgo_by_tulporgobot` | static stickers | 51 × 512 WEBP | https://t.me/addstickers/tulporgo_by_tulporgobot |
| `tulporgo_anim_by_tulporgobot` | video stickers | 51 × WEBM (2 s hop) | https://t.me/addstickers/tulporgo_anim_by_tulporgobot |
| `tulporgo_emoji_by_tulporgobot` | custom emoji | 51 × **vector TGS** (replaced in place from blurry 100 px PNG) | https://t.me/addemoji/tulporgo_emoji_by_tulporgobot |
| `tulporgo_reactions` | custom emoji, head close-ups | 24 × vector TGS — **created 2026-11-11 via @Stickers from Saidakbar aka's account** | https://t.me/addemoji/tulporgo_reactions |
| `tulporgo_icons` | custom emoji, interface icons | 14 × animated vector TGS (`brand/icons/tgs`) — **created 2026-11-11 via @Stickers** | https://t.me/addemoji/tulporgo_icons |

### ✅ "TulporGo Reactions" pack — RESOLVED 2026-11-11

- The bot kept getting `429` (7 attempts, the last 2026-11-11 00:30), so on Saidakbar aka's request ("@Stickers da
  yarataqol accountim orqali") Claude drove @Stickers from his account: `/newemojipack` → Animated → "TulporGo
  Reactions" → 24 TGS + emoji (mapping of `create_sticker_sets.py`) → `/publish` → `/skip` → short name
  `tulporgo_reactions`. Verified with Bot API `getStickerSet`: 24, all animated, `custom_emoji`, emoji order as planned.
- **Do NOT run `create_sticker_sets.py reactions`** any more — it would try to create a second, bot-owned copy
  (`tulporgo_reactions_by_tulporgobot`). The history below is kept for reference.

### (history) Blocker: "TulporGo Reactions" pack

- `createNewStickerSet` returns `429 {"retry_after":301}` on **every** attempt — 6 attempts
  2026-11-09 22:20 … 2026-11-10 04:08 (hourly gaps didn't help). Likely a per-bot daily
  set-creation limit (bot created 3 sets on 2026-11-09). Logged as MUAMMOLAR #26.
- **2026-11-11 00:30 (Saidakbar aka: "hozir urinib ko'r"): attempt 7 → again `429 retry after 301`**, although more than
  24 h had passed since the 3 sets were created — so not a plain daily limit. The scheduler listed **no** tasks (the
  10:00 task below never registered). The guard allows the next attempt from **2026-11-11 20:30**. Fallback: he creates
  the pack himself in @Stickers (`/newemojipack`).
- (superseded) A scheduled task was meant to make ONE attempt on 2026-11-11 10:00 (+05:00):
  `C:\Users\nsn\.claude\scheduled-tasks\tulporgo-reactions-create\SKILL.md` (**deleted 2026-11-11** on his OK; one-shot, bypass mode,
  runs only while the Claude app is open). Check its result before doing anything else; don't
  start a parallel attempt.
- ⚠ Measured 2026-11-10 12:15 by the next agent: the app log says the task was saved
  (`[CCDScheduledTasks] Saved scheduled task: tulporgo-reactions-create`, 04:07:46), but the
  `scheduled-tasks` MCP in a new session lists **no tasks** and `list_task_runs` says "not found".
  The app also logs `Deferring dispatch this tick: memory pressure critical` (RAM 0.7 GB free of
  31.8 GB; WSL ≈ 6.9 GB, 39 `claude` ≈ 5.5 GB, 74 `node` ≈ 3.5 GB, 78 `python` ≈ 2.7 GB).
  So the 10:00 run is **not guaranteed** — check `getStickerSet` after 10:00. A backup scheduled
  task (10:30) was offered on 2026-11-10 and Saidakbar aka **declined** it — don't create one; if the
  set is still missing after 10:00, report and wait for his call.
- **Double-attempt guard** (2026-11-10): `create_sticker_sets.py` now records every
  `createNewStickerSet` attempt in `content/prototype/create_attempts.json` *before* the call and
  refuses another one for the same set within 20 h (`attempt_guard.py`, `TG_CREATE_COOLDOWN_H`;
  `TG_FORCE_CREATE=1` overrides; corrupt state or a held lock → refuse). Seeded with the last real
  attempt (2026-11-10 04:08), so the earliest allowed attempt is 2026-11-11 00:08. Two runners
  (scheduled + manual/backup) can therefore not both hit the API. Tests:
  `content/prototype/test_attempt_guard.py` (9, mutation-checked).
- Manual command (one attempt, no internal retry):
  ```bash
  cd /d/Linux/coding/taxi-bot/content/prototype
  PYTHONIOENCODING=utf-8 TG_MAX_WAIT=0 python create_sticker_sets.py reactions
  ```
  Idempotent: if the set exists it only adds missing stickers. After success verify with
  `getStickerSet`: 24 stickers, all `is_animated`, `sticker_type == custom_emoji`; send him the
  link via the bot; mark MUAMMOLAR #26 done.
- Fallback he knows about: he creates it himself in @Stickers (`/newemojipack`) from
  `brand/mascot/poses/vector/telegram/emoji_head_tgs/*.tgs` (slug would then not end in `_by_tulporgobot`).
- Pack decisions (made by him): shape **rounded square**, only emotion/gesture poses
  (24, list in `head_set.txt`), title **"TulporGo Reactions"**, crops adjusted (`head_adjust.txt`).

### Tests
`cd brand/mascot/poses/vector && python -m pytest -q` → **33 passed** (2026-11-10, incl. `test_png_holes.py`).
`cd content/prototype && python -m pytest -q` → **13 passed** (attempt guard + in-place replace).
`directions/test_*.py` are plain scripts with asserts — run `python test_x.py` (pytest collects 0);
both print PASS.

## 4. Vector / Telegram pipeline (brand/mascot/poses/vector)

Driven from bash; Illustrator 2025 runs via COM: `run.ps1 -Jsx <file.jsx> -Names a,b,c`
(names go through `batch.txt`). Illustrator must be installed and not busy with a modal dialog.

```
src PNG → prep_src.py (magenta bg, per-pose thresholds prep_overrides.txt)
        → trace_poses.jsx (Image Trace, settings.txt "24,50,50,25") → raw/
        → drop_magenta.py → brand_snap.py (palette 09) → clean/
        → export_poses.jsx (variant.txt: full | ns | em; border.txt "14,24": vector closing border,
          94 % normalise) → svg/ ai/ png/ | svg_ns/ png_ns/ | svg_em/ png_em/
        → fill_holes.py (fills small holes in <g id="sticker-border"> in the SVG)
        → check_final.py (islands ≤ 4, border, size) 
telegram_export.py (fills border holes via png_holes.py) → telegram/{sticker,emoji,video,video_emoji}/
SVG → lottie_convert (python-lottie 0.7.2, 512, 60 fps) → tgs_optimize.py (≤ 64 KB) → telegram/emoji_tgs/
      (source per pose: tgs_source.txt — svg_em for 22,25,26,27,32, else svg_ns)
head emoji: head_rects.py (+head_adjust.txt) → emoji_head.jsx (optional head_opts.txt, default "rr,emoji_head")
      → emoji_head/ → TGS → telegram/emoji_head_tgs/ (24, max 40 KB)
telegram_check.py — validates all Telegram outputs (limits, fps, size, duration, sticker border holes)
tgs_render.py — TGS → screenshot sheet (headless Edge) for visual review
```
Full runs: `pipeline.sh` (v3), `reexport.sh`. Review sheets: `brand/mascot/poses/review/*.png`.

Gotchas (all in MUAMMOLAR.md):
- ExtendScript: no nested ternaries (evaluates wrong) — use if/else; `//` comment eats the rest of a line.
- After `applyEffect` reselect the item before `expandStyle`.
- TGS colours must keep 3 decimals (integer rounding destroys colours); merging paths only with identity transforms.
- Bot API 429: `create_sticker_sets.py` stops when `retry_after > TG_MAX_WAIT` (default 60). `TG_PACE` paces replace calls. Never loop on 429.

## 5. Open work (priority order)

1. **Reactions pack** — see §3 blocker.
2. ~~Border holes in the static + video sticker packs~~ — **DONE 2026-11-10** (MUAMMOLAR #27, #28):
   `png_holes.py` fills them at export, 10 poses re-exported and replaced in place in both packs
   (`create_sticker_sets.py replace static|video <names>`), verified on files downloaded back from
   Telegram (0 holes, 51/51). Originals: `telegram/_before_holes_2026-11-10/`.
3. ~~Verdict on poses 21–50~~ — **DONE 2026-11-10**: all 31 approved as-is (`poses/INDEX.md`,
   review sheets `poses/review/verdict-*.png`). All 51 poses are now approved; packs unchanged.
3b. **Emoji system (decision 39, 2026-11-10)**: interface = own TulporGo icons (`brand/icons/`, 14, **animated vector TGS** via `icons_tgs.py`, official TGS rules checked),
   emotion = tulpor head (Reactions), max 1 official animated accent per message (`content/i18n/emoji_system.py`).
   ✅ 2026-11-11: dedicated packs `tulporgo_icons` + `tulporgo_reactions` exist (via @Stickers, his account); their ids are in
   `brand/icons/pack_ids.json` (`brand/icons/pack_ids.py`), `emoji_system.py` and `content/i18n/build/emoji_map.json` use them
   (verified in a real bot message), and the 15 test emoji were removed from `tulporgo_emoji_by_tulporgobot` (back to 51).
   Head emoji (Reactions, 24 TGS) stay **static** — animation offered 2026-11-10, Saidakbar aka: "hozircha kerak emas".
4. Bot avatar (02 on yellow), description; channel @tulporgo, groups @tulporgo_chat + hidden drivers
   group, Community (decisions 26–31). Full staged plan: `TELEGRAM-REJA.md`. Stage 1 texts (5 languages, `content/i18n/`) **APPROVED 2026-11-10 (decision 40)**.
   Stage 2 visuals drafted 2026-11-10 and shown via bot: `brand/telegram/avatars.py` (bot yellow + solid black 02 —
   the yellow body vanishes on yellow; channel black; chat white or white + yellow ring; drivers black + wheel badge),
   `visuals.py` (channel welcome 1280x720, RM panorama carousel with poses 05/06/08 on the borders), `send_stage2.py`.
   Q&A avatar: white + yellow ring (chosen 2026-11-10, decision 31). Stage 2 **APPROVED 2026-11-10 (decision 41)**.
   Stage 3 DONE 2026-11-10 (his go-ahead "Ha, o'rnat"): `content/i18n/apply_bot_profile.py` set avatar (bot.jpg),
   short description, description, 4 commands for default/uz (new alphabet), ru, en; read back = OK; re-run changes 0
   (idempotent); live avatar matches source (mean diff 0.61). Backup of old values: `content/i18n/build/bot_profile_before.json`.
   Not set: menu button (no Mini App), "coming soon" reply (needs an always-on process), driver commands.
   Stage 4 (his go-ahead "Ha, yarat"): channel + Q&A + drivers created PRIVATE 2026-11-10, all titled "TulporGo"
   (decision 28); ids in `brand/telegram/chats.json`; avatars, about texts, @tulporgobot admin (no add-admins/change-info),
   member perms (no self-tags/topics; drivers: no invites) — verified via Bot API. chigwell `edit_chat_photo` refuses paths
   outside its roots → photos via overpod `telegram-edit-group`. No tool can set public usernames, Welcome Messages or
   Communities → Saidakbar aka does them in the app (`brand/telegram/send_launch_kit.py` sent him steps + materials).
   2026-11-10 (his request "o'zing bajara oladigan qil"): dedicated Telethon session for @menarzullayev
   (`~/.mcp-telegram/claude-tulporgo-admin/.env`, device "TulporGo admin (Claude)", own QR login + his 2FA typed by him)
   + `brand/telegram/tg_admin.py` (bot-rights | welcome | community | usernames | status). DONE and verified:
   bot manage_welcome_messages in all 3; Welcome Messages in all 3 (channel with photo, custom emoji, collapsed RU;
   `ephemeral.SendMessage(welcome=True, receiver_id=InputUserEmpty)` — InputUserSelf gives MESSAGE_NOT_COMMAND);
   Community "TulporGo" id 1098470603512: channel/chat/bot visible, drivers HIDDEN (CommunityFull.linked_peers),
   members can't add chats (default_banned_rights.manage_linked_peers); channel PUBLIC @tulporgo (live, t.me ok).
   @tulporgo_chat was blocked by CHANNELS_ADMIN_PUBLIC_TOO_MUCH (9 public chats). On his instruction ("rankwant_chat
   yopiq qoladi hozircha") @rankwant_chat ("RankWant Muhokama", id 4421064288) was made PRIVATE — group and members kept,
   restore data in `brand/telegram/released_usernames.json` — then Q&A became PUBLIC @tulporgo_chat (verified: MTProto,
   t.me, Bot API). ⚠ Any t.me/rankwant_chat links (RankWant site/posts) are now dead; restoring needs a free public slot.
   Stage 4 DONE. The account is at its public-chat limit: a new public chat needs a slot freed first.
   «Tez orada» stub LIVE 2026-11-10 (his "Ha, qo'y"): `bot/coming_soon.py` (stdlib long polling; private chats only,
   1 reply/chat/min, backlog skipped, approved bot.coming_soon text in ru/en/uz_new + 🚀 accent + "Kanalga o'tish" →
   t.me/tulporgo with icon), Task Scheduler "TulporGo coming-soon bot" (pythonw, at logon, restart every 1 min),
   `bot/install_autostart.ps1`; log `bot/coming_soon.log` (counts/errors only). Measured: real /start → reply in 2.1 s.
   ⚠ It long-polls getUpdates permanently: any other getUpdates caller gets 409 Conflict. `send_variants.owner_chat()`
   now uses the cached `.secrets/owner_chat_id` first; `content/i18n/collect_emoji_map.py` would conflict — stop the task
   first (`Stop-ScheduledTask -TaskName "TulporGo coming-soon bot"`). Replace the stub with the real aiogram bot later.
   Fixed 2026-11-10 after a power cut: the single-instance check used os.kill with signal 0, which on Windows
   TERMINATES that pid (logs show nothing was killed that time). Now an OS file lock (msvcrt/fcntl, released by the OS
   on any death) and in-process network retries instead of re-exec; tests incl. crash/stale-lock + no-os.kill guard. Domain tulporgo.uz: whois (whois.cctld.uz, 2026-11-10)
   `Status: ACTIVE`, created 09-Nov-2026, expires 09-Nov-2027, NS ns1–ns4.eskiz.uz. DNS zone at Eskiz (2026-11-11,
   verified via ns1.eskiz.uz and 1.1.1.1): `www` CNAME tulporgo.uz, TXT `v=spf1 -all`, `_dmarc` TXT `v=DMARC1; p=reject`
   (the domain sends no mail), CAA `0 issue "letsencrypt.org"`; Eskiz defaults (apex/ftp/mail/webmail A, MX) removed;
   WHOIS contacts hidden. **No apex A record yet** — add it (→ VPS IP) after the VPS is bought.
5. Brand guide; post templates finalisation (decisions 32–37).
6. Product open work (2026-11-11) — the code is built, see §7 and `PROGRESS.md`:
   - **Owner-only blockers:** VPS purchase + deploy (`docs/DEPLOY.md`) and the DNS A record for tulporgo.uz at Eskiz;
     lawyer review (`docs/legal/README.md`, 8 questions); legal status (YATT/MChJ) + Click/Payme merchant contracts;
     BotFather Login Widget client secret; after deploy: R2 values from `.secrets/r2.env` into `deploy/.env` and the
     VPS IP on the R2 token (decision 62; account, bucket and token are ready and verified); BotFather
     "Configure Mini App" + menu button (`getMe.has_main_web_app=false`).
   - **Owner to confirm (rules the agents chose, not in QARORLAR):** 3 open requests per passenger, max price
     5 000 000 so'm, request TTL 120 min / offer TTL 30 min; userbot 5-minute absolute floor; userbot posts in the
     driver's language (new alphabet in public groups); rejected documents delete the server copy; a Stars refund
     shortens the subscription; the share page shows the car plate; a driver cancelling before start reopens the request.
   - **Later:** other regions' mahallas (+22 missing in Samarqand); new-alphabet spelling rules (decision 16); the
     userbot *reading* groups to pick up passenger requests (decision 8 — not built, it only posts); Click/Payme sandbox
     consoles; watch blocked driver accounts in the first weeks of auto-posting.
7. ~~Bot code itself~~ — **DONE 2026-11-10** (`/goal` build, closed by Saidakbar aka): see §7.

## 6. First 5 minutes for a new agent

1. Read `C:\Users\nsn\.claude\CLAUDE.md`, this file, `QARORLAR.md`, `poses/vector/MUAMMOLAR.md`.
2. Emoji packs are done (`tulporgo_icons`, `tulporgo_reactions`, 2026-11-11; §5 item 3b). Open work: §5 item 6.
3. `uv run pytest -q` at the repo root → ≈1 290 passed; `python -m pytest -q` in `brand/mascot/poses/vector` → 33 passed.
4. Greet "Saidakbar aka" in Uzbek with a 3-line status and ask which open item to take.

## 7. Build goal (2026-11-10)

Decisions 42–54 (QARORLAR.md) and `GOAL.md`: bot + driver side + driver userbot + Mini App built together; VPS in
Uzbekistan; free 1–2 months but P2P/Stars/Click/Payme integrated now; no deadline; foundation first (Phase 0, Claude),
then 4 parallel worktree agents (W1 bot, W2 userbot, W3 Mini App + API, W4 payments + referral). Public repo with
internal docs; brand only final deliverables (`.gitignore`), third-party refs excluded; code AGPL-3.0, brand rights
reserved (`BRAND.md`).
Status 2026-11-10 (end of the `/goal` build) — **live status is `PROGRESS.md`**, read it first:
- Phases 0, 1 and the code part of 2 are done and on `main`: `packages/core` (models, services, Alembic 0001, places,
  i18n, privacy export/delete), `apps/bot` (W1), `apps/userbot` (W2), `apps/api` + `apps/miniapp` (W3),
  `packages/payments` (W4), `tests/e2e`, `tests/contract` (`docs/openapi.json`), `deploy/` (Compose, Caddy, backups,
  restore test, VPS scripts, runbook `docs/DEPLOY.md`), legal drafts `docs/legal/` (uz/ru).
- Checks: `uv run pytest -q` (≈1 290), `uv run mypy`, `uv run ruff check packages apps tests`,
  `npm --prefix apps/miniapp test`, `python tools/secret_scan.py`. Test helpers are `*_fixtures.py` / `bot_harness.py`,
  never a second `conftest.py` (it shadows `packages/core/tests/conftest.py`).
- GOAL §4 features (decision 55): ON — `TULPORGO_EPHEMERAL_GROUP`, `TULPORGO_WIDGETS`, Guest Mode (BotFather Guest
  Chat Mode enabled); Login with Telegram once `TULPORGO_LOGIN_CLIENT_SECRET` is set. **OFF — trip topics**
  (`TULPORGO_TRIP_TOPICS=false`, decision 59: BotFather Threaded Mode adds a fee to Stars purchases).
  Migrations: 0001 initial, 0002 trip topics, 0003 driver documents. Public legal pages: `/legal/<doc>?lang=uz|ru`.
- Decided 2026-11-10/11 (QARORLAR 56–60): Stars 165 so'm; driver documents encrypted on the server + Telegram copy;
  backups monthly, 1 copy, encrypted copy to R2; topics not enabled, Guest Chat Mode enabled; the my.telegram.org app
  renamed TulporGo — its `api_id`/`api_hash` are in `.secrets/telegram_app.env` (verified with Telegram; copy to the
  server `.env` at deploy). Still blocked on the owner: see §5 item 6.
- The PC stub `bot/coming_soon.py` still answers @tulporgobot; stop its scheduled task before the bot runs anywhere
  else (one `getUpdates` consumer per token).
