"""Prepare trace input: paint the OUTSIDE background (flood fill from all edges) pure magenta.

Magenta never occurs in the mascot, so after tracing every magenta shape is background and can be
deleted without guessing. Gaps enclosed by the white sticker border are not reached by the fill.
The fill runs on a median-filtered copy (kills speckle noise in the background); the mask is then
morphologically closed (fills specks up to ~`close` px) and applied to the original image.
Usage: python prep_src.py <names...>  (src/<n>.png -> prep/<n>.png). Prints % painted.
Exit 8 if painted area is implausible (< 5 % or > 85 %).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFilter

V = os.path.dirname(os.path.abspath(__file__))
MAG = (255, 0, 255)


def prep(im, thresh=40, close=7):
    im = im.convert("RGB")
    w, h = im.size
    work = im.filter(ImageFilter.MedianFilter(5))
    seeds = [(x, y) for x in range(0, w, 5) for y in (0, 1, h - 2, h - 1)] + \
            [(x, y) for y in range(0, h, 5) for x in (0, 1, w - 2, w - 1)]
    for s in seeds:
        if work.getpixel(s) != MAG:
            ImageDraw.floodfill(work, s, MAG, thresh=thresh)
    mask = Image.frombytes("L", (w, h), bytes(255 if p == MAG else 0 for p in work.getdata()))
    if close:
        mask = mask.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    out = im.copy()
    out.paste(Image.new("RGB", (w, h), MAG), (0, 0), mask)
    painted = sum(1 for v in mask.getdata() if v) / (w * h) * 100
    return out, painted


def overrides(path=os.path.join(V, "prep_overrides.txt")):
    """Per-pose flood threshold: lines '<name> <thresh>'. Lower = keeps light details (snow, breath, gold
    silhouettes) that are close to the light-grey background (problem A)."""
    o = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            parts = line.split("#")[0].split()
            if len(parts) == 2:
                o[parts[0]] = int(parts[1])
    return o


if __name__ == "__main__":
    os.makedirs(os.path.join(V, "prep"), exist_ok=True)
    bad = 0
    ov = overrides()
    for n in sys.argv[1:]:
        im, pct = prep(Image.open(os.path.join(V, "src", n + ".png")), thresh=ov.get(n, 40))
        im.save(os.path.join(V, "prep", n + ".png"))
        ok = 5 <= pct <= 85
        bad += not ok
        print(n, f"{pct:.1f}%", "" if ok else "IMPLAUSIBLE")
    sys.exit(8 if bad else 0)
