#!/usr/bin/env python3
"""
Sequential .io/.ai whois re-check -- throttle-safe.

Why this exists: the parallel first pass (check_names.py) will report `error`
for many .io/.ai cells because Identity Digital throttles bulk queries. This
second pass runs strictly sequentially with a 2.5 s gap so the registry stays
responsive, and separates "genuinely taken" from "I got rate-limited".

Reads  : input.txt  (one handle per line)
Writes : io_ai_results.json
Prints : the confirmed-free set, the io-only free set, and any remaining errors

Adjust INPUT/OUTPUT paths for the job at hand.
"""

import json
import socket
import time

TIMEOUT = 15
PACING = 2.5          # seconds between whois queries -- do not lower

INPUT = "family_survivors.txt"
OUTPUT = "io_ai_results.json"

FREE_MARKERS = ("domain not found", "no match", "no entries found",
                "not found in database")

SERVERS = (("io", "whois.nic.io"), ("ai", "whois.nic.ai"))


def whois(domain: str, server: str) -> str:
    try:
        with socket.create_connection((server, 43), timeout=TIMEOUT) as s:
            s.sendall(f"{domain}\r\n".encode())
            buf = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        return buf.decode("utf-8", "ignore")
    except Exception:
        return ""


def verdict(text: str) -> str:
    if not text:
        return "error"
    low = text.lower()
    if any(m in low for m in FREE_MARKERS):
        return "free"
    if "domain name:" in low:
        return "taken"
    return "error"


def main():
    with open(INPUT, encoding="utf-8") as f:
        handles = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    out = {}
    for i, h in enumerate(handles, 1):
        row = {"handle": h}
        for zone, server in SERVERS:
            row[zone] = verdict(whois(f"{h}.{zone}", server))
            time.sleep(PACING)
        out[h] = row
        mark = {"free": "FREE", "taken": "x", "error": "?"}
        print(f"  {i:>3}/{len(handles)}  {h:<22} "
              f"io={mark[row['io']]} ai={mark[row['ai']]}", flush=True)
        time.sleep(1.0)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("\n=== io + ai BOTH FREE ===")
    for h, r in out.items():
        if r["io"] == "free" and r["ai"] == "free":
            print("   ***", h)

    print("\n=== io free, ai taken ===")
    for h, r in out.items():
        if r["io"] == "free" and r["ai"] != "free":
            print(f"   {h:<22} ai={r['ai']}")

    errs = [h for h, r in out.items() if "error" in (r["io"], r["ai"])]
    print("\n=== still needs a re-check ===")
    print("  ", ", ".join(errs) if errs else "(none)")


if __name__ == "__main__":
    main()
