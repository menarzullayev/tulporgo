"""Head close-up box per pose for emoji (in the 895-px source/clean SVG coordinates).

Art = non-magenta pixels of prep/<n>.png. The box is a square starting a little above the art top (cap),
side = HEAD * art height (min 330 px), centred on the cap: median column of yellow pixels in the top 20 %.
Writes head_rects.txt lines: '<name> x y side'. Usage: python head_rects.py [names...]"""
import os, sys
import numpy as np
from PIL import Image

V = os.path.dirname(os.path.abspath(__file__))
HEAD = float(os.environ.get("HEAD", "0.60"))  # box side as a share of the art height


def head_box(prep_rgb):
    a = np.asarray(prep_rgb).astype(int)
    art = ~((a[:, :, 0] == 255) & (a[:, :, 1] == 0) & (a[:, :, 2] == 255))
    ys, xs = np.where(art)
    top, bot = ys.min(), ys.max()
    side = max(330, int(HEAD * (bot - top)))
    # centre: median column of the cap (yellow pixels in the top 20 % of the art)
    a2 = a[top:top + int(0.20 * (bot - top))]
    yel = (a2[:, :, 0] > 200) & (a2[:, :, 1] > 150) & (a2[:, :, 2] < 110)
    cx = int(np.median(np.where(yel)[1])) if yel.sum() > 200 else int(np.median(xs))
    h, w = art.shape
    x = int(min(max(cx - side // 2, 0), w - side))
    y = int(max(top - 6, 0))
    return x, y, side


def adjustments(path=os.path.join(V, "head_adjust.txt")):
    """Manual framing fixes: '<name> dx dy dside' (source px), from visual review."""
    o = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            p = line.split("#")[0].split()
            if len(p) == 4:
                o[p[0]] = tuple(int(v) for v in p[1:])
    return o


def adjust(box, adj, w=895, h=895):
    x, y, s = box
    dx, dy, ds = adj
    s = min(s + ds, w, h)
    x = min(max(x + dx - ds // 2, 0), w - s)
    y = min(max(y + dy, 0), h - s)
    return x, y, s


if __name__ == "__main__":
    ADJ = adjustments()
    names = sys.argv[1:] or [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]
    with open(os.environ.get("HEAD_OUT", os.path.join(V, "head_rects.txt")), "w") as f:
        for n in names:
            x, y, s = head_box(Image.open(os.path.join(V, "prep", n + ".png")).convert("RGB"))
            if n in ADJ:
                x, y, s = adjust((x, y, s), ADJ[n])
            f.write(f"{n} {x} {y} {s}\n")
    print(open(os.environ.get("HEAD_OUT", os.path.join(V, "head_rects.txt"))).read())
