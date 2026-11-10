"""TulporGo interface icons as animated vector TGS (Telegram Lottie), decision 39.

Same file format Bodymovin-TG exports, built directly so every icon is exact and reproducible, and only uses
features allowed by core.telegram.org/stickers (shape layers, groups, paths, rect, ellipse, fill, stroke, trim
paths; no text, masks, effects, images, solids, 3D, merge paths, star shapes, repeaters, expressions).
512x512, 60 fps, 3 s loop: a short motion (~0.5-0.8 s), then the icon rests until the loop restarts.
Digits are Arial Black outlines converted to paths (text layers are forbidden).
Usage: python icons_tgs.py   -> tgs/<name>.tgs
"""
import gzip, json, os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from lottie.parsers.svg.importer import PathDParser

HERE = os.path.dirname(os.path.abspath(__file__))
FR, OP, K = 60, 180, 512 / 24 * 100           # fps, frames (3 s), layer scale: 24-unit grid -> 512 px
Y = [1, 199 / 255, 44 / 255, 1]                # #FFC72C
B = [17 / 255, 18 / 255, 20 / 255, 1]          # #111214
EASE_O, EASE_I = {"x": [0.33], "y": [0]}, {"x": [0.67], "y": [1]}
LIN_O, LIN_I = {"x": [0], "y": [0]}, {"x": [1], "y": [1]}


# ---------- property / shape helpers ----------
def st(v):
    return {"a": 0, "k": v}


def anim(keys, linear=False):
    """keys: [(frame, value), ...] -> animated property; value may be a number or list."""
    o, i = (LIN_O, LIN_I) if linear else (EASE_O, EASE_I)
    ks = []
    for n, (t, v) in enumerate(keys):
        k = {"t": t, "s": v if isinstance(v, list) else [v]}
        if n < len(keys) - 1:
            k.update(o=o, i=i)
        ks.append(k)
    return {"a": 1, "k": ks}


def path(d):
    p = PathDParser(d)
    p.parse()
    return [{"ty": "sh", "ks": st(b.to_dict())} for b in p.paths]


def rect(x, y, w, h, r=0):
    return {"ty": "rc", "p": st([x + w / 2, y + h / 2]), "s": st([w, h]), "r": st(r)}


def ellipse(cx, cy, r):
    return {"ty": "el", "p": st([cx, cy]), "s": st([2 * r, 2 * r])}


def fill(c):
    return {"ty": "fl", "c": st(c), "o": st(100), "r": 1}


def stroke(c, w):
    return {"ty": "st", "c": st(c), "o": st(100), "w": st(w), "lc": 2, "lj": 2}


def trim(end):
    return {"ty": "tm", "s": st(0), "e": end, "o": st(0), "m": 1}


def tr(p=None, s=None, r=None, o=None, a=(12, 12)):
    return {"ty": "tr", "a": st(list(a)), "p": p or st(list(a)), "s": s or st([100, 100]), "r": r or st(0), "o": o or st(100)}


def group(items, transform=None):
    return {"ty": "gr", "it": items + [transform or tr()]}


def layer(ind, name, shapes):
    ks = {"a": st([12, 12, 0]), "p": st([256, 256, 0]), "s": st([K, K, 100]), "r": st(0), "o": st(100)}
    return {"ddd": 0, "ind": ind, "ty": 4, "nm": name, "sr": 1, "ks": ks, "ao": 0, "shapes": shapes,
            "ip": 0, "op": OP, "st": 0, "bm": 0}


def base():
    return [group([rect(1, 1, 22, 22, 6), fill(Y)])]


# ---------- digits from the font ----------
FONT = TTFont(r"C:\Windows\Fonts\ariblk.ttf")


def digit_path(ch, height=11.0, cx=12.0, cy=12.0):
    gs = FONT.getGlyphSet()
    g = gs[FONT.getBestCmap()[ord(ch)]]
    bp = BoundsPen(gs)
    g.draw(bp)
    x0, y0, x1, y1 = bp.bounds
    s = height / (y1 - y0)
    sp = SVGPathPen(gs)
    # font y-up -> grid y-down, centred on (cx, cy)
    g.draw(TransformPen(sp, (s, 0, 0, -s, cx - s * (x0 + x1) / 2, cy + s * (y0 + y1) / 2)))
    return sp.getCommands()


# ---------- icons ----------
def pop(t0=0):
    return anim([(0, [100, 100]), (t0 + 1, [60, 60]), (t0 + 11, [115, 115]), (t0 + 19, [95, 95]), (t0 + 25, [100, 100])])


def icon_glyph(name):
    if name == "taxi":
        g = [rect(9, 4.6, 6, 2.6, .8), fill(B)], [*path("M5 15.5V12l2-4h10l2 4v3.5z"), fill(B)], \
            [rect(8, 9.2, 8, 2.4, .6), fill(Y)], [ellipse(8, 16.5, 2), ellipse(16, 16.5, 2), fill(B)]
        move = anim([(0, [12, 12]), (1, [10.6, 12]), (20, [12, 12]), (26, [12, 11.4]), (32, [12, 12]), (38, [12, 11.6]), (44, [12, 12])])
        # draw order: last group is drawn first -> window above body
        return [group([group(list(g[2])), group(list(g[0])), group(list(g[3])), group(list(g[1]))], tr(p=move))]
    if name == "driver":
        rot = anim([(0, 0), (15, -35), (32, 25), (46, 0)])
        return [group([group([ellipse(12, 12, 6.6), stroke(B, 2.4)]), group([ellipse(12, 12, 1.9), fill(B)]),
                       group([*path("M5.6 11h4.6M13.8 11h4.6M12 13.6v4.8"), stroke(B, 2.2)])], tr(r=rot))]
    if name == "check":
        return [group([*path("M6 12.5l4 4 8-9"), stroke(B, 2.8), trim(anim([(0, 100), (1, 0), (25, 100)]))])]
    if name == "pin":
        move = anim([(0, [12, 19.5]), (1, [12, 16]), (15, [12, 19.5]), (23, [12, 18.7]), (31, [12, 19.5])])
        squash = anim([(0, [100, 100]), (15, [112, 88]), (25, [100, 100])])
        return [group([group([ellipse(12, 10, 2.2), fill(Y)]),
                       group([*path("M12 4.5a5.5 5.5 0 0 1 5.5 5.5c0 4-5.5 9.5-5.5 9.5S6.5 14 6.5 10A5.5 5.5 0 0 1 12 4.5z"), fill(B)])],
                      tr(p=move, s=squash, a=(12, 19.5)))]
    if name == "shield":
        pulse = anim([(0, [100, 100]), (12, [114, 114]), (26, [100, 100])])
        return [group([group([*path("M9 12l2.2 2.2L15.5 10"), stroke(Y, 2), trim(anim([(0, 100), (1, 0), (8, 0), (30, 100)]))]),
                       group([*path("M12 4l6.5 2.5v5c0 4-3 7-6.5 8.5C8.5 18.5 5.5 15.5 5.5 11.5v-5z"), fill(B)])], tr(s=pulse))]
    if name == "chat":
        dots = []
        for n, x in enumerate((9, 12, 15)):
            keys = []
            keys = [(0, 100), (1, 30)]
            for c in range(2):                          # two typing cycles, then rest
                t = 2 + c * 40 + n * 8
                keys += [(t + 10, 100), (t + 22, 30)]
            keys.append((110, 100))
            dots.append(group([ellipse(x, 11, 1.1), fill(Y)], tr(o=anim(keys))))
        return [group(dots + [group([*path("M5 6.5h14v9H10l-4 3v-3H5z"), fill(B)])])]
    if name == "question":
        rot = anim([(0, 0), (10, -12), (20, 10), (28, -5), (36, 0)])
        return [group([group([ellipse(12, 17.4, 1.5), fill(B)]),
                       group([*path("M9.2 9.3a2.9 2.9 0 1 1 4.3 2.5c-1 .6-1.5 1.1-1.5 2.4"), stroke(B, 2.5)])], tr(r=rot, a=(12, 18)))]
    if name == "megaphone":
        pulse = anim([(0, [100, 100]), (8, [108, 108]), (16, [100, 100]), (24, [108, 108]), (32, [100, 100])])
        wave = anim([(0, 100), (1, 0), (9, 100), (30, 100), (40, 0), (48, 100)])
        return [group([group([*path("M17.5 9.5a3.5 3.5 0 0 1 0 5"), stroke(B, 1.8)], tr(o=wave)),
                       group([*path("M5 10h3l7-4v12l-7-4H5z"), *path("M8.5 14.5l1 4h2l-1-4"), fill(B)])], tr(s=pulse))]
    if name == "card":
        rot = anim([(0, 0), (12, -10), (28, 0)])
        return [group([group([rect(6.8, 13.6, 4.5, 1.6, .8), fill(Y)]), group([rect(4.5, 9.2, 15, 2), fill(Y)]),
                       group([rect(4.5, 7, 15, 10.5, 2), fill(B)])], tr(r=rot))]
    if name == "star":                                  # a path, not a Star Shape (forbidden)
        return [group([*path("M12 4.6l2.2 4.6 5 .7-3.6 3.5.9 5-4.5-2.4-4.5 2.4.9-5L4.8 9.9l5-.7z"), fill(B)],
                      tr(r=anim([(0, 0), (30, 72)]), s=anim([(0, [100, 100]), (12, [120, 120]), (30, [100, 100])]), a=(12, 12.4)))]
    if name == "clock":
        minute = group([*path("M12 12V7.6"), stroke(Y, 2)], tr(r=anim([(0, 0), (45, 360)])))
        hour = group([*path("M12 12l2.8 1.8"), stroke(Y, 2)])
        return [group([minute, hour, group([ellipse(12, 12, 6.8), fill(B)])])]
    if name in ("n1", "n2", "n3"):
        return [group([*path(digit_path(name[1])), fill(B)], tr(s=pop()))]
    raise KeyError(name)


NAMES = ["taxi", "driver", "check", "pin", "shield", "chat", "question", "megaphone", "card", "star", "clock", "n1", "n2", "n3"]
SYMMETRY = {"star": 72}                         # rotating a 5-point star by 72 deg looks identical


def loop_problems(d, sym=360):
    """Design rule: frame 0 must equal the resting end state, so (1) the loop is seamless and (2) the static
    first frame Telegram shows in power-saving mode is the complete icon. Rotation is compared modulo `sym`."""
    out = []

    def walk(o, path):
        if isinstance(o, dict):
            if o.get("a") == 1 and isinstance(o.get("k"), list) and o["k"] and isinstance(o["k"][0], dict):
                ks = o["k"]
                first, last = ks[0], ks[-1]
                v0, v1 = first["s"], last["s"]
                if first.get("t", 0) != 0:
                    out.append(f"{path}: first keyframe at {first.get('t')} (frame 0 not set)")
                elif path.endswith(".r"):
                    if (v0[0] - v1[0]) % sym:
                        out.append(f"{path}: rotation {v0[0]} -> {v1[0]}")
                elif any(abs(a - b) > 1e-6 for a, b in zip(v0, v1)):
                    out.append(f"{path}: {v0} -> {v1}")
            for k, v in o.items():
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
    walk(d.get("layers"), "layers")
    return out


def build(name):
    return {"tgs": 1, "v": "5.5.2", "fr": FR, "ip": 0, "op": OP, "w": 512, "h": 512, "nm": f"tulporgo-{name}", "ddd": 0,
            "assets": [], "layers": [layer(1, "glyph", icon_glyph(name)), layer(2, "base", base())]}


def write(name, out_dir=os.path.join(HERE, "tgs")):
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, name + ".tgs")
    raw = json.dumps(build(name), separators=(",", ":"))
    with gzip.open(p, "wb", compresslevel=9) as f:
        f.write(raw.encode())
    return p


if __name__ == "__main__":
    for n in NAMES:
        p = write(n)
        print(f"{n:10s} {os.path.getsize(p) / 1024:5.1f} KB")
