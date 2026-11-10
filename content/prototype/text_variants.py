"""Render 5 'text on image' variants (4:5, 1080x1350) with brand fonts via headless Edge.

Copy is in the new Uzbek Latin alphabet (O'→Ö, G'→Ğ, Sh→Ş, Ch→Ç). No invented numbers or promises.
"""
import os, subprocess, tempfile, pathlib

HERE = pathlib.Path(__file__).resolve().parent
V = (HERE / ".." / ".." / "brand" / "mascot" / "directions" / "vector").resolve()
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
MASCOT = (V / "10-taksi-haydovchi-brand-1024.png").as_uri()
LOGO = (V / "02-uchayotgan-minimal-brand-dark-1024.png").as_uri()

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@600;800&family=Manrope:wght@600;700;800&display=block');
*{box-sizing:border-box;margin:0}html,body{width:1080px;height:1350px;overflow:hidden}
.c{position:relative;width:1080px;height:1350px;background:#FFC72C;overflow:hidden;font-family:Manrope,sans-serif;color:#111214}
.ring{position:absolute;border-radius:50%}
.r1{width:1500px;height:1500px;left:-210px;top:60px;background:#FFD24F}.r2{width:1000px;height:1000px;left:40px;top:330px;background:#FFDA6B}
.road{position:absolute;left:0;right:0;bottom:0;height:190px;background:#111214}
.road i{position:absolute;bottom:95px;width:60px;height:14px;background:#fff}
.logo{position:absolute;left:44px;top:44px;width:150px;height:150px;border-radius:30px;background:#111214;padding:14px}
.logo img{width:100%;height:100%}
.m{position:absolute}
.h{font-family:Unbounded,sans-serif;font-weight:800;letter-spacing:-1px;line-height:1.02}
"""
ROAD = '<div class="road">' + "".join(f'<i style="left:{x+20}px"></i>' for x in range(0, 1080, 120)) + "</div>"
BG = '<div class="ring r1"></div><div class="ring r2"></div>' + ROAD
LOGO_HTML = f'<div class="logo"><img src="{LOGO}"></div>'

VARIANTS = {
    "A-matnsiz": ("Matnsiz (hozirgi prototip)", f"""{BG}
<img class="m" src="{MASCOT}" style="width:900px;left:90px;bottom:120px">{LOGO_HTML}"""),

    "B-tepada-sarlavha": ("Tepada katta sarlavha", f"""{BG}
<img class="m" src="{MASCOT}" style="width:760px;left:160px;bottom:120px">{LOGO_HTML}
<div style="position:absolute;left:230px;right:44px;top:56px">
  <div class="h" style="font-size:78px">Qöşrabot →<br>Samarqand</div>
  <div style="font-size:38px;font-weight:700;margin-top:18px">Taksini bot orqali toping</div>
</div>"""),

    "C-pastki-plashka": ("Pastda qora plashka", f"""{BG}
<img class="m" src="{MASCOT}" style="width:860px;left:110px;bottom:330px">{LOGO_HTML}
<div style="position:absolute;left:0;right:0;bottom:0;height:360px;background:#111214;padding:56px 64px">
  <div class="h" style="font-size:72px;color:#FFC72C">Qöşrabot → Samarqand</div>
  <div style="font-size:40px;font-weight:700;color:#fff;margin-top:22px">Narxni haydovçi bilan özingiz kelişasiz</div>
  <div style="position:absolute;right:64px;bottom:48px;font-size:30px;font-weight:800;color:#FFC72C">@tulporgobot</div>
</div>"""),

    "D-yonalish-stikeri": ("Yo'nalish stikeri (minimal matn)", f"""{BG}
<img class="m" src="{MASCOT}" style="width:900px;left:90px;bottom:120px">{LOGO_HTML}
<div style="position:absolute;right:44px;top:62px;background:#fff;border:6px solid #111214;border-radius:999px;padding:20px 34px;box-shadow:10px 10px 0 #111214">
  <div class="h" style="font-size:42px">Qöşrabot → Samarqand</div>
</div>
<div style="position:absolute;right:60px;top:212px;background:#111214;color:#FFC72C;border-radius:999px;padding:12px 28px;font-size:32px;font-weight:800">bot orqali</div>"""),

    "E-katta-tipografika": ("Reklama: chapda katta matn", f"""<div class="ring r1" style="left:300px"></div>{ROAD}
<img class="m" src="{MASCOT}" style="width:740px;left:400px;bottom:110px">{LOGO_HTML}
<div style="position:absolute;left:56px;top:250px;width:640px">
  <div class="h" style="font-size:112px">Taksi<br>topiş<br>endi<br>oson</div>
  <div style="font-size:36px;font-weight:700;margin-top:30px;max-width:400px">Yönalişni yozing — haydovçilar özi taklif yuboradi</div>
</div>"""),
}


def render(name, body, out_png):
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head><body><div class='c'>{body}</div></body></html>"
    src = HERE / f"_tmp-{name}.html"
    src.write_text(html, encoding="utf-8")
    prof = tempfile.mkdtemp(prefix="edge-headless-")
    subprocess.run([EDGE, "--headless=new", f"--user-data-dir={prof}", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", "--virtual-time-budget=8000", "--window-size=1080,1350",
                    f"--screenshot={out_png}", src.as_uri()], check=True, capture_output=True, timeout=120)
    src.unlink()


if __name__ == "__main__":
    out = HERE / "text-variants"
    out.mkdir(exist_ok=True)
    for name, (label, body) in VARIANTS.items():
        p = out / f"{name}.png"
        render(name, body, str(p))
        print(name, p.stat().st_size)
