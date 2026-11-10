"""Snap traced SVG fills to brand colors and drop the white background.

Usage: python brandify.py <in.svg> <out.svg>
Near-yellow -> #FFC72C, near-black -> #111214, near-white -> removed (transparent).
Exits non-zero if no fills are found or an off-palette colour remains.
"""
import re, sys

YELLOW, BLACK = "#FFC72C", "#111214"
SHAPE = re.compile(r"<(path|polygon|rect)\b[^>]*?style=\"fill:(#[0-9A-Fa-f]{6});\"[^>]*?/>", re.S)


def classify(hexcol):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    if min(r, g, b) > 225:
        return None  # background / white gap -> drop
    if max(r, g, b) < 80:
        return BLACK
    if r > 180 and g > 120 and b < 120:
        return YELLOW
    return "?"


def brandify(svg):
    stats = {"shapes": 0, "dropped": 0, "unknown": set()}

    def repl(m):
        stats["shapes"] += 1
        new = classify(m.group(2))
        if new is None:
            stats["dropped"] += 1
            return ""
        if new == "?":
            stats["unknown"].add(m.group(2))
            return m.group(0)
        return m.group(0).replace("fill:" + m.group(2), "fill:" + new)

    out = SHAPE.sub(repl, svg)
    return out, stats


def main(src, dst):
    svg = open(src, encoding="iso-8859-1").read()
    out, st = brandify(svg)
    if st["shapes"] == 0:
        print(f"{src}: ERROR no filled shapes found", file=sys.stderr)
        sys.exit(3)
    open(dst, "w", encoding="iso-8859-1").write(out)
    print(f"{dst}: shapes={st['shapes']} dropped={st['dropped']} unknown={sorted(st['unknown'])}")
    if st["unknown"]:
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
