"""Compare vector PNG exports with the source rasters, on the CHARACTER area only.

Character area = pixels NOT painted magenta in prep/<n>.png (the border we add is outside it).
Metrics: mean abs diff (0-255) and % of pixels with diff > 60, inside the character area;
plus: corners must be transparent, and the added border must be present (alpha ring outside the character).
Usage: python compare.py [names...]
"""
import os, sys
import numpy as np
from PIL import Image

V = os.path.dirname(os.path.abspath(__file__))
names = sys.argv[1:] or [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]
for n in names:
    vp = os.path.join(V, "png", n + ".png")
    if not os.path.exists(vp):
        print(n, None, None, "MISSING"); continue
    sp = os.path.join(V, "svg", n + ".svg")
    if os.path.getmtime(vp) + 1 < os.path.getmtime(sp):
        print(n, None, None, "STALE (png older than svg)"); continue
    src = np.asarray(Image.open(os.path.join(V, "src", n + ".png")).convert("RGB")).astype(int)
    prep = np.asarray(Image.open(os.path.join(V, "prep", n + ".png")).convert("RGB"))
    char = ~((prep[:, :, 0] == 255) & (prep[:, :, 1] == 0) & (prep[:, :, 2] == 255))
    v = Image.open(vp).convert("RGBA").resize((895, 895), Image.LANCZOS)
    va = np.asarray(v).astype(int)
    rgb, alpha = va[:, :, :3], va[:, :, 3]
    d = np.abs(rgb - src).max(axis=2)
    mad = float(np.abs(rgb - src).mean(axis=2)[char].mean())
    big = float((d[char] > 60).mean() * 100)
    corners = max(alpha[2, 2], alpha[2, -3], alpha[-3, 2], alpha[-3, -3])
    ring = float(((alpha > 200) & ~char).mean() * 100)          # border area outside the character, % of canvas
    flag = "OK" if mad < 8 and big < 3 and corners == 0 and ring > 0.5 else "CHECK"
    print(n, round(mad, 2), round(big, 2), flag, f"corner={corners}", f"border={ring:.1f}%")
