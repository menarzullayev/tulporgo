"""Panorama carousels: one 5120x1280 canvas rendered in brand fonts, sliced into 4 frames (1280x1280).
Elements cross the frame borders, so every frame visibly continues into the next one.

R  — route line Qöşrabot → Samarqand runs through all frames; the taxi sits on the 1|2 border; chevrons on the line at each border
M  — the chibi tulpor straddles every border (half here, half in the next frame)
RM — route line + chibi on borders
Copy: new Uzbek Latin alphabet (O'→Ö, G'→Ğ, Sh→Ş, Ch→Ç).
"""
import pathlib, subprocess, sys, tempfile
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
V = (HERE / ".." / ".." / "brand" / "mascot" / "directions" / "vector").resolve()
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TAXI = (V / "10-taksi-haydovchi-brand-1024.png").as_uri()
CHIBI = (V / "09-chibi-stiker-brand-1024.png").as_uri()
LOGO = (V / "02-uchayotgan-minimal-brand-dark-1024.png").as_uri()
S, W = 1280, 5120

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@800&family=Manrope:wght@700;800&display=block');
*{{box-sizing:border-box;margin:0}}html,body{{width:{W}px;height:{S}px;overflow:hidden}}
.p{{position:relative;width:{W}px;height:{S}px;background:#FFC72C;overflow:hidden;font-family:Manrope,sans-serif;color:#111214}}
.ring{{position:absolute;border-radius:50%;background:#FFD24F}}
.logo{{position:absolute;top:52px;width:150px;height:150px;border-radius:30px;background:#111214;padding:14px}}.logo img{{width:100%;height:100%}}
.h{{font-family:Unbounded,sans-serif;font-weight:800;letter-spacing:-1px;line-height:1.04}}
.num{{position:absolute;top:250px;width:170px;height:170px;border-radius:50%;background:#111214;color:#FFC72C;
     font-family:Unbounded;font-weight:800;font-size:108px;display:flex;align-items:center;justify-content:center}}
.pin{{position:absolute;width:110px;height:110px;background:#111214;border-radius:50% 50% 50% 0;transform:rotate(-45deg)}}
.pin::after{{content:"";position:absolute;left:32px;top:32px;width:46px;height:46px;border-radius:50%;background:#FFC72C}}
.lbl{{position:absolute;background:#fff;border:5px solid #111214;border-radius:999px;padding:10px 26px;font-family:Unbounded;font-weight:800;font-size:40px;box-shadow:7px 7px 0 #111214}}
"""

STEPS = [(1, "Yönalişni yozing", "Qayerdan, qayerga va qaçon ketasiz"),
         (2, "Takliflar keladi", "Haydovçilar narx va maşina bilan javob beradi"),
         (3, "Özingiz tanlaysiz", "Narxni kelişing — yölga çiqing")]


def text_layer(left_pad):
    """Frame texts; left_pad shifts frames 2-4 text right when a mascot half sits on their left edge."""
    h = []
    for i in range(4):
        x = i * S
        h.append(f'<div class="logo" style="left:{x + 52}px"><img src="{LOGO}"></div>')
        h.append(f'<div class="ring" style="width:1100px;height:1100px;left:{x + 300}px;top:-420px;opacity:.6"></div>')
    h.append(f"""<div style="position:absolute;left:250px;top:62px;width:980px">
      <div class="h" style="font-size:96px">Taksini qanday topasiz?</div>
      <div style="display:inline-block;margin-top:26px;background:#111214;color:#FFC72C;border-radius:999px;padding:14px 32px;font-size:40px;font-weight:800">3 qadam · @tulporgobot</div></div>""")
    for i, (k, t, sub) in enumerate(STEPS, start=1):
        x = i * S + left_pad
        h.append(f'<div class="num" style="left:{x}px">{k}</div>')
        h.append(f"""<div style="position:absolute;left:{x}px;top:450px;width:{S - left_pad - 80}px">
          <div class="h" style="font-size:88px">{t}</div><div style="font-size:42px;font-weight:700;margin-top:24px;max-width:760px">{sub}</div></div>""")
    return "".join(h)


ROUTE_SVG = f"""<svg style="position:absolute;left:0;top:0" width="{W}" height="{S}" viewBox="0 0 {W} {S}">
  <path d="M 420 1010 C 900 1180, 1100 930, 1500 1000 S 2300 1160, 2700 1020 S 3500 900, 3850 1030 S 4500 1120, 4700 960"
        fill="none" stroke="#111214" stroke-width="18" stroke-linecap="round" stroke-dasharray="2 46"/>
  {''.join(f'<text x="{b - 70}" y="{y}" font-family="Unbounded" font-weight="800" font-size="90" fill="#111214">›››</text>' for b, y in ((2560, 1135), (3840, 1060)))}
</svg>
<div class="pin" style="left:365px;top:870px"></div><div class="lbl" style="left:190px;top:745px">Qöşrabot</div>
<div class="pin" style="left:4645px;top:820px"></div><div class="lbl" style="left:4420px;top:695px">Samarqand</div>
<img src="{TAXI}" style="position:absolute;width:560px;left:{S - 280}px;top:640px">"""


def chibi_borders(size=620, top=650):
    return "".join(f'<img src="{CHIBI}" style="position:absolute;width:{size}px;left:{b - size // 2}px;top:{top}px">' for b in (S, 2 * S, 3 * S))


VARIANTS = {
    "R": text_layer(56) + ROUTE_SVG,
    "M": text_layer(340) + chibi_borders()
         + f'<img src="{TAXI}" style="position:absolute;width:700px;left:300px;top:560px">',
    "RM": text_layer(340) + ROUTE_SVG.replace(f'<img src="{TAXI}" style="position:absolute;width:560px;left:{S - 280}px;top:640px">',
                                              f'<img src="{TAXI}" style="position:absolute;width:500px;left:520px;top:520px">')
          + chibi_borders(520, 600),
}
# RM: the frame-4 text is shifted right, so end the route lower to keep the Samarqand label clear of it
VARIANTS["RM"] = (VARIANTS["RM"].replace("S 4500 1120, 4700 960", "S 4500 1180, 4720 1090")
                  .replace('class="pin" style="left:4645px;top:820px"', 'class="pin" style="left:4665px;top:950px"')
                  .replace('class="lbl" style="left:4420px;top:695px"', 'class="lbl" style="left:4440px;top:830px"'))


def render(name, body):
    out = HERE / "carousel" / f"pano-{name}"
    out.mkdir(parents=True, exist_ok=True)
    src = HERE / f"_tmp-pano-{name}.html"
    src.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='p'>{body}</div></body></html>", encoding="utf-8")
    full = out / "panorama.png"
    prof = tempfile.mkdtemp(prefix="edge-headless-")
    subprocess.run([EDGE, "--headless=new", f"--user-data-dir={prof}", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", "--virtual-time-budget=8000", f"--window-size={W},{S}",
                    f"--screenshot={full}", src.as_uri()], check=True, capture_output=True, timeout=180)
    src.unlink()
    im = Image.open(full).convert("RGB")
    assert im.size == (W, S), im.size
    for i in range(4):
        im.crop((i * S, 0, (i + 1) * S, S)).save(out / f"f{i + 1}.png")
    return out


if __name__ == "__main__":
    for n in (sys.argv[1:] or VARIANTS):
        print(n, render(n, VARIANTS[n]))
