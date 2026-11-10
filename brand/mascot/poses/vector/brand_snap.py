"""Snap near-brand fills of a cleaned SVG to the exact TulporGo mascot palette (model sheet 09).

Only colours within MAX_DIST (redmean distance) of a brand colour are replaced, so props keep their own
colours (tree green, gift red, confetti purple) while the character's yellow/black/cream become identical
across all poses. Usage: python brand_snap.py <in.svg> <out.svg> [max_dist]
Prints shapes / snapped. Exit 11 if no brand colour was snapped (wrong input or palette)."""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "directions"))
from palette_snap import PALETTES, dist  # noqa: E402

BRAND = [h for h, role in PALETTES["09"][0] if role != "bg"]  # white bg entry excluded
MAX_DIST = 26.0
FILL = re.compile(r"fill:(#[0-9A-Fa-f]{6})")


def snap(svg, max_dist=MAX_DIST):
    st = {"shapes": 0, "snapped": 0}
    def repl(m):
        st["shapes"] += 1
        h = m.group(1).upper()
        best = min(BRAND, key=lambda b: dist(h, b))
        if dist(h, best) <= max_dist:
            if h != best:
                st["snapped"] += 1
            return "fill:" + best
        return m.group(0)
    return FILL.sub(repl, svg), st


if __name__ == "__main__":
    svg = open(sys.argv[1], encoding="iso-8859-1").read()
    out, st = snap(svg, float(sys.argv[3]) if len(sys.argv) > 3 else MAX_DIST)
    open(sys.argv[2], "w", encoding="iso-8859-1").write(out)
    print(f"{sys.argv[2]}: shapes={st['shapes']} snapped={st['snapped']}")
    sys.exit(11 if st["snapped"] == 0 else 0)
