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
| `backup` | `postgres:17-alpine` | daily `pg_dump` at `BACKUP_AT_UTC` (22:00 UTC = 03:00 Tashkent), keeps `BACKUP_KEEP_DAYS` |

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

`TULPORGO_USERBOT_ENCRYPTION_KEY` encrypts every driver session. Keep a copy offline (password manager): without it,
backups of `userbot_accounts` cannot be decrypted and drivers must log in again.

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

## Backups

- Automatic: `deploy/backups/tulporgo-<UTC timestamp>.dump` (PostgreSQL custom format), daily + before every deploy.
- Prove they restore (throwaway container, live DB untouched): `./scripts/restore-test.sh` — run it weekly and after
  changing anything in the backup setup. Check an older file: `./scripts/restore-test.sh tulporgo-<ts>.dump`.
- Restore into the live database (destructive, takes a safety dump first): `./scripts/restore.sh backups/<file> --yes`.
- Off-server copy: **open item for the owner** — a second storage location inside Uzbekistan (another VPS or a local
  disk via `scp`). Not automated until that location exists.

Verified locally on 2026-11-10 (Docker 29.8): stack up, `migrate` at head with 1 301 places, API healthy, dump →
restore into a throwaway PostgreSQL with identical tables and row counts; a truncated dump is rejected, `restore.sh`
refuses without `--yes`.

## Useful commands

```bash
docker compose ps
docker compose logs -f --tail=100 bot
docker compose run --rm --no-deps migrate python -m tulporgo_core.manage check
docker compose exec postgres psql -U tulporgo tulporgo
```
