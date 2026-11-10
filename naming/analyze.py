#!/usr/bin/env python3
"""
Stage-1 filter and stage-2 grouping.

Stage 1 (filter_survivors): keep only names that are free on .uz + .com +
Telegram + Facebook. Writes the survivors list that feeds the throttled
.io/.ai re-check.

Stage 2 (group_and_rank): merge everything into the final shortlist, grouped by
naming strategy -- which is how a user actually decides, not alphabetically.
Rows with any `error`/`unknown` cell are kept out of the confirmed set.

Adapt the GROUPS table and the input paths per job.
"""

import json

# ------------------------------------------------------------------ config
RESULTS = "results.json"          # from check_names.py
IO_AI = "io_ai_results.json"      # from recheck_io_ai.py
SURVIVORS = "survivors.txt"
CONFIRMED = "confirmed.txt"

ZONES = [".uz", ".com", ".io", ".ai"]
OK = "free"


def filter_survivors():
    rows = json.load(open(RESULTS, encoding="utf-8"))
    keep = [r["handle"] for r in rows
            if r.get(".uz") == OK and r.get(".com") == OK
            and r.get("telegram") == OK and r.get("facebook") == OK]
    keep.sort()
    open(SURVIVORS, "w", encoding="utf-8").write("\n".join(keep) + "\n")

    print(f".uz + .com + Telegram + Facebook all free: {len(keep)}\n")
    for h in keep:
        print("  ", h)

    print("\n=== domains free but a social is taken ===")
    for r in rows:
        if r.get(".uz") == OK and r.get(".com") == OK:
            bad = [p for p in ("telegram", "facebook")
                   if r.get(p) == "taken"]
            if bad:
                print(f"   {r['handle']:<22} {', '.join(bad)} taken")


def group_and_rank():
    io_ai = json.load(open(IO_AI, encoding="utf-8"))
    confirmed = [h for h, r in io_ai.items()
                 if r["io"] == OK and r["ai"] == OK]
    confirmed.sort()
    open(CONFIRMED, "w", encoding="utf-8").write("\n".join(confirmed) + "\n")

    print(f"\nFully confirmed ({len(confirmed)}): "
          f"all four zones + Telegram + Facebook free")
    for h in confirmed:
        print("   ***", h)

    print("\nReorder these into naming-strategy groups for the report "
          "(see SKILL.md section 5): family root, root+suffix, derived, "
          "meaning-based, initials.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "group":
        group_and_rank()
    else:
        filter_survivors()
