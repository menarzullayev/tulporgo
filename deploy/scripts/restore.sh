#!/usr/bin/env bash
# Restore a backup into the LIVE database. Destructive: current data is replaced.
#   deploy/scripts/restore.sh deploy/backups/tulporgo-20261110T220000Z.dump --yes
set -euo pipefail
cd "$(dirname "$0")/.."

dump="${1:-}"
[[ -f "$dump" ]] || { echo "usage: $0 <file.dump> --yes" >&2; exit 2; }
[[ "${2:-}" == "--yes" ]] || { echo "refusing: this replaces the live database; add --yes" >&2; exit 2; }

echo "restore: stopping writers"
docker compose stop api bot userbot >/dev/null 2>&1 || true
echo "restore: safety dump of the current state first"
docker compose run --rm backup --once
echo "restore: $dump"
docker compose exec -T postgres pg_restore --clean --if-exists --no-owner -U tulporgo -d tulporgo < "$dump"
docker compose run --rm --no-deps migrate python -m tulporgo_core.manage check
docker compose up -d
echo "restore: done"
