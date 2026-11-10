"""Render TGS files to PNG for visual checks: TGS -> SVG (python-lottie) -> headless Edge screenshot.
Usage: python tgs_render.py <size> <out.png> <a.tgs> [b.tgs ...]   (tiles side by side on dark bg)"""
import os, re, shutil, subprocess, sys, tempfile

LC = shutil.which("lottie_convert.py") or shutil.which("lottie_convert")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
size, out, files = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
tmp = tempfile.mkdtemp()
cells = []
for i, f in enumerate(files):
    sv = os.path.join(tmp, f"{i}.svg")
    subprocess.run([sys.executable, LC, f, sv], check=True, capture_output=True)
    s = re.sub(r"<\?xml[^>]*>", "", open(sv, encoding="utf-8").read())
    cells.append(s.replace("<svg", f'<svg style="width:{size}px;height:{size}px;display:inline-block"', 1))
html = os.path.join(tmp, "p.html")
open(html, "w", encoding="utf-8").write('<html><body style="margin:0;background:#18191f;white-space:nowrap">' + "".join(cells) + "</body></html>")
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={size * len(files)},{size}",
                f"--screenshot={os.path.abspath(out)}", "file:///" + html.replace("\\", "/")], capture_output=True)
print(out, os.path.exists(out))
