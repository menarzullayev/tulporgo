"""Render a 4-frame 1:1 carousel (1280x1280) in brand fonts via headless Edge.

Copy in the new Uzbek Latin alphabet (O'→Ö, G'→Ğ, Sh→Ş, Ch→Ç). No invented numbers or promises.
"""
import pathlib, subprocess, tempfile

HERE = pathlib.Path(__file__).resolve().parent
V = (HERE / ".." / ".." / "brand" / "mascot" / "directions" / "vector").resolve()
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TAXI = (V / "10-taksi-haydovchi-brand-1024.png").as_uri()
CHIBI = (V / "09-chibi-stiker-brand-1024.png").as_uri()
LOGO = (V / "02-uchayotgan-minimal-brand-dark-1024.png").as_uri()
S = 1280

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@800&family=Manrope:wght@600;700;800&display=block');
*{{box-sizing:border-box;margin:0}}html,body{{width:{S}px;height:{S}px;overflow:hidden}}
.c{{position:relative;width:{S}px;height:{S}px;background:#FFC72C;overflow:hidden;font-family:Manrope,sans-serif;color:#111214}}
.ring{{position:absolute;border-radius:50%;background:#FFD24F}}
.logo{{position:absolute;left:52px;top:52px;width:150px;height:150px;border-radius:30px;background:#111214;padding:14px}}.logo img{{width:100%;height:100%}}
.h{{font-family:Unbounded,sans-serif;font-weight:800;letter-spacing:-1px;line-height:1.04}}
.num{{position:absolute;left:56px;top:250px;width:190px;height:190px;border-radius:50%;background:#111214;color:#FFC72C;
     font-family:Unbounded;font-weight:800;font-size:120px;display:flex;align-items:center;justify-content:center}}
.dots{{position:absolute;left:0;right:0;bottom:48px;display:flex;gap:16px;justify-content:center}}
.dots i{{width:18px;height:18px;border-radius:50%;background:#111214;opacity:.25}}.dots i.on{{opacity:1}}
"""
LOGO_HTML = f'<div class="logo"><img src="{LOGO}"></div>'


def dots(k):
    return '<div class="dots">' + "".join(f'<i class="{"on" if i == k else ""}"></i>' for i in range(4)) + "</div>"


def step(k, title, sub):
    return f"""<div class="ring" style="width:1300px;height:1300px;left:380px;top:300px"></div>{LOGO_HTML}
<div class="num">{k}</div>
<div style="position:absolute;left:56px;top:480px;width:640px">
  <div class="h" style="font-size:92px">{title}</div>
  <div style="font-size:42px;font-weight:700;margin-top:28px">{sub}</div>
</div>
<img src="{CHIBI}" style="position:absolute;width:640px;right:20px;bottom:120px">{dots(k)}"""


FRAMES = {
    "f1": f"""<div class="ring" style="width:1500px;height:1500px;left:-110px;top:420px"></div>{LOGO_HTML}
<div style="position:absolute;left:250px;right:52px;top:62px">
  <div class="h" style="font-size:96px">Taksini qanday topasiz?</div>
  <div style="display:inline-block;margin-top:26px;background:#111214;color:#FFC72C;border-radius:999px;padding:14px 32px;font-size:40px;font-weight:800">3 qadam · @tulporgobot</div>
</div>
<img src="{TAXI}" style="position:absolute;width:780px;left:250px;bottom:90px">{dots(0)}""",
    "f2": step(1, "Yönalişni yozing", "Qayerdan, qayerga va qaçon ketasiz"),
    "f3": step(2, "Takliflar keladi", "Haydovçilar narx va maşina bilan javob beradi"),
    "f4": step(3, "Özingiz tanlaysiz", "Narxni kelişing — yölga çiqing"),
}


def render(name, body, out_png):
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='c'>{body}</div></body></html>"
    src = HERE / f"_tmp-{name}.html"
    src.write_text(html, encoding="utf-8")
    prof = tempfile.mkdtemp(prefix="edge-headless-")
    subprocess.run([EDGE, "--headless=new", f"--user-data-dir={prof}", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", "--virtual-time-budget=8000", f"--window-size={S},{S}",
                    f"--screenshot={out_png}", src.as_uri()], check=True, capture_output=True, timeout=120)
    src.unlink()


if __name__ == "__main__":
    out = HERE / "carousel"
    out.mkdir(exist_ok=True)
    for name, body in FRAMES.items():
        render(name, body, str(out / f"{name}.png"))
        print(name)
