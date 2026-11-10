#!/usr/bin/env bash
# Re-run only the export stage (full + no-shadow) and the checks, from existing clean/ SVGs.
set -u
cd "$(dirname "$0")"
mapfile -t ALL < <(tr -d '\r' < names.txt)
run() { local j="$1"; shift; local IFS=,; powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1 -Jsx "$j" -Names "$*"; }
export_all() {
  echo "$1" > variant.txt
  rm -f "$2"/*.png
  for ((i=0; i<${#ALL[@]}; i+=5)); do run export_poses.jsx "${ALL[@]:i:5}" | grep -v " OK " || true; done
  local miss=(); for n in "${ALL[@]}"; do [ -f "$2/$n.png" ] || miss+=("$n"); done
  if [ ${#miss[@]} -gt 0 ]; then echo "retry export $1: ${miss[*]}"; run export_poses.jsx "${miss[@]}"; fi
}
echo "== export full ($(date +%T))"; export_all full png
echo "== export no-shadow ($(date +%T))"; export_all ns png_ns
echo "full" > variant.txt
python check_final.py > check.txt; echo "check full rc=$?"; grep -c " OK" check.txt; grep FAIL check.txt || true
python check_final.py --dir png_ns > check_ns.txt; echo "check ns rc=$?"; grep -c " OK" check_ns.txt; grep FAIL check_ns.txt || true
echo "== done ($(date +%T))"
