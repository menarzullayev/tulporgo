"""Final sanity check of exported sticker PNGs (after normalisation the art is scaled, so no pixel compare).

Per file: no magenta left, transparent corners, white border present (opaque near-white ring at the outer edge),
art does not touch the canvas edge, art bbox fills 85-100 % of the canvas on its longer side.
Also counts separate opaque pieces ("islands", problem B): more than MAX_ISLANDS pieces bigger than 0.02 % of
the canvas fails. Exit 9 if any file fails. Usage: python check_final.py [--dir png_ns] [names...]
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

MAX_ISLANDS = 4


def islands(alpha):
    lab, k = ndimage.label(alpha > 40)
    if not k:
        return 0
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, k + 1))
    return int((sizes > alpha.size * 0.0002).sum())

V = os.path.dirname(os.path.abspath(__file__))
if __name__ == "__main__":
    args = sys.argv[1:]
    D = "png"
    if args[:1] == ["--dir"]:
        D, args = args[1], args[2:]
    names = args or [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]
    fails = 0
    for n in names:
        p = os.path.join(V, D, n + ".png")
        if not os.path.exists(p):
            print(n, "MISSING"); fails += 1; continue
        a = np.asarray(Image.open(p).convert("RGBA")).astype(int)
        h, w = a.shape[:2]; al = a[:, :, 3]
        problems = []
        if ((a[:, :, 0] > 200) & (a[:, :, 1] < 90) & (a[:, :, 2] > 200) & (al > 40)).sum() > 30: problems.append("magenta")
        if max(al[1, 1], al[1, -2], al[-2, 1], al[-2, -2]) > 0: problems.append("corner")
        if al[:3, :].max() > 0 or al[-3:, :].max() > 0 or al[:, :3].max() > 0 or al[:, -3:].max() > 0: problems.append("touches-edge")
        ys, xs = np.where(al > 40)
        fill = max(xs.max() - xs.min(), ys.max() - ys.min()) / w * 100
        if not 85 <= fill <= 100: problems.append(f"fill={fill:.0f}%")
        # border: outermost opaque pixel on 8 rays from centre should be near-white
        cy, cx = (ys.min() + ys.max()) // 2, (xs.min() + xs.max()) // 2; whites = 0
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            y, x, last = cy, cx, None
            while 0 <= y < h and 0 <= x < w:
                if al[y, x] > 200: last = (y, x)
                y += dy; x += dx
            if last and a[last[0], last[1], :3].min() > 225: whites += 1
        if whites < 6: problems.append(f"border {whites}/8")
        isl = islands(al)
        if isl > MAX_ISLANDS: problems.append(f"islands={isl}")
        fails += bool(problems)
        print(n, f"fill={fill:.0f}%", f"islands={isl}", "OK" if not problems else "FAIL " + ",".join(problems))
    sys.exit(9 if fails else 0)
