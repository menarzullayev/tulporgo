"""Export the vector poses to Telegram-ready files (problem F).

  telegram/sticker/<n>.webp   static sticker   512x512 WEBP, <= 512 KB          (from png/)
  telegram/sticker/<n>.png    same, PNG (for @Stickers bot uploads)              (from png/)
  telegram/emoji/<n>.png      custom emoji     100x100 PNG, no ground shadow     (from png_ns/)
  telegram/video/<n>.webm     video sticker    512x512 VP9+alpha, 2 s, 30 fps, <= 256 KB, no audio
  telegram/video_emoji/<n>.webm video emoji    100x100 VP9+alpha, 2 s, <= 64 KB

Small holes in the white border are filled first (png_holes.py, MUAMMOLAR #27).
The animation is a soft "hop": the art rises and lands with a small squash. Limits from
core.telegram.org/stickers. Usage: python telegram_export.py [names...]
"""
import math, os, shutil, subprocess, sys, tempfile
from PIL import Image
import png_holes

V = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(V, "telegram")
FPS, SECONDS = 30, 2


def fit(im, side):
    im = im.convert("RGBA")
    im.thumbnail((side, side), Image.LANCZOS)
    c = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    c.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    return c


def hop_frames(im, side):
    """Frames of a looping hop. Art is drawn at 86 % so the jump stays inside the canvas."""
    art = fit(im, int(side * 0.86))
    frames = []
    n = FPS * SECONDS
    for i in range(n):
        t = i / n
        phase = (t * 2) % 1.0                       # two hops per loop
        lift = math.sin(math.pi * phase)            # 0 -> 1 -> 0
        squash = max(0.0, 1 - lift * 4) * 0.06      # squash only near the ground
        w = int(art.width * (1 + squash)); h = int(art.height * (1 - squash))
        a = art.resize((w, h), Image.LANCZOS)
        c = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        y = side - h - int(side * 0.02) - int(lift * side * 0.10)
        c.paste(a, ((side - w) // 2, y), a)
        frames.append(c)
    return frames


def encode_webm(frames, out, max_kb):
    tmp = tempfile.mkdtemp()
    try:
        for i, f in enumerate(frames):
            f.save(os.path.join(tmp, f"f{i:03d}.png"))
        for crf in (34, 40, 46, 52, 58):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%03d.png"),
                            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", str(crf),
                            "-an", "-t", str(SECONDS), out], check=True)
            if os.path.getsize(out) <= max_kb * 1024:
                return crf
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(names):
    for d in ("sticker", "emoji", "video", "video_emoji"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    bad = 0
    for n in names:
        full, h1, _ = png_holes.fill(Image.open(os.path.join(V, "png", n + ".png")))      # border holes (#27)
        ns, h2, _ = png_holes.fill(Image.open(os.path.join(V, "png_ns", n + ".png")))
        st = fit(full, 512)
        st.save(os.path.join(OUT, "sticker", n + ".webp"), "WEBP", quality=90, method=6)
        st.save(os.path.join(OUT, "sticker", n + ".png"), optimize=True)
        fit(ns, 100).save(os.path.join(OUT, "emoji", n + ".png"), optimize=True)
        c1 = encode_webm(hop_frames(full, 512), os.path.join(OUT, "video", n + ".webm"), 256)
        c2 = encode_webm(hop_frames(ns, 100), os.path.join(OUT, "video_emoji", n + ".webm"), 64)
        ok = c1 is not None and c2 is not None
        bad += not ok
        print(n, f"holes filled={h1}/{h2}", f"video crf={c1}", f"video_emoji crf={c2}", "OK" if ok else "TOO BIG")
    return 12 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [l.strip() for l in open(os.path.join(V, "names.txt")) if l.strip()]))
