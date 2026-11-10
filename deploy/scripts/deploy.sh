#!/usr/bin/env bash
# Deploy a git ref on the VPS (run from the repository checkout, as the deploy user).
#   deploy/scripts/deploy.sh                # origin/main
#   deploy/scripts/deploy.sh <commit|tag>   # also how to roll back
set -euo pipefail
cd "$(dirname "$0")/.."                    # deploy/
repo=$(git rev-parse --show-toplevel)

[[ -f .env ]] || { echo "deploy: deploy/.env missing (copy .env.example)" >&2; exit 2; }
ref="${1:-origin/main}"

git -C "$repo" fetch --quiet origin
prev=$(git -C "$repo" rev-parse --short HEAD)
git -C "$repo" checkout --quiet --detach "$ref"
new=$(git -C "$repo" rev-parse --short HEAD)
export TULPORGO_IMAGE_TAG="$new"
echo "deploy: $prev -> $new"

fail() {
    echo "deploy: FAILED at: $1" >&2
    echo "deploy: roll back with: deploy/scripts/deploy.sh $prev" >&2
    exit 1
}

docker compose build || fail "build"
docker compose up -d postgres redis || fail "database start"
docker compose run --rm -T backup --once || fail "pre-deploy backup"
docker compose up -d --remove-orphans || fail "start"

echo "deploy: waiting for the API health check"
for _ in $(seq 1 40); do
    state=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q api)" 2>/dev/null || echo none)
    [[ "$state" == "healthy" ]] && break
    sleep 3
done
[[ "$state" == "healthy" ]] || fail "api health ($state)"

docker compose run --rm --no-deps -T migrate python -m tulporgo_core.manage check || fail "database revision"

domain=$(sed -n 's/^TULPORGO_DOMAIN=//p' .env | tail -1)
if [[ -n "$domain" && "$domain" != "localhost" ]]; then
    curl -fsS --max-time 10 "https://$domain/api/health" >/dev/null || fail "public https://$domain/api/health"
fi

echo "$new $(date -u +%FT%TZ)" >> deployed.log
echo "deploy: OK — commit $new is live"
