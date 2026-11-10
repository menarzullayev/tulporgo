#!/bin/sh
# Runs inside the `backup` container (postgres:17-alpine, BusyBox).
# Daily pg_dump (custom format) into /backups at BACKUP_AT_UTC, keeps BACKUP_KEEP_DAYS days.
#   sh /backup-loop.sh          # loop forever (container default)
#   sh /backup-loop.sh --once   # one dump now, then exit (used by deploy.sh before migrating)
set -eu

keep="${BACKUP_KEEP_DAYS:-14}"
at="${BACKUP_AT_UTC:-22:00}"

dump() {
    f="/backups/tulporgo-$(date -u +%Y%m%dT%H%M%SZ).dump"
    pg_dump --format=custom --no-owner --file="$f.part"
    mv "$f.part" "$f"
    echo "backup: $f ($(wc -c < "$f") bytes)"
    find /backups -name 'tulporgo-*.dump' -mtime +"$keep" -delete
}

seconds_until() {   # seconds until the next $1 (HH:MM, UTC)
    now=$(date -u +%s)
    target=$(date -u -d "$(date -u +%Y-%m-%d) $1" +%s)
    if [ "$target" -le "$now" ]; then target=$((target + 86400)); fi
    echo $((target - now))
}

if [ "${1:-}" = "--once" ]; then
    dump
    exit 0
fi

# no dump in the last 24 h (fresh server, long downtime) → take one now
if [ -z "$(find /backups -name 'tulporgo-*.dump' -mtime -1 2>/dev/null)" ]; then
    dump || echo "backup: FAILED" >&2
fi

while true; do
    sleep "$(seconds_until "$at")"
    dump || echo "backup: FAILED" >&2
done
