"""Remove the flat background from an Illustrator-traced pose SVG.

A shape is background when (a) its fill is close to the background colour sampled from the source PNG
corner AND (b) it starts on the canvas edge. Interior shapes of the same colour (gaps between legs) are kept,
because they are inside the white sticker border and do not touch the edge.

Usage: python clean_bg.py <src.png> <raw.svg> <out.svg>
Exit 3: no filled shapes; exit 5: nothing removed (background not found); exit 6: canvas corner still opaque.
"""
import re, sys
from PIL import Image, ImageDraw

CANVAS, EDGE, TOL = 895.0, 2.0, 30.0
SHAPE = re.compile(r"<(path|polygon|rect)\b[^>]*?style=\"fill:(#[0-9A-Fa-f]{6});\"[^>]*?/>", re.S)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def dist(a, b):
    (r1, g1, b1), (r2, g2, b2) = a, b
    rm = (r1 + r2) / 2
    return ((2 + rm / 256) * (r1 - r2) ** 2 + 4 * (g1 - g2) ** 2 + (2 + (255 - rm) / 256) * (b1 - b2) ** 2) ** 0.5


def start_xy(tag):
    m = (re.search(r'\bd="M\s*([-\d.]+)[ ,]+([-\d.]+)', tag) or re.search(r'\bpoints="\s*([-\d.]+)[ ,]+([-\d.]+)', tag)
         or re.search(r'\bx="([-\d.]+)"[^>]*\by="([-\d.]+)"', tag))
    return (float(m.group(1)), float(m.group(2))) if m else None


def on_edge(xy):
    return xy is not None and (xy[0] <= EDGE or xy[1] <= EDGE or xy[0] >= CANVAS - EDGE or xy[1] >= CANVAS - EDGE)


def bg_mask(png, thresh=24):
    """Outside-background mask: flood fill from every edge pixel of the source raster.
    Pixels enclosed by the white sticker border (gaps between legs) are NOT reached."""
    im = Image.open(png).convert("RGB")
    if im.size != (895, 895):
        im = im.resize((895, 895))
    w, h = im.size
    marker = (255, 0, 255)
    work = im.copy()
    for x in range(0, w, 7):
        for y in (0, h - 1):
            if work.getpixel((x, y)) != marker:
                ImageDraw.floodfill(work, (x, y), marker, thresh=thresh)
    for y in range(0, h, 7):
        for x in (0, w - 1):
            if work.getpixel((x, y)) != marker:
                ImageDraw.floodfill(work, (x, y), marker, thresh=thresh)
    return work




def clean(svg, bg, mask=None):
    """bg: one RGB tuple or a list of them. mask: flood-filled source image (outside bg = magenta)."""
    bgs = bg if isinstance(bg, list) else [bg]
    st = {"shapes": 0, "removed": 0}

    def outside(xy):
        if mask is None or xy is None:
            return False
        x, y = min(max(int(xy[0]), 0), 894), min(max(int(xy[1]), 0), 894)
        return mask.getpixel((x, y)) == (255, 0, 255)

    def repl(m):
        st["shapes"] += 1
        xy = start_xy(m.group(0))
        if min(dist(rgb(m.group(2)), b) for b in bgs) <= TOL and (on_edge(xy) or outside(xy)):
            st["removed"] += 1
            return ""
        return m.group(0)

    return SHAPE.sub(repl, svg), st


def bg_samples(png):
    """Background colours sampled along all four edges (handles vertical/diagonal gradients)."""
    im = Image.open(png).convert("RGB")
    w, h = im.size
    pts = [(4, 4), (w - 5, 4), (4, h - 5), (w - 5, h - 5), (w // 2, 4), (4, h // 2), (w - 5, h // 2), (w // 2, h - 5)]
    return [im.getpixel(p) for p in pts]


def bg_of(png):
    px = bg_samples(png)
    return tuple(sum(c[i] for c in px) // len(px) for i in range(3))


def main(png, raw, out):
    svg = open(raw, encoding="iso-8859-1").read()
    res, st = clean(svg, bg_samples(png), bg_mask(png))
    if st["shapes"] == 0:
        sys.exit(3)
    if st["removed"] == 0:
        print(out, "NO BACKGROUND REMOVED", file=sys.stderr)
        sys.exit(5)
    open(out, "w", encoding="iso-8859-1").write(res)
    print(f"{out}: shapes={st['shapes']} removed={st['removed']}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
