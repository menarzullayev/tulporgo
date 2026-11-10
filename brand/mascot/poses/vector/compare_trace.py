"""Measure trace fidelity: <dir>png/<n>.png (1:1 raster of the traced SVG) vs src/<n>.png on the
character area (not magenta in prep/). Prints mean abs diff, % pixels off by > 60, path count, svg KB.
Usage: python compare_trace.py <dir> [names...]   Exit 10 if any file is missing."""
import os, re, sys
import numpy as np
from PIL import Image

V = os.path.dirname(os.path.abspath(__file__))
d = sys.argv[1]
names = sys.argv[2:] or [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]
miss = 0
for n in names:
    rp, sp = os.path.join(V, d + "png", n + ".png"), os.path.join(V, d, n + ".svg")
    if not (os.path.exists(rp) and os.path.exists(sp)):
        print(n, "MISSING"); miss += 1; continue
    src = np.asarray(Image.open(os.path.join(V, "src", n + ".png")).convert("RGB")).astype(int)
    prep = np.asarray(Image.open(os.path.join(V, "prep", n + ".png")).convert("RGB"))
    char = ~((prep[:, :, 0] == 255) & (prep[:, :, 1] == 0) & (prep[:, :, 2] == 255))
    t = np.asarray(Image.open(rp).convert("RGB").resize(src.shape[1::-1])).astype(int)
    diff = np.abs(t - src)
    mad = diff.mean(axis=2)[char].mean(); big = (diff.max(axis=2)[char] > 60).mean() * 100
    svg = open(sp, encoding="iso-8859-1").read()
    print(n, f"mad={mad:.2f}", f"big={big:.2f}%", "shapes=%d" % len(re.findall(r"<(?:path|polygon|rect)\b", svg)),
          f"kb={os.path.getsize(sp) // 1024}")
sys.exit(10 if miss else 0)
