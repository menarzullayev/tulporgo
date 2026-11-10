"""Fill small inner holes of the white sticker border in an exported SVG (in place).

The border is one <path> inside <g id="sticker-border">; holes are extra subpaths. A subpath is dropped when
its bbox lies inside the outline's bbox and its area is < MAX_FRAC of the outline. Large openings (between legs)
stay. Done here because removing hole paths inside Illustrator did not reach the SVG export.
Usage: python fill_holes.py <file.svg>...   prints removed holes per file."""
import re, sys
from svgpathtools import parse_path

MAX_FRAC = 0.02
GROUP = re.compile(r'<g id="sticker-border">(.*?)</g>', re.S)
PATH_D = re.compile(r'(<path\b[^>]*?\bd=")([^"]+)(")', re.S)


def parea(p, n=400):
    """|area| of a closed path by shoelace over sampled points (svgpathtools.area() is unreliable here)."""
    if p is None or len(p) == 0:
        return 0.0
    pts = [p.point(i / n) for i in range(n)]
    return abs(sum((a.real * b.imag - b.real * a.imag) for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def split_subpaths(d):
    parts = re.split(r"(?=[Mm])", d.strip())
    return [p for p in parts if p.strip()]


def fill(d):
    subs = split_subpaths(d)
    if len(subs) < 2:
        return d, 0
    if any(s[0] == "m" for s in subs[1:]):
        # relative moveto depends on the previous subpath's end point: convert via svgpathtools
        path = parse_path(d)
        subs = [p.d() for p in path.continuous_subpaths()]
    info = []
    for s in subs:
        p = parse_path(s)
        x0, x1, y0, y1 = p.bbox()
        try:
            a = parea(p)
        except RuntimeError:                           # zero-length subpath (a single point): no area
            a = 0.0
        info.append((s, (x0, x1, y0, y1), a))
    outer = max(info, key=lambda t: t[2])
    ox0, ox1, oy0, oy1 = outer[1]
    keep, removed = [], 0
    for s, (x0, x1, y0, y1), a in info:
        inside = s is not outer[0] and x0 > ox0 and x1 < ox1 and y0 > oy0 and y1 < oy1
        if inside and a < MAX_FRAC * outer[2]:
            removed += 1
        else:
            keep.append(s)
    return " ".join(keep), removed


def process(svg):
    """All paths in the border group: the biggest is the outline; holes (in it or as separate paths,
    incl. degenerate zero-size paths) inside its bbox and < MAX_FRAC of its area are removed."""
    g = GROUP.search(svg)
    if not g:
        return svg, -1
    body = g.group(1)
    paths = list(PATH_D.finditer(body))
    if not paths:
        return svg, -1
    areas = []
    for m in paths:
        try:
            p = parse_path(m.group(2))
            areas.append((p if len(p) else None, parea(p)))
        except Exception:
            areas.append((None, 0.0))
    bi = max(range(len(paths)), key=lambda i: areas[i][1])
    ox0, ox1, oy0, oy1 = areas[bi][0].bbox()
    big = areas[bi][1]
    new, removed, pos = "", 0, 0
    for i, m in enumerate(paths):
        new += body[pos:m.start()]
        pos = m.end()
        if i == bi:
            nd, k = fill(m.group(2)); removed += k
            new += m.group(1) + nd + m.group(3)
            continue
        p = areas[i][0]
        if p is None:                                   # empty/degenerate path: draws nothing anyway
            new += m.group(0); continue
        x0, x1, y0, y1 = p.bbox()
        if x0 >= ox0 and x1 <= ox1 and y0 >= oy0 and y1 <= oy1 and areas[i][1] < MAX_FRAC * big:
            removed += 1
            new += m.group(1) + "M0,0" + m.group(3)   # emptied (keeps the element, draws nothing)
        else:
            new += m.group(0)
    new += body[pos:]
    return svg[:g.start(1)] + new + svg[g.end(1):], removed


if __name__ == "__main__":
    for f in sys.argv[1:]:
        s = open(f, encoding="iso-8859-1").read()
        out, k = process(s)
        if k > 0:
            open(f, "w", encoding="iso-8859-1").write(out)
        print(f, "holes-filled=%d" % k)
