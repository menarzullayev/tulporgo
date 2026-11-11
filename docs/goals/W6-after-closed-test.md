# W6 — after the closed test: passengers, driver value, payments, accuracy (decisions 76–80)

Agreed with Saidakbar aka in a wide discussion on 2026-11-12. **Nothing here starts before the 1–2 week closed test
ends** (decision 80); the launch order stays W5 dry run → PC deploy → closed test → wide launch.

**First constraint for every item: a driver's Telegram account must not get blocked.** Any feature that makes a
driver account send more, or send links, is opt-in, keeps decision 48's limits, and is measured (blocked accounts per
week) before it reaches everyone.

## Why (measured 2026-11-11)

Six real taxi groups, 14 days, read-only: ~1 100 driver ads, ~12 passenger requests left in the history — passengers
delete their post once they have a taxi because drivers keep calling (decision 75). Supply is plentiful; a passenger
has no easy way to find the right car, and a request lives only minutes. The product's value is matching fast.

## Checklist

1. **"Ketayotgan mashinalar" board (decision 76)** — Mini App screen, searchable by route (district level, the same
   `route_matches` as the feed) and date/time. Source: each driver's structured post template (`UserbotAccount.post_template`:
   from, to, time, seats, price) — never group text. Shows every driver, trial included. Order: nearest departure first;
   Biznes badge and wins ties. Contact, chosen per driver: (a) "Joy band qilish" → a booking request to the driver in the
   bot, the passenger's phone revealed only when the driver accepts; (b) open phone / Telegram link.
2. **Regular route subscription (decision 76)** — a passenger saves "every weekday 07:30 Qovunchi → Samarqand"; each
   evening the bot sends tomorrow's matching cars from the board. Plain text + buttons fallback for old apps.
3. **Reaching passengers (decision 77)** — Guest Mode reply gets a "Ketayotgan mashinalar" button (Guest Mode itself is
   built: `apps/bot/tulporgo_bot/handlers/guest.py`); channel and mahalla-group announcements only after the owner
   approves each post; a TulporGo link at the end of a driver's auto-post — **opt-in, off by default**, with a risk
   warning, blocked-account count tracked; a shareable "my trips" link per driver.
4. **"N drivers contacted" on feed cards (decision 78)** — the "Olindi" tap increments a counter shown on every card
   of the same request (in memory with the request, like decision 75's sources); no locking.
5. **Demand map (decision 78)** — counts of detected requests per route × hour (no text), Pro and Biznes only.
6. **Smart post timing (decision 78)** — opt-in; shifts posts towards high-demand hours inside decision 48's limits;
   never more posts.
7. **Payments (decision 79)** — Telegram Stars subscriptions (`createInvoiceLink` with `subscription_period`, currency
   `XTR`) next to card/P2P, both in the bot (owner accepted the risk of Telegram's bot developer terms 6.2). The card/P2P
   path must be switchable off with one setting; if Telegram sends a notice, switch to Stars only at once. Star amounts are
   set so the driver pays about the same so'm price (we carry the store fee; 0.013 USD per Star to the developer, held up
   to 21 days). Tariffs re-checked with closed-test usage data.
8. **Accuracy (decision 80)** — "Noto'g'ri" button on feed cards ("not a request" / "wrong route"): only counts and the
   error type are stored, never the text; weekly precision. Plus a monthly manual survey like
   `tools/feed_dryrun.py`-based checks.
9. **Local AI (decision 80)** — after the closed test the owner exports his taxi groups' history (his PC only, phone
   numbers masked); label, train a small local model behind `groupscan.Classifier`; measure disk first (CLAUDE.md
   ML rules: reuse an existing torch venv, models only in `HF_HOME`).

## Telegram features used

Guest Mode (10.0), Stars subscriptions, `date_time` entity (9.5) on board and cards, colored buttons (9.4) with plain
fallbacks. Widgets (10.4) are not used until aiogram supports them.

## Done when

Each item merged with tests (each rule with a negative case), CI green, and for items 3, 6 and 7 the blocked-account
count measured over two weeks.
