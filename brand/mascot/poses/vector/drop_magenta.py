"""Delete magenta (outside background) shapes from a traced SVG. Exit 5 if none found, 6 if magenta remains visible.
Usage: python drop_magenta.py <raw.svg> <out.svg>"""
import re, sys
SHAPE = re.compile(r"<(path|polygon|rect)\b[^>]*?style=\"fill:(#[0-9A-Fa-f]{6});\"[^>]*?/>", re.S)

def is_mag(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return r > 180 and b > 180 and g < 110

def drop(svg):
    st = {"shapes": 0, "removed": 0}
    def repl(m):
        st["shapes"] += 1
        if is_mag(m.group(2)):
            st["removed"] += 1; return ""
        return m.group(0)
    return SHAPE.sub(repl, svg), st

if __name__ == "__main__":
    svg = open(sys.argv[1], encoding="iso-8859-1").read()
    out, st = drop(svg)
    if st["removed"] == 0:
        print(sys.argv[2], "NO MAGENTA FOUND", file=sys.stderr); sys.exit(5)
    if re.search(r"fill:#(F[0-9A-F]|E[0-9A-F]|D[0-9A-F]|C[0-9A-F]|B[5-9A-F])[0-6][0-9A-F](F[0-9A-F]|E[0-9A-F]|D[0-9A-F]|C[0-9A-F])", out, re.I):
        print(sys.argv[2], "MAGENTA-LIKE FILL REMAINS", file=sys.stderr); sys.exit(6)
    open(sys.argv[2], "w", encoding="iso-8859-1").write(out)
    print(f"{sys.argv[2]}: shapes={st['shapes']} removed={st['removed']}")
