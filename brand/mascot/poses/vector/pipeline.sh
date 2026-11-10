#!/usr/bin/env bash
# Vector pipeline v3:
#   prep (magenta bg, per-pose thresholds) -> trace (+1:1 preview) -> drop magenta -> brand palette snap (clean/)
#   -> export full (closing border; svg/ ai/ png/) -> export no-shadow (svg_ns/ png_ns/) -> checks.
set -u
cd "$(dirname "$0")"
mapfile -t ALL < <(tr -d '\r' < names.txt)
run() { local j="$1"; shift; local IFS=,; powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1 -Jsx "$j" -Names "$*"; }
export_all() {  # $1 = variant, $2 = png dir
  echo "$1" > variant.txt
  for ((i=0; i<${#ALL[@]}; i+=5)); do run export_poses.jsx "${ALL[@]:i:5}" | grep -v " OK " || true; done
  local miss=(); for n in "${ALL[@]}"; do [ -f "$2/$n.png" ] || miss+=("$n"); done
  if [ ${#miss[@]} -gt 0 ]; then echo "retry export $1: ${miss[*]}"; run export_poses.jsx "${miss[@]}"; fi
}
rm -f raw/*.svg rawpng/*.png clean/*.svg svg/*.svg ai/*.ai png/*.png svg_ns/*.svg png_ns/*.png
mkdir -p clean
echo "== prep ($(date +%T))"
python -W ignore prep_src.py "${ALL[@]}" | grep IMPLAUSIBLE || true
echo "== trace ($(date +%T))"
for ((i=0; i<${#ALL[@]}; i+=10)); do run trace_poses.jsx "${ALL[@]:i:10}" | grep -v " OK " || true; done
missing=(); for n in "${ALL[@]}"; do [ -f "raw/$n.svg" ] || missing+=("$n"); done
if [ ${#missing[@]} -gt 0 ]; then echo "retry trace: ${missing[*]}"; run trace_poses.jsx "${missing[@]}"; fi
n_raw=$(ls raw/*.svg | wc -l); echo "raw traced: $n_raw / ${#ALL[@]}"
if [ "$n_raw" -ne "${#ALL[@]}" ]; then echo "STOP: trace count mismatch"; exit 7; fi
python -W ignore compare_trace.py raw > trace_fidelity.txt; echo "trace fidelity rc=$?"
echo "== drop magenta + brand snap ($(date +%T))"
for n in "${ALL[@]}"; do
  python drop_magenta.py "raw/$n.svg" "clean/$n.svg" > /dev/null || echo "DROP-FAIL $n rc=$?"
  python brand_snap.py "clean/$n.svg" "clean/$n.svg" > /dev/null || echo "SNAP-FAIL $n rc=$?"
done
echo "== export full ($(date +%T))"; export_all full png
echo "== export no-shadow ($(date +%T))"; export_all ns png_ns
echo "full" > variant.txt
echo "== check ($(date +%T))"
python check_final.py > check.txt; echo "check full rc=$?"; grep -c " OK" check.txt; grep FAIL check.txt || true
python check_final.py --dir png_ns > check_ns.txt; echo "check ns rc=$?"; grep -c " OK" check_ns.txt; grep FAIL check_ns.txt || true
echo "== done ($(date +%T))"
