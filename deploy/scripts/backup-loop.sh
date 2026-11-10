#!/bin/sh
# Runs inside the `backup` container (postgres:17-alpine, BusyBox).
# Decision 58: one automatic pg_dump a MONTH (day BACKUP_DAY_OF_MONTH at BACKUP_AT_UTC), only the newest
# BACKUP_KEEP_COUNT dumps stay on the server (default 1). Other backups are taken by hand (`--once`).
# The `offsite` service encrypts each new dump and copies it to Cloudflare R2.
#   sh /backup-loop.sh          # loop forever (container default)
#   sh /backup-loop.sh --once   # one dump now, then exit (manual backup, and deploy.sh before migrating)
set -eu

keep="${BACKUP_KEEP_COUNT:-1}"
day="${BACKUP_DAY_OF_MONTH:-1}"
at="${BACKUP_AT_UTC:-22:00}"

prune() {   # keep the newest $keep dumps
    ls -1t /backups/tulporgo-*.dump 2>/dev/null | tail -n +"$((keep + 1))" | while read -r old; do
        rm -f "$old"
        echo "backup: removed old $old"
    done
}

dump() {
    f="/backups/tulporgo-$(date -u +%Y%m%dT%H%M%SZ).dump"
    pg_dump --format=custom --no-owner --file="$f.part"
    mv "$f.part" "$f"
    echo "backup: $f ($(wc -c < "$f") bytes)"
    prune
}

seconds_until() {   # seconds until the next $1 (HH:MM, UTC)
    now=$(date -u +%s)
    target=$(date -u -d "$(date -u +%Y-%m-%d) $1" +%s)
    if [ "$target" -le "$now" ]; then target=$((target + 86400)); fi
    echo $((target - now))
}

today() { date -u +%d | sed 's/^0//'; }

if [ "${1:-}" = "--once" ]; then
    dump
    exit 0
fi

# no dump in the last month (fresh server, long downtime) → take one now
if [ -z "$(find /backups -name 'tulporgo-*.dump' -mtime -31 2>/dev/null)" ]; then
    dump || echo "backup: FAILED" >&2
fi

while true; do
    sleep "$(seconds_until "$at")"
    if [ "$(today)" = "$day" ]; then
        dump || echo "backup: FAILED" >&2
    fi
done
