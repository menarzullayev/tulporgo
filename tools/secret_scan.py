"""Fail if a secret or personal identifier is about to be published (decisions 46, 54).

Scans the files git would commit (`git ls-files -co --exclude-standard`), or the paths given. Base64 inside
`data:` URIs (embedded images) is ignored. Exit 1 with the file and the kind of finding — the value is never printed.
Usage: python tools/secret_scan.py [paths...]
"""
import re, subprocess, sys
from pathlib import Path

PATTERNS = {
    "telegram bot token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "telegram api hash": re.compile(r"(?i)api_?hash\W{0,4}[0-9a-f]{32}"),
    "telethon/gramjs session string": re.compile(r"\b1[A-Za-z0-9+/_=-]{340,}\b"),
    "uzbek phone number": re.compile(r"\+?998[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "access hash": re.compile(r"(?i)\"access_hash\"\s*:\s*-?\d{6,}"),
}
DATA_URI = re.compile(r"data:[\w.+-]+/[\w.+-]+;base64,[A-Za-z0-9+/=]+")
BINARY = (".png", ".jpg", ".jpeg", ".webp", ".webm", ".tgs", ".gif", ".pdf", ".zip", ".ico", ".woff", ".woff2", ".ttf")


def findings(text):
    spans = [m.span() for m in DATA_URI.finditer(text)]
    out = []
    for kind, rx in PATTERNS.items():
        for m in rx.finditer(text):
            if not any(a <= m.start() and m.end() <= b for a, b in spans):
                out.append((kind, text.count("\n", 0, m.start()) + 1))
    return out


def files(args):
    if args:
        return [Path(a) for a in args]
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True, check=True).stdout
    return [Path(l) for l in out.splitlines() if l]


def main(args):
    bad = 0
    for p in files(args):
        if p.suffix.lower() in BINARY or not p.is_file():
            continue
        for kind, line in findings(p.read_text(encoding="utf-8", errors="ignore")):
            print(f"{p}:{line}: {kind}")
            bad += 1
    print(f"secret scan: {bad} finding(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
