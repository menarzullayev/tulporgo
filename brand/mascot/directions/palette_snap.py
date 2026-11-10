"""Snap every fill in a traced SVG to the nearest colour of a per-design brand palette,
and drop background shapes (snapped to a 'bg' entry AND starting on the canvas edge).

Usage: python palette_snap.py <key> <in.svg> <out.svg>
Exit codes: 3 = no filled shapes, 4 = a colour is farther than MAX_DIST from every palette entry.
"""
import re, sys

Y, A, K, W = "#FFC72C", "#E0A100", "#111214", "#FFFFFF"
CANVAS = 895.0
EDGE = 1.5
MAX_DIST = 140.0

# Each entry: (hex, role). role "bg" = background candidate. BG_INTERIOR: colour for bg-snapped
# shapes that do NOT start on the edge (white gaps inside the art); None = drop those too.
PALETTES = {
    "01": ([(Y, ""), (A, ""), (K, ""), (W, "bg")], W),
    "03": ([(Y, ""), ("#FFDD55", ""), (A, ""), ("#B87400", ""), (K, ""), ("#3A3B3F", ""), ("#6E6D73", ""),
            ("#F7EBDD", ""), ("#E6D2BC", ""), ("#CFB497", ""), ("#8A6A4C", ""), ("#A54631", ""),
            ("#E4E3E4", "bg")], "#F4F3F3"),
    "06": ([(Y, ""), (A, ""), ("#FCE59A", ""), (K, ""), ("#1FA3A3", ""), ("#A0640A", ""), ("#FBF7F3", "bg")], "#FBF7F3"),
    "07": ([(Y, ""), ("#FCDD87", ""), (A, ""), ("#D47002", ""), ("#A0640A", ""), (K, ""), ("#FCEFD6", "bg")], "#FCEFD6"),
    "09": ([(Y, ""), (A, ""), ("#FDE49B", ""), (K, ""), ("#4A4B4F", ""), ("#FCF4E8", ""), ("#F4E0C9", ""),
            ("#FCA082", ""), ("#EF6B5D", ""), ("#5D2317", ""), ("#E2E0E1", ""), ("#ABAAAB", ""), ("#A0640A", ""), (W, "bg")], W),
    "10": ([(Y, ""), (A, ""), ("#FCDD83", ""), (K, ""), ("#4A4B4F", ""), ("#ACABAB", ""), ("#D4D5D8", ""),
            ("#FCF5EB", ""), ("#FCA27A", ""), ("#593625", ""), ("#353535", ""), ("#A0640A", ""), ("#EEEEEE", "bg")], W),
}

# Interior bg-snapped shapes starting below this y are dropped too (floor shadows).
DROP_BELOW = {"03": 800.0}

SHAPE = re.compile(r"<(path|polygon|rect)\b[^>]*?style=\"fill:(#[0-9A-Fa-f]{6});\"[^>]*?/>", re.S)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def dist(a, b):
    (r1, g1, b1), (r2, g2, b2) = rgb(a), rgb(b)
    rm = (r1 + r2) / 2  # "redmean" approximation of perceptual distance
    return ((2 + rm / 256) * (r1 - r2) ** 2 + 4 * (g1 - g2) ** 2 + (2 + (255 - rm) / 256) * (b1 - b2) ** 2) ** 0.5


def start_xy(tag):
    m = re.search(r'\bd="M\s*([-\d.]+)[ ,]+([-\d.]+)', tag)
    return (float(m.group(1)), float(m.group(2))) if m else None


def starts_on_edge(tag):
    m = re.search(r'\bd="M\s*([-\d.]+)[ ,]+([-\d.]+)', tag) or re.search(r'\bpoints="\s*([-\d.]+)[ ,]+([-\d.]+)', tag)
    if not m:
        m = re.search(r'\bx="([-\d.]+)"[^>]*\by="([-\d.]+)"', tag)
    if not m:
        return False
    x, y = float(m.group(1)), float(m.group(2))
    return x <= EDGE or y <= EDGE or x >= CANVAS - EDGE or y >= CANVAS - EDGE


def snap(svg, palette, bg_interior, drop_below=None):
    st = {"shapes": 0, "dropped": 0, "far": set(), "used": {}}

    def repl(m):
        st["shapes"] += 1
        col = m.group(2)
        best, role = min(palette, key=lambda e: dist(col, e[0]))
        if dist(col, best) > MAX_DIST:
            st["far"].add(col)
        if role == "bg":
            xy = start_xy(m.group(0))
            low = drop_below is not None and xy is not None and xy[1] >= drop_below
            if bg_interior is None or low or starts_on_edge(m.group(0)):
                st["dropped"] += 1
                return ""
            best = bg_interior
        st["used"][best] = st["used"].get(best, 0) + 1
        return m.group(0).replace("fill:" + col, "fill:" + best)

    return SHAPE.sub(repl, svg), st


def main(key, src, dst):
    palette, bg_interior = PALETTES[key]
    svg = open(src, encoding="iso-8859-1").read()
    out, st = snap(svg, palette, bg_interior, DROP_BELOW.get(key))
    if st["shapes"] == 0:
        print(f"{src}: ERROR no filled shapes found", file=sys.stderr)
        sys.exit(3)
    open(dst, "w", encoding="iso-8859-1").write(out)
    used = " ".join(f"{k}:{v}" for k, v in sorted(st["used"].items(), key=lambda x: -x[1]))
    print(f"{dst}: shapes={st['shapes']} dropped={st['dropped']} colours={len(st['used'])} far={sorted(st['far'])}\n   {used}")
    if st["far"]:
        sys.exit(4)


if __name__ == "__main__":
    main(*sys.argv[1:4])
