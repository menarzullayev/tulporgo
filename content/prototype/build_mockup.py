"""Build a self-contained Telegram channel post mockup (3 image ratios, light/dark)."""
import base64, os

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, "..", "..", "brand", "mascot", "directions", "vector")


def b64(path, mime):
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


AVATAR = b64(os.path.join(V, "02-uchayotgan-minimal-brand-dark-1024.png"), "image/png")
IMGS = {k: b64(os.path.join(HERE, f"web-{k}.jpg"), "image/jpeg") for k in ("4x5", "1x1", "16x9")}
LABELS = {"4x5": "4:5 portret · 1080×1350", "1x1": "1:1 kvadrat · 1280×1280", "16x9": "16:9 gorizontal · 1280×720"}

# Sample copy — new Uzbek Latin alphabet (O'→Ö, G'→Ğ, Sh→Ş, Ch→Ç). No invented numbers or promises.
POST_UZ = """<b>Qöşrabot — Samarqand: taksini bot orqali toping</b><br><br>
Yönalişni yozing — haydovçilar taklif yuboradi.<br>
Narxni haydovçi bilan özingiz kelişasiz.<br>
Ayol yölovçilar uçun alohida belgi bor."""
POST_RU = ("Напишите маршрут — водители пришлют предложения. Цену договариваетесь с водителем сами. "
           "Для женщин-пассажиров есть отдельная отметка.")

PHONE = """
<figure class="col">
  <figcaption>{label}</figcaption>
  <div class="phone">
    <div class="bar"><img class="ava" src="{avatar}" alt="TulporGo avatari"><div><div class="ttl">TulporGo</div><div class="sub">1 248 obunaçi</div></div></div>
    <div class="feed">
      <div class="post">
        <img class="media" src="{img}" alt="Post rasmi, {label}">
        <div class="text">{uz}
          <blockquote class="exp" tabindex="0" role="button" aria-expanded="false"><span class="ru">{ru}</span></blockquote>
          <div class="meta">👁 3,4K · 09:30</div>
        </div>
      </div>
      <div class="btns"><a>🚕 Taksi çaqiriş</a><a>Haydovçi böliş</a></div>
    </div>
  </div>
</figure>"""

HTML = """<!doctype html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TulporGo post prototipi</title>
<style>
:root{--page:#e9edf2;--chat:#c9d7e3;--bub:#fff;--tx:#111214;--mu:#7c8a97;--acc:#3a8bd6;--btn:rgba(70,90,110,.35);--bar:#fff;--q:#3a8bd6}
:root[data-theme=dark]{--page:#0e1117;--chat:#0f1923;--bub:#182533;--tx:#e8edf2;--mu:#7d8b99;--acc:#6ab3f3;--btn:rgba(30,45,60,.75);--bar:#17212b;--q:#6ab3f3}
*{box-sizing:border-box}body{margin:0;background:var(--page);font:15px/1.4 -apple-system,"Segoe UI",Roboto,sans-serif;color:var(--tx)}
header{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:16px}
h1{font-size:18px;margin:0}.note{color:var(--mu);font-size:13px;margin:4px 0 0}
button{border:0;border-radius:10px;padding:8px 14px;background:#FFC72C;color:#111214;font-weight:700;cursor:pointer}
.row{display:flex;gap:20px;justify-content:center;flex-wrap:wrap;padding:0 16px 24px}
.col{margin:0}figcaption{text-align:center;font-weight:700;margin-bottom:8px}
.phone{width:340px;max-width:calc(100vw - 32px);height:720px;border-radius:28px;overflow:hidden;background:var(--chat);box-shadow:0 10px 30px rgba(0,0,0,.18);display:flex;flex-direction:column}
.bar{display:flex;gap:10px;align-items:center;padding:10px 14px;background:var(--bar)}
.ava{width:38px;height:38px;border-radius:50%;background:#111214;object-fit:contain;padding:3px}
.ttl{font-weight:700}.sub{font-size:12px;color:var(--mu)}
.feed{flex:1;overflow-y:auto;padding:12px 10px;display:flex;flex-direction:column}.post{margin-top:auto}
.post{background:var(--bub);border-radius:14px;overflow:hidden}
.media{display:block;width:100%;height:auto}
.text{padding:8px 10px 6px}
.exp{margin:8px 0 0;padding:4px 8px;border-left:3px solid var(--q);background:color-mix(in srgb,var(--q) 12%,transparent);border-radius:4px;cursor:pointer;position:relative}
.exp .ru{display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;padding-right:18px}
.exp::after{content:"⌄";position:absolute;right:6px;top:2px;color:var(--q)}
.exp[aria-expanded=true] .ru{-webkit-line-clamp:unset}.exp[aria-expanded=true]::after{content:"⌃"}
.meta{text-align:right;font-size:12px;color:var(--mu);margin-top:4px}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:4px}
.btns a{background:var(--btn);color:#fff;text-align:center;padding:9px 4px;border-radius:10px;font-weight:600;font-size:14px}
</style></head><body>
<header><div><h1>TulporGo · kanal posti prototipi</h1>
<p class="note">Namuna matn (yangi alifbo). Ruscha blokni bosib oching. Tugmalar ishlamaydi.</p></div>
<button id="t">Qorong'i / yorug' mavzu</button></header>
<div class="row">{phones}</div>
<script>
document.querySelectorAll('.exp').forEach(q=>{const f=()=>q.setAttribute('aria-expanded',q.getAttribute('aria-expanded')!=='true');q.onclick=f;q.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();f()}}});
const r=document.documentElement;document.getElementById('t').onclick=()=>{r.dataset.theme=r.dataset.theme==='dark'?'light':'dark'};
</script></body></html>"""

phones = "".join(PHONE.format(label=LABELS[k], avatar=AVATAR, img=IMGS[k], uz=POST_UZ, ru=POST_RU) for k in ("4x5", "1x1", "16x9"))
out = os.path.join(HERE, "post-prototip.html")
open(out, "w", encoding="utf-8").write(HTML.replace("{phones}", phones))
print(out, os.path.getsize(out))
