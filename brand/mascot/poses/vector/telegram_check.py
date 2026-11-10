"""Validate telegram/ files against Telegram sticker/emoji limits. Exit 13 if anything breaks a limit.

static sticker : WEBP/PNG, one side 512 and the other <= 512, <= 512 KB, transparent corners, no border holes
custom emoji   : 100x100 PNG, transparent corners
video sticker  : WEBM VP9, 512 side, <= 3 s, <= 30 fps, no audio, alpha, <= 256 KB
video emoji    : WEBM VP9, 100x100, <= 3 s, no audio, alpha, <= 64 KB
vector emoji   : TGS (gzip Lottie), 512x512 canvas, 60 fps, <= 3 s, "tgs": 1, <= 64 KB
Usage: python telegram_check.py [names...]
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
import png_holes

V = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(V, "telegram")


def check_image(p, side, max_kb, exact=False, holes=False):
    if not os.path.exists(p):
        return ["missing"]
    pr = []
    im = Image.open(p)
    w, h = im.size
    if exact and (w, h) != (side, side): pr.append(f"size {w}x{h}")
    if not exact and (max(w, h) != side or min(w, h) > side): pr.append(f"size {w}x{h}")
    if os.path.getsize(p) > max_kb * 1024: pr.append(f"{os.path.getsize(p) // 1024}KB")
    a = im.convert("RGBA").getchannel("A")
    if max(a.getpixel((0, 0)), a.getpixel((w - 1, h - 1))) > 0: pr.append("opaque corner")
    if holes:
        k = png_holes.hole_mask(np.array(a))[1]
        if k: pr.append(f"{k} border holes")
    return pr


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", p],
                       capture_output=True, text=True)
    return json.loads(r.stdout or "{}")


def check_video(p, side, max_kb, exact=False):
    if not os.path.exists(p):
        return ["missing"]
    pr = []
    j = probe(p)
    streams = j.get("streams", [])
    v = [s for s in streams if s.get("codec_type") == "video"]
    if any(s.get("codec_type") == "audio" for s in streams): pr.append("audio")
    if not v: return pr + ["no video"]
    v = v[0]
    if v.get("codec_name") != "vp9": pr.append("codec " + str(v.get("codec_name")))
    w, h = v["width"], v["height"]
    if (exact and (w, h) != (side, side)) or (not exact and max(w, h) != side): pr.append(f"size {w}x{h}")
    num, den = map(int, v.get("r_frame_rate", "0/1").split("/"))
    if den and num / den > 30.01: pr.append("fps")
    if float(j.get("format", {}).get("duration", 99)) > 3.0: pr.append("duration")
    if os.path.getsize(p) > max_kb * 1024: pr.append(f"{os.path.getsize(p) // 1024}KB")
    if v.get("tags", {}).get("alpha_mode") != "1": pr.append("no alpha")
    return pr


FORBIDDEN_LAYERS = {1: "solid layer", 2: "image layer", 5: "text layer"}
FORBIDDEN_SHAPES = {"mm": "merge paths", "sr": "star shape", "gs": "gradient stroke", "rp": "repeater"}


def tgs_forbidden(d):
    """AE features Telegram forbids in TGS (core.telegram.org/stickers): expressions, masks, layer effects,
    images, solids, texts, 3D layers, merge paths, star shapes, gradient strokes, repeaters, time stretching,
    time remapping, auto-oriented layers."""
    found = set()
    if d.get("ddd") == 1:
        found.add("3D layer")
    if any(a.get("p") or a.get("u") for a in d.get("assets", []) if isinstance(a, dict) and "layers" not in a):
        found.add("image asset")

    def walk_shapes(items):
        for s in items or []:
            if s.get("ty") in FORBIDDEN_SHAPES:
                found.add(FORBIDDEN_SHAPES[s["ty"]])
            walk_shapes(s.get("it"))

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("x"), str):
                found.add("expression")
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    layers = list(d.get("layers", [])) + [l for a in d.get("assets", []) if isinstance(a, dict) for l in a.get("layers", [])]
    for l in layers:
        if l.get("ty") in FORBIDDEN_LAYERS:
            found.add(FORBIDDEN_LAYERS[l["ty"]])
        if l.get("ddd") == 1:
            found.add("3D layer")
        if l.get("masksProperties"):
            found.add("mask")
        if l.get("ef"):
            found.add("layer effect")
        if "tm" in l:
            found.add("time remapping")
        if l.get("sr", 1) != 1:
            found.add("time stretching")
        if l.get("ao") == 1:
            found.add("auto-orient")
        walk_shapes(l.get("shapes"))
    walk(d)
    return sorted(found)


def check_tgs(p):
    import gzip
    if not os.path.exists(p):
        return ["missing"]
    pr = []
    if os.path.getsize(p) > 64 * 1024: pr.append(f"{os.path.getsize(p) // 1024}KB")
    try:
        d = json.load(gzip.open(p))
    except Exception:
        return pr + ["not gzip json"]
    if (d.get("w"), d.get("h")) != (512, 512): pr.append(f"canvas {d.get('w')}x{d.get('h')}")
    if d.get("fr") != 60: pr.append(f"fps {d.get('fr')}")
    if (d.get("op", 0) - d.get("ip", 0)) / max(d.get("fr") or 60, 1) > 3: pr.append("duration")
    if d.get("tgs") != 1: pr.append("no tgs flag")
    pr += [f"forbidden: {f}" for f in tgs_forbidden(d)]
    return pr


if __name__ == "__main__":
    names = sys.argv[1:] or [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]
    fails = 0
    for n in names:
        pr = check_image(os.path.join(T, "sticker", n + ".webp"), 512, 512, holes=True) + \
             check_image(os.path.join(T, "sticker", n + ".png"), 512, 512, holes=True) + \
             check_image(os.path.join(T, "emoji", n + ".png"), 100, 512, exact=True) + \
             check_video(os.path.join(T, "video", n + ".webm"), 512, 256) + \
             check_video(os.path.join(T, "video_emoji", n + ".webm"), 100, 64, exact=True) + \
             check_tgs(os.path.join(T, "emoji_tgs", n + ".tgs"))
        fails += bool(pr)
        print(n, "OK" if not pr else "FAIL " + ",".join(pr))
    sys.exit(13 if fails else 0)
