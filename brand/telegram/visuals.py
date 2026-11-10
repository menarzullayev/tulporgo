"""Stage 2 visuals (TELEGRAM-REJA.md): channel welcome image (16:9) and the pinned «Bu yerdan boshlang» carousel
(RM panorama, decision 37: one 5120x1280 canvas cut into 4 frames; route line and tulpor cross the frame borders;
a different approved pose on every border). Style = post templates (decision 36): yellow, rings, road, 02 tile,
Unbounded 800 + Manrope. Copy is written in current Latin and converted to the new alphabet (decision 29).
Poses come from the vector PNGs with border holes filled (png_holes, MUAMMOLAR #27).
Usage: python visuals.py   -> out/welcome-channel.png, out/carousel/f1..f4.png (+ panorama.png)
"""
import os, pathlib, subprocess, sys, tempfile

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "content" / "i18n"))
sys.path.insert(0, str(ROOT / "brand" / "mascot" / "poses" / "vector"))
from alphabet import convert  # noqa: E402
import png_holes  # noqa: E402

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
DIRS = ROOT / "brand" / "mascot" / "directions" / "vector"
POSES = ROOT / "brand" / "mascot" / "poses" / "vector" / "png"
OUT = HERE / "out"
LOGO = (DIRS / "02-uchayotgan-minimal-brand-dark-1024.png").as_uri()
TAXI = (DIRS / "10-taksi-haydovchi-brand-1024.png").as_uri()
uz = lambda s: convert(s, "uz_new")

FONTS = "@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@800&family=Manrope:wght@700;800&display=block');"
BASE = """*{box-sizing:border-box;margin:0}
.p{position:relative;background:#FFC72C;overflow:hidden;font-family:Manrope,sans-serif;color:#111214}
.ring{position:absolute;border-radius:50%;background:#FFD24F}
.logo{position:absolute;width:150px;height:150px;border-radius:30px;background:#111214;padding:14px}.logo img{width:100%;height:100%}
.h{font-family:Unbounded,sans-serif;font-weight:800;letter-spacing:-1px;line-height:1.04}
.pill{display:inline-block;background:#111214;color:#FFC72C;border-radius:999px;padding:14px 32px;font-size:40px;font-weight:800}
.num{position:absolute;width:170px;height:170px;border-radius:50%;background:#111214;color:#FFC72C;font-family:Unbounded;
     font-weight:800;font-size:108px;display:flex;align-items:center;justify-content:center}
.road{position:absolute;left:0;right:0;bottom:0;background:#111214}.road i{position:absolute;height:14px;width:60px;background:#fff}
.pin{position:absolute;width:110px;height:110px;background:#111214;border-radius:50% 50% 50% 0;transform:rotate(-45deg)}
.pin::after{content:"";position:absolute;left:32px;top:32px;width:46px;height:46px;border-radius:50%;background:#FFC72C}
.lbl{position:absolute;background:#fff;border:5px solid #111214;border-radius:999px;padding:10px 26px;font-family:Unbounded;
     font-weight:800;font-size:40px;box-shadow:7px 7px 0 #111214}"""


def pose(name, tmp):
    """Transparent pose PNG with border holes filled, as a file URI."""
    p = pathlib.Path(tmp) / f"{name}.png"
    if not p.exists():
        png_holes.fill(Image.open(POSES / f"{name}.png"))[0].save(p)
    return p.as_uri()


def shoot(body, w, h, out):
    prof = tempfile.mkdtemp(prefix="edge-headless-")
    src = pathlib.Path(tempfile.mkdtemp()) / "p.html"
    src.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{FONTS}{BASE}"
                   f"html,body{{width:{w}px;height:{h}px;overflow:hidden}}.p{{width:{w}px;height:{h}px}}</style></head>"
                   f"<body><div class='p'>{body}</div></body></html>", encoding="utf-8")
    subprocess.run([EDGE, "--headless=new", f"--user-data-dir={prof}", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", "--virtual-time-budget=8000", f"--window-size={w},{h}",
                    f"--screenshot={out}", src.as_uri()], check=True, capture_output=True, timeout=180)
    im = Image.open(out)
    assert im.size == (w, h), im.size
    return im


def welcome(tmp):
    W, H = 1280, 720
    road = '<div class="road" style="height:110px">' + "".join(f'<i style="left:{x + 20}px;bottom:48px"></i>' for x in range(0, W, 120)) + "</div>"
    body = f"""<div class="ring" style="width:1100px;height:1100px;left:520px;top:-300px"></div>
<div class="ring" style="width:700px;height:700px;left:700px;top:-60px;background:#FFDA6B"></div>{road}
<div class="logo" style="left:48px;top:44px"><img src="{LOGO}"></div>
<div style="position:absolute;left:52px;top:215px;width:640px">
  <div class="h" style="font-size:84px">{uz("Xush kelibsiz!")}</div>
  <div style="font-size:36px;font-weight:700;margin-top:18px;line-height:1.25">{uz("Taksini Telegram'dan chaqiring — haydovchilar o'zi taklif yuboradi")}</div>
  <div class="pill" style="margin-top:24px">@tulporgobot</div></div>
<img src="{pose("09-01-salomlashadi", tmp)}" style="position:absolute;width:600px;right:40px;bottom:40px">"""
    return shoot(body, W, H, OUT / "welcome-channel.png")


STEPS = [(1, "Yo'nalishni yozing", "Botga: qayerdan, qayerga va qachon"),
         (2, "Takliflar keladi", "Haydovchilar narx va mashina bilan javob beradi"),
         (3, "O'zingiz tanlaysiz", "Ma'qulini tanlang, narxni kelishing — yo'lga chiqing")]
BORDER_POSES = ["09-05-telefonda-yozyapti", "09-06-telefon-korsatyapti", "09-08-bosh-barmoq"]


def carousel(tmp):
    S, W = 1280, 5120
    pad = 340
    h = []
    for i in range(4):
        h.append(f'<div class="logo" style="left:{i * S + 52}px;top:52px"><img src="{LOGO}"></div>')
        h.append(f'<div class="ring" style="width:1100px;height:1100px;left:{i * S + 300}px;top:-420px;opacity:.6"></div>')
    h.append(f"""<div style="position:absolute;left:250px;top:62px;width:980px"><div class="h" style="font-size:100px">{uz("Bu yerdan boshlang")}</div>
      <div class="pill" style="margin-top:26px">{uz("3 qadam · @tulporgobot")}</div></div>""")
    for i, (k, t, sub) in enumerate(STEPS, start=1):
        x = i * S + pad
        h.append(f'<div class="num" style="left:{x}px;top:250px">{k}</div>')
        h.append(f"""<div style="position:absolute;left:{x}px;top:450px;width:{S - pad - 80}px"><div class="h" style="font-size:84px">{uz(t)}</div>
          <div style="font-size:42px;font-weight:700;margin-top:24px;max-width:780px">{uz(sub)}</div></div>""")
    h.append(f"""<svg style="position:absolute;left:0;top:0" width="{W}" height="{S}" viewBox="0 0 {W} {S}">
  <path d="M 420 1010 C 900 1180, 1100 930, 1500 1000 S 2300 1160, 2700 1020 S 3500 900, 3850 1030 S 4500 1180, 4720 1090"
        fill="none" stroke="#111214" stroke-width="18" stroke-linecap="round" stroke-dasharray="2 46"/></svg>
<div class="pin" style="left:365px;top:870px"></div><div class="lbl" style="left:190px;top:745px">{uz("Qo'shrabot")}</div>
<div class="pin" style="left:4665px;top:950px"></div><div class="lbl" style="left:4440px;top:830px">Samarqand</div>
<img src="{TAXI}" style="position:absolute;width:500px;left:520px;top:520px">""")
    size, top = 560, 600
    for b, name in zip((S, 2 * S, 3 * S), BORDER_POSES):
        h.append(f'<img src="{pose(name, tmp)}" style="position:absolute;width:{size}px;left:{b - size // 2}px;top:{top}px">')
    d = OUT / "carousel"
    d.mkdir(parents=True, exist_ok=True)
    im = shoot("".join(h), W, S, d / "panorama.png").convert("RGB")
    for i in range(4):
        im.crop((i * S, 0, (i + 1) * S, S)).save(d / f"f{i + 1}.png")
    return d


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="poses-")
    print(welcome(tmp).size, carousel(tmp))
