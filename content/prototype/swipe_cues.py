"""Render the carousel with 4 different 'swipe to next' cues (frames 1-3 get the cue, frame 4 does not).

A: big arrow button on the right edge + "Varaqlang"
B: counter pill "1/4 →" top-right
C: peek — the next frame's left edge shows on the right side (composited with PIL)
D: bottom-right pill "Surib köring »»" with hand emoji
"""
import sys, pathlib
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from carousel_frames import FRAMES, render, HERE, S

CUES = {
    "A": lambda k: """<div style="position:absolute;right:52px;top:250px;width:150px;height:150px;border-radius:50%;background:#111214;
        color:#FFC72C;font-family:Unbounded;font-weight:800;font-size:84px;display:flex;align-items:center;justify-content:center;
        box-shadow:0 10px 0 rgba(0,0,0,.18)">→</div>
        <div style="position:absolute;right:46px;top:414px;width:162px;text-align:center;font-weight:800;font-size:30px">Varaqlang</div>""",
    "B": lambda k: f"""<div style="position:absolute;left:52px;bottom:100px;background:#111214;color:#FFC72C;border-radius:999px;
        padding:14px 30px;font-family:Unbounded;font-weight:800;font-size:44px">{k + 1}/4 →</div>""",
    "C": lambda k: "",
    "D": lambda k: """<div style="position:absolute;left:52px;bottom:100px;background:#fff;border:5px solid #111214;border-radius:999px;
        padding:14px 30px;font-weight:800;font-size:40px;box-shadow:8px 8px 0 #111214">👉 Surib köring »»</div>""",
}


def peek(frames):
    """C: paste a 110px slice of the next frame on the right edge with a shadow, frames 1-3."""
    out = []
    for i, f in enumerate(frames):
        im = Image.open(f).convert("RGBA")
        if i < len(frames) - 1:
            nxt = Image.open(frames[i + 1]).convert("RGBA").crop((0, 0, 110, S))
            sh = Image.new("RGBA", (40, S), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rectangle((20, 0, 40, S), fill=(0, 0, 0, 90))
            im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (S - 130, 0))
            im.alpha_composite(nxt, (S - 110, 0))
            d = ImageDraw.Draw(im)
            d.line((S - 110, 0, S - 110, S), fill="#111214", width=6)
        im.convert("RGB").save(f)
        out.append(f)
    return out


if __name__ == "__main__":
    names = ["f1", "f2", "f3", "f4"]
    for cue, html in CUES.items():
        d = HERE / "carousel" / f"cue-{cue}"
        d.mkdir(parents=True, exist_ok=True)
        files = []
        for k, n in enumerate(names):
            body = FRAMES[n] + (html(k) if k < 3 else "")
            p = str(d / f"{n}.png")
            render(f"{cue}{n}", body, p)
            files.append(p)
        if cue == "C":
            peek(files)
        print(cue, "done")
