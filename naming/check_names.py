#!/usr/bin/env python3
"""
Brand name availability checker -- parallel first pass.

For each candidate handle, reports a verdict per surface:
  - Domains  : .uz / .io / .ai via port-43 whois, .com via RDAP (Verisign)
  - Telegram : t.me/<handle>   (title says View vs Contact)
  - Facebook : facebook.com/<handle>  (redirect target discriminates)
  - Instagram: always UNKNOWN -- see SKILL.md section 4

Verdicts are deliberately three-valued: free / taken / error. An error is
NEVER reported as free; a throttled lookup must not look like an available
name.

Usage:
    python check_names.py candidates.txt
    python check_names.py candidates.txt --json out.json --workers 6
    python check_names.py candidates.txt --zones uz,com --no-social
"""

import argparse
import json
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

TIMEOUT = 12
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RDAP = {
    "com": "https://rdap.verisign.com/com/v1/domain/{d}",
}

# Port-43 whois beats RDAP here: the Identity Digital RDAP endpoint for
# .io/.ai hard-throttles datacenter IPs with 429, while the registry whois
# servers stay responsive.
WHOIS_SERVERS = {
    "uz": "whois.cctld.uz",
    "io": "whois.nic.io",
    "ai": "whois.nic.ai",
}

FREE = "free"
TAKEN = "taken"
ERROR = "error"
UNKNOWN = "unknown"

MARKS = {"free": "FREE", "taken": "taken", "error": "?", "unknown": "manual"}


# ---------------------------------------------------------------- domains
def whois_lookup(domain: str, server: str) -> str:
    """Raw port-43 whois query. Returns response text, or '' on failure."""
    try:
        with socket.create_connection((server, 43), timeout=TIMEOUT) as s:
            s.sendall(f"{domain}\r\n".encode())
            chunks = []
            while True:
                buf = s.recv(4096)
                if not buf:
                    break
                chunks.append(buf)
        return b"".join(chunks).decode("utf-8", "ignore")
    except Exception:
        return ""


# Free-domain markers, per registry wording.
_FREE_MARKERS = (
    "not found in database",       # .uz
    "no match",                    # generic
    "domain not found",            # .io / .ai
    "no entries found",
    "not registered",
)


def check_domain(handle: str, zone: str) -> str:
    """FREE / TAKEN / ERROR for <handle>.<zone>."""
    domain = f"{handle}.{zone}"

    if zone == "com":
        try:
            r = requests.get(RDAP["com"].format(d=domain), headers=HEADERS,
                             timeout=TIMEOUT, allow_redirects=True)
            if r.status_code == 404:
                return FREE
            if r.status_code == 200:
                return TAKEN
            return ERROR          # includes 429 -- never call this free
        except Exception:
            return ERROR

    server = WHOIS_SERVERS.get(zone)
    if not server:
        return ERROR
    text = whois_lookup(domain, server)
    if not text:
        return ERROR
    low = text.lower()
    if any(m in low for m in _FREE_MARKERS):
        return FREE
    if "domain name:" in low:
        return TAKEN
    return ERROR


# ----------------------------------------------------------------- socials
def check_telegram(handle: str) -> str:
    """
    The t.me page <title> carries the status verbatim:
        TAKEN -> "<title>Telegram: View @handle</title>"
        FREE  -> "<title>Telegram: Contact @handle</title>"
    Measured against: telegram (View), durov (View), nasa (Contact),
    aaaabbbbccccdddd (Contact).
    """
    try:
        r = requests.get(f"https://t.me/{handle}", headers=HEADERS, timeout=TIMEOUT)
        m = re.search(r"<title>\s*Telegram:\s*(View|Contact)\s*@", r.text, re.I)
        if m:
            return TAKEN if m.group(1).lower() == "view" else FREE
        return ERROR
    except Exception:
        return ERROR


def check_facebook(handle: str) -> str:
    """
    The redirect target discriminates:
        TAKEN -> 302 to https://www.facebook.com/<Handle>/   (real page)
        FREE  -> 302 to https://www.facebook.com/login/?next=...
    A direct 200 on the canonical /<handle>/ is also TAKEN.
    """
    # 2026-11-09: Facebook now 302s every handle (google, NASA, random) to /login/ from this network,
    # so the redirect no longer discriminates. Report manual instead of a false FREE.
    return 'manual'
    try:
        r = requests.get(
            f"https://www.facebook.com/{handle}", headers=HEADERS,
            timeout=TIMEOUT, allow_redirects=False,
        )
        if r.status_code == 200:
            return TAKEN
        if r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get("Location", "")
            if "/login/" in loc or "login.php" in loc or "checkpoint" in loc:
                return FREE
            return TAKEN
        if r.status_code == 404:
            return FREE
        return ERROR
    except Exception:
        return ERROR


def check_instagram(handle: str) -> str:
    """
    Instagram answers every request -- existing and non-existing alike -- with
    200 + "<title>Instagram</title>" and a login wall. Existence is therefore
    NOT observable over plain HTTP from a datacenter IP. Returned as UNKNOWN
    on purpose, never guessed.
    """
    return UNKNOWN


# ------------------------------------------------------------------ driver
def check_row(handle: str, zones, do_social: bool) -> dict:
    row = {"handle": handle}
    for z in zones:
        row[f".{z}"] = check_domain(handle, z)
    if do_social:
        row["telegram"] = check_telegram(handle)
        row["instagram"] = check_instagram(handle)
        row["facebook"] = check_facebook(handle)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="file with one handle per line (# = comment)")
    ap.add_argument("--json", help="write JSON results here")
    ap.add_argument("--zones", default="uz,com,io,ai")
    ap.add_argument("--no-social", action="store_true")
    ap.add_argument("--workers", type=int, default=8,
                    help="keep <= 6; higher triggers whois/RDAP throttling")
    args = ap.parse_args()

    zones = [z.strip().lstrip(".") for z in args.zones.split(",") if z.strip()]

    handles = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            h = re.sub(r"[^a-z0-9-]", "", line.lower())
            if h:
                handles.append(h)
    handles = sorted(set(handles))

    print(f"Checking {len(handles)} names x {len(zones)} zones "
          f"{'+ 3 social' if not args.no_social else ''}\n", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(check_row, h, zones, not args.no_social): h
                for h in handles}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({"handle": futs[fut], "error": str(e)})
            print(f"  [{i}/{len(handles)}] {futs[fut]}", flush=True)

    results.sort(key=lambda r: r["handle"])
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nJSON written: {args.json}")

    cols = list(zones) + ([] if args.no_social else
                          ["telegram", "instagram", "facebook"])
    keys = [f".{z}" for z in zones] + ([] if args.no_social else
                                       ["telegram", "instagram", "facebook"])

    print("\n" + "=" * 78)
    print(f"{'HANDLE':<20}" + "".join(f"{c:<12}" for c in cols))
    print("=" * 78)
    for r in results:
        line = f"{r['handle']:<20}"
        for k in keys:
            line += f"{MARKS.get(r.get(k), '?'):<12}"
        print(line)


if __name__ == "__main__":
    main()
