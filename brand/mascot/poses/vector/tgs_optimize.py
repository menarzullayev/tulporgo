"""Shrink a static TGS (from lottie_convert of an Illustrator abutting trace) so it fits Telegram's 64 KB.

Abutting-trace shapes never overlap, so their paint order does not matter: all paths with the same fill
are merged into ONE group (one fill + one transform instead of one per path). The last leaf group
(the white sticker border, painted at the back) stays last. Coordinates are rounded to `prec` decimals.
Usage: python tgs_optimize.py <in.tgs> <out.tgs> [prec]   -> prints KB; exit 15 if > 64 KB.
"""
import gzip, json, sys

LIMIT = 64 * 1024
IDENT = {"ty": "tr", "a": {"k": [0, 0], "a": 0}, "p": {"k": [0, 0], "a": 0}, "s": {"k": [100, 100], "a": 0},
         "r": {"k": 0, "a": 0}, "o": {"k": 100, "a": 0}}


def leaves(items, out):
    """Collect (fill item, [path items]) for every group that directly holds a fill."""
    shp = [x for x in items if x.get("ty") == "sh"]
    fl = [x for x in items if x.get("ty") == "fl"]
    for x in items:
        if x.get("ty") == "tr":
            t = x
            ident = t["p"]["k"][:2] == [0, 0] and t["a"]["k"][:2] == [0, 0] and t["s"]["k"][:2] == [100, 100] and t["r"]["k"] == 0
            if not ident:
                raise ValueError("non-identity group transform; cannot merge safely")
    if shp and fl:
        out.append((fl[0], shp))
    for x in items:
        if x.get("ty") == "gr":
            leaves(x["it"], out)
    return out


def rnd(o, p):
    if isinstance(o, float):
        r = round(o, p)
        return int(r) if r == int(r) else r
    if isinstance(o, list):
        return [rnd(x, p) for x in o]
    if isinstance(o, dict):
        # colours ("c") are 0..1 floats: keep 3 decimals whatever `p` is
        return {k: rnd(v, 3 if k == "c" else p) for k, v in o.items() if k not in ("nm", "mn", "hd", "ix", "cix", "np")}
    return o


def optimize(d, prec=1):
    def fix_layers(layers):
        for L in layers:
            if "shapes" in L:
                lv = leaves(L["shapes"], [])
                if not lv:
                    continue
                border, rest = lv[-1], lv[:-1]
                order, by = [], {}
                for fl, paths in rest:
                    key = json.dumps(fl["c"]["k"]) + json.dumps(fl.get("o", {}).get("k", 100))
                    if key not in by:
                        by[key] = (fl, []); order.append(key)
                    by[key][1].extend(paths)
                groups = [{"ty": "gr", "it": by[k][1] + [by[k][0], IDENT]} for k in order]
                groups.append({"ty": "gr", "it": border[1] + [border[0], IDENT]})
                L["shapes"] = groups
    fix_layers(d.get("layers", []))
    for a in d.get("assets", []):
        fix_layers(a.get("layers", []))
    return rnd(d, prec)


def encode(d):
    return gzip.compress(json.dumps(d, separators=(",", ":")).encode(), 9)


if __name__ == "__main__":
    d = json.load(gzip.open(sys.argv[1]))
    prec = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    try:
        data = encode(optimize(json.loads(json.dumps(d)), prec))
    except ValueError as e:                      # transformed groups: no merging, rounding only
        print(f"{sys.argv[1]}: {e} -> rounding only")
        data = encode(rnd(d, prec))
    open(sys.argv[2], "wb").write(data)
    print(f"{sys.argv[2]}: {len(data) // 1024} KB")
    sys.exit(15 if len(data) > LIMIT else 0)
