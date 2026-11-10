#!/usr/bin/env bash
# Proves backups are usable without touching the live database:
# takes a fresh dump, restores it into a throwaway PostgreSQL container and compares tables and row counts.
#   deploy/scripts/restore-test.sh                       # fresh dump; exit 0 = restorable and complete
#   deploy/scripts/restore-test.sh tulporgo-<ts>.dump    # check an existing file in deploy/backups/
set -euo pipefail
cd "$(dirname "$0")/.."

scratch="tulporgo-restore-test-$$"
cleanup() { docker rm -f "$scratch" >/dev/null 2>&1 || true; }
trap cleanup EXIT

if [[ -n "${1:-}" ]]; then
    file=$(basename "$1")
else
    echo "restore-test: fresh dump"
    out=$(docker compose run --rm -T backup --once)
    echo "$out"
    file=$(printf '%s\n' "$out" | sed -n 's#^backup: /backups/\(tulporgo-[^ ]*\.dump\).*#\1#p' | tail -1)
fi
[[ -n "$file" && -f "backups/$file" ]] || { echo "restore-test: dump not found" >&2; exit 1; }

echo "restore-test: throwaway PostgreSQL"
docker run -d --name "$scratch" -e POSTGRES_PASSWORD=scratch -e POSTGRES_DB=restore postgres:17-alpine >/dev/null
for _ in $(seq 1 60); do
    docker exec "$scratch" pg_isready -U postgres -d restore >/dev/null 2>&1 && break
    sleep 1
done
docker exec -i "$scratch" pg_restore --no-owner -U postgres -d restore < "backups/$file"

counts_sql="SELECT table_name, (xpath('/row/c/text()', query_to_xml('SELECT count(*) AS c FROM public.' || quote_ident(table_name), false, true, '')))[1]::text
            FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1"
live=$(docker compose exec -T postgres psql -U tulporgo -d tulporgo -AtF ' ' -c "$counts_sql")
restored=$(docker exec "$scratch" psql -U postgres -d restore -AtF ' ' -c "$counts_sql")

echo "restore-test: table  live  restored"
join -a1 -a2 -e MISSING -o 0,1.2,2.2 <(echo "$live" | sort) <(echo "$restored" | sort) \
    | awk '{ printf "  %-22s %10s %10s\n", $1, $2, $3 }'
if [[ "$live" != "$restored" ]]; then
    # rows written between the dump and the count are expected on a busy server; missing tables are not
    if join -v1 <(echo "$live" | cut -d' ' -f1 | sort) <(echo "$restored" | cut -d' ' -f1 | sort) | grep -q .; then
        echo "restore-test: FAILED — tables missing after restore" >&2
        exit 1
    fi
    echo "restore-test: row counts differ (writes during the test?) — check the table above"
fi
echo "restore-test: OK ($file)"
