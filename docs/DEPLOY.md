# Deploying TulporGo (decision 43: one VPS in Uzbekistan)

Everything runs with Docker Compose from `deploy/`. Personal data (database, backups, encrypted userbot sessions)
stays on the server in Uzbekistan — do not copy dumps to storage abroad (Telegram, foreign clouds).

## What runs

| Service | Image | Role |
|---|---|---|
| `postgres` | `postgres:17-alpine` | primary database (volume `pgdata`) |
| `redis` | `redis:7.4-alpine` | event bus between bot, API and userbot worker (no persistence) |
| `migrate` | `tulporgo-app` | one-shot: `manage migrate` + `manage seed-places`, every start |
| `api` | `tulporgo-app` | FastAPI on :8000 (health: `/api/health`) |
| `bot` | `tulporgo-app` | aiogram polling — profile `telegram` |
| `userbot` | `tulporgo-app` | Telethon worker for drivers' accounts — profile `telegram` |
| `proxy` | `tulporgo-proxy` | Caddy: HTTPS (Let's Encrypt), Mini App at `/app/`, `/api/*` → api — profile `web` |
| `backup` | `postgres:17-alpine` | monthly `pg_dump` (decision 58), keeps the newest one |
| `offsite` | `tulporgo-app` | encrypts each new dump here and copies it to Cloudflare R2 (one copy kept) |

`COMPOSE_PROFILES=web,telegram` in `deploy/.env` turns everything on.

## Server requirements

- Ubuntu 24.04 LTS, 2 vCPU, 4 GB RAM, 40 GB SSD is enough for the pilot (Samarqand).
- A public IPv4 address; DNS `A` record `tulporgo.uz` → that address (Eskiz panel).
- Ports 80 and 443 reachable from the internet (Let's Encrypt HTTP challenge).

## First deploy

```bash
# as root, once
curl -fsSL https://raw.githubusercontent.com/menarzullayev/tulporgo/main/deploy/scripts/bootstrap-vps.sh -o bootstrap.sh
less bootstrap.sh
bash bootstrap.sh
```

```bash
# as the deploy user
sudo -iu tulporgo
cd /opt/tulporgo/deploy
cp .env.example .env && chmod 600 .env
nano .env        # POSTGRES_PASSWORD, TULPORGO_BOT_TOKEN, TULPORGO_USERBOT_ENCRYPTION_KEY, admin ids, ...
./scripts/deploy.sh
```

Before the `telegram` profile starts on the VPS, **stop the PC "coming soon" stub** (Task Scheduler task
`TulporGo coming-soon bot`): Telegram allows only one `getUpdates` consumer per token.

Three keys are generated on the server and kept offline as well (password manager) — without them encrypted data is lost:
`TULPORGO_USERBOT_ENCRYPTION_KEY` (driver sessions), `TULPORGO_DOCUMENTS_ENCRYPTION_KEY` (driver documents, decision 57)
— both Fernet: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — and
`TULPORGO_BACKUP_ENCRYPTION_KEY` (off-site backups, decision 58): `python -m tulporgo_core.offsite keygen`.

## Telegram features (on by default, decision 55)

Approved by Saidakbar aka on 2026-11-10. Each is a switch in `deploy/.env` (`false` turns it off), then
`./scripts/deploy.sh`. Old clients always get the plain card / plain reply.

| Variable | What it does | Extra step |
|---|---|---|
| `TULPORGO_TRIP_TOPICS` (default **false**, decision 59) | one topic per trip in each party's chat with the bot | needs BotFather → Bot Settings → Threaded Mode, which adds a fee to Telegram Stars purchases |
| `TULPORGO_EPHEMERAL_GROUP` | `/taksi`, `/yordam` in groups answered only to the asking user | — |
| `TULPORGO_WIDGETS` | trip-status HTML widget in private chats | — |
| `TULPORGO_LOGIN_CLIENT_SECRET=<secret>` | "Login with Telegram" on tulporgo.uz outside Telegram (OpenID Connect) | BotFather → Bot Settings → Login Widget: origin `https://tulporgo.uz`, redirect `https://tulporgo.uz/api/auth/telegram/callback` |

## Every later deploy

```bash
cd /opt/tulporgo/deploy && ./scripts/deploy.sh            # deploys origin/main
```

`deploy.sh` fetches, builds images tagged with the commit, takes a backup, starts the stack, waits for the API health
check, verifies the database is at the head migration (`manage check`) and calls `https://<domain>/api/health`.
It prints the live commit and appends it to `deploy/deployed.log`. On failure it prints the rollback command:

```bash
./scripts/deploy.sh <previous-commit>
```

Migrations only add (expand first, remove later), so rolling back the code never needs a database downgrade.

## Backups (decision 58)

- Automatic: **one `pg_dump` a month** (`BACKUP_DAY_OF_MONTH`, default the 1st, at 22:00 UTC = 03:00 Tashkent), and one
  before every deploy. Only the newest dump stays on the server (`BACKUP_KEEP_COUNT=1`):
  `deploy/backups/tulporgo-<UTC timestamp>.dump`.
- Manual (any time — Saidakbar aka does these by hand between the monthly ones):
  `docker compose run --rm backup --once`
- Off-site: the `offsite` service encrypts every new dump **on this server** (streaming AES-256-GCM, key
  `TULPORGO_BACKUP_ENCRYPTION_KEY`, generate with `docker compose run --rm --no-deps offsite python -m
  tulporgo_core.offsite keygen`) and copies only the ciphertext to Cloudflare R2 (`TULPORGO_R2_*`); R2 keeps the newest
  copy only. **Keep the key offline too** (password manager): without it the R2 copy cannot be read. R2 is outside
  Uzbekistan — see the lawyer question in `docs/legal/README.md`.
- Prove a dump restores (throwaway container, live DB untouched): `./scripts/restore-test.sh`.
- Restore from R2: download the `.enc` object from the R2 dashboard into `deploy/restore/`, then
  `docker compose run --rm --no-deps --user root -v "$PWD/restore:/work" offsite python -m tulporgo_core.offsite decrypt /work/<file>.enc /work/<file>.dump`
  and `./scripts/restore.sh restore/<file>.dump --yes` (replaces the live database; takes a safety dump first).

Verified locally on 2026-11-10 (Docker 29.8): two manual dumps leave exactly one file; the `offsite` service copied the
new dump to an S3-compatible store (SeaweedFS standing in for R2) as ciphertext only (no `PGDMP` marker), the
downloaded object decrypts byte-for-byte to the local dump, and after the next dump the store again holds one object;
`restore-test.sh` OK. A truncated or tampered encrypted file and a wrong key are refused (`packages/core/tests/test_offsite.py`).

## Useful commands

```bash
docker compose ps
docker compose logs -f --tail=100 bot
docker compose run --rm --no-deps migrate python -m tulporgo_core.manage check
docker compose exec postgres psql -U tulporgo tulporgo
```
