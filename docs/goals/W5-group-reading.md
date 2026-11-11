# W5 — Reading taxi groups for drivers (decisions 8, 73)

Built **before the launch** (decision 72: closed test, then the PC deploy). Today the userbot only posts the driver's ad
(W2). This adds the other half of decision 8: one reader account per group watches it live, finds passenger (and
parcel / cargo / delivery / bazaar) requests, and each matching driver gets a card from @tulporgobot in his own channel.

Owner decisions are in `QARORLAR.md` 72–73; this file is how to build them. Language rules: code and docs in English,
user texts in Uzbek (new alphabet in channel/bot texts per decision 29) and Russian.

## Flow

```
group x1 ── new message ──> reader account (one per group, live Telethon connection)
   └─> normalise → classify (request / driver ad / other) → parse (type, from, to, time, seats) → confidence
         └─ low confidence → local AI (interface only in v1; model chosen later)
   └─> dedupe (same author + route + time, or same text, within 30 min → one event, groups listed)
   └─> match against the filters of TulporGo drivers who are members of that group
         └─> card via @tulporgobot to the driver's own channel/group (fallback: bot chat)
               Biznes at once, other plans after 60 s (decision 73)
   └─> nothing stored; cards deleted by the bot after 2 h
```

## Checklist

1. **Membership map** — from the existing groups sync (`UserbotGroup`: account × chat). A group is readable when at
   least one connected, consented account is a member. Only groups a driver marked as taxi groups count.
2. **Reader assignment** — one reader per group (table `group_readers`: chat_id → account_id, assigned_at). Prefer
   the account that already reads the most groups (fewest live connections), skip accounts in FloodWait or paused.
   When a reader stops (logout, ban, flood, offline > N min) the group moves to the next member within a minute.
   Readers only read: no sends, no reactions, no "mark read" side effects beyond what Telethon does by default.
3. **Live reading** — reader clients stay connected (`events.NewMessage(chats=assigned)`); measure memory per client
   on the PC (decision 70: Docker VM 10 GB shared) and record it in PROGRESS before the closed test.
4. **Detection** — extend `tulporgo_core.parser`: request type (passenger, parcel, cargo/luggage flag, delivery,
   bazaar trip), driver-ad vs request classification (start from `D:\Linux\coding\taxi-analysis\classify_lib.py`
   patterns), seats, "hozir/srochno", tomorrow. Returns a confidence. A `Classifier` protocol with the rule-based
   implementation now and a slot for a local model later (decision 73) — no external AI service (localisation).
5. **Landmarks** — places data gets landmarks (bazaars incl. Mayiz bozor and Mol bozor, vokzal, aeroport, hospitals) with
   spelling variants and the district they belong to. Claude drafts the list, Saidakbar aka approves it.
6. **Driver filters** — table `driver_filters`: name, enabled, routes (district level, optional mahalla, "on the way"
   flag, reverse-route helper), time window (+ include "no time / now", include tomorrow), weekdays, seats min/max,
   request types, groups (all or chosen). Several per driver; plan limits (Asosiy / Pro / Biznes) as settings.
7. **Delivery chat** — the driver links his channel/group: adds @tulporgobot as admin, the bot confirms with a test
   card; stored as `drivers.delivery_chat_id`. Not linked → cards go to the bot chat.
8. **Card** — rich message (decision 69) with a plain-text fallback: type, route, time, seats, groups with message
   links (`t.me/c/...` works for members), author username when public. Buttons: open message, "Olindi" (hides it for
   this driver), pause filter. Biznes immediately, others after 60 s; the bot deletes cards after 2 h.
9. **Mini App + bot** — Mini App: filter list and editor, delivery chat status. Bot: quick toggles (filter on/off,
   pause all) in the `/elon` menu.
10. **Consent and privacy** — userbot consent gets the clause "your account may watch the groups you are in for
    TulporGo drivers; it only reads" (uz/ru) and a new consent version (re-accept on next open). Privacy policy gets
    a "group messages" section: what is read, nothing stored, cards removed after 2 h, who sees a card (members of
    that group only). Texts by Claude, approved by Saidakbar aka.
11. **Tests (each rule with a negative case)** — driver ads never become cards; a driver who is not a member of the
    group gets nothing; non-matching filter/time/weekday/type gets nothing; Biznes before others (60 s); duplicates
    across groups → one card; reader failover; nothing about the message is written to the database; cards deleted
    after 2 h; a reader never sends to a group.

## Status (2026-11-11)

| Item | State | Where |
|---|---|---|
| 1–2 membership, one reader per wanted group, failover | done | `tulporgo_core/services/groupfeed.py` (`assign_readers`) |
| 3 live reading on the shared client | done; memory per reader **not measured yet** (needs real accounts) | `apps/userbot/tulporgo_userbot/reader.py`, `client.py` |
| 4 detection (kinds, driver ads, single place) | done, rule-based; local-AI slot = `Classifier` | `tulporgo_core/groupscan.py` |
| 5 landmarks | done: owner-approved villages, bazaars, station, airport; corridor Qo'shrabot→Dagbit→Samarqand (decision 74); M39 still a draft | `data/landmarks.csv`, `data/corridors.csv` |
| 6 filters | done | `DriverFilter`, migration 0005 |
| 7 delivery chat | done: making @tulporgobot an admin links it | `feedbot.py` |
| 8 card | plain HTML + buttons (works on old apps; decision 69 is for channel posts), Biznes first, 2 h cleanup | `cards.py`, `reader.py` |
| 9 Mini App + bot | done: `#/feed` / `?page=feed`, /elon → "Yo'lovchi qidirish" | `apps/miniapp/src/screens/Feed.tsx`, `feedapi.py` |
| 10 consent + privacy | done: consent version 2, privacy "group messages" | `locales/userbot.py`, `docs/legal/` |
| 11 tests | done, each rule with a negative | core, userbot, api, miniapp tests |
| Deleted request (decision 75) | done: when every copy of a request is deleted, its cards are struck through, lose their buttons and go after 10 min; a card still waiting 60 s is never sent | `reader.handle_delete`, `cards.render_gone` |
| Dry run on the PC with real accounts and groups | **in progress** — driver1 connected, 6 taxi groups picked (2026-11-11); 2-min smoke run OK; daytime observation next (latency, memory, request lifetime) | `tools/feed_dryrun.py` |
| Basic plan | done (decision 74): connects to read only, up to 15 groups, no posting | `service.selection_limit` |

## Done when

- all checklist items merged with tests; CI green;
- a dry run on the PC with 2–3 real accounts and 3+ real groups: cards arrive within seconds, Biznes delay holds,
  no duplicates, reader memory measured;
- consent and privacy texts updated and approved;
- then decision 72's order continues: PC deploy (`docs/RUN-ON-PC.md`) → 1–2 weeks closed test → wide launch.

## Later (not in v1)

- local AI model for uncertain messages (free model or trained on a one-off export of group history — decision 73);
- statistics for drivers (how many requests per route/hour in their groups).
