import os, subprocess, sys, tempfile
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clean_bg import clean

BG = (236, 236, 236)
svg = ('<svg>'
       '<path style="fill:#ECECEC;" d="M0,0h895v895z"/>'        # background touching edge -> removed
       '<path style="fill:#EDEDED;" d="M400,600h10z"/>'          # same colour inside (gap between legs) -> kept
       '<path style="fill:#FFFFFF;" d="M0,300h5z"/>'             # white sticker border on edge, far from bg -> kept
       '<path style="fill:#111214;" d="M100,100h5z"/>'
       '</svg>')
out, st = clean(svg, BG)
assert st == {"shapes": 4, "removed": 1}, st
assert "#ECECEC" not in out and "#EDEDED" in out and "#FFFFFF" in out
print("PASS clean")

# negative: an SVG whose background colour differs from the PNG corner must fail (exit 5), not silently pass
with tempfile.TemporaryDirectory() as td:
    png = os.path.join(td, "s.png"); Image.new("RGB", (895, 895), (236, 236, 236)).save(png)
    raw = os.path.join(td, "r.svg"); open(raw, "w").write('<svg><path style="fill:#3366FF;" d="M0,0h895z"/></svg>')
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "clean_bg.py"), png, raw, raw + ".o"], capture_output=True)
    assert r.returncode == 5, r.returncode
print("PASS negative")

# gradient background: top white, bottom lavender -> both edge pieces removed, character kept
svg = ('<svg><path style="fill:#FDFDFD;" d="M0,0h895z"/><path style="fill:#E6E0F0;" d="M0,895h895z"/>'
       '<path style="fill:#E6E0F0;" d="M400,500h5z"/><path style="fill:#FFC72C;" d="M300,300h5z"/></svg>')
out, st = clean(svg, [(253, 253, 253), (230, 224, 240)])
assert st["removed"] == 2 and "#FFC72C" in out and out.count("#E6E0F0") == 1, (st, out)
# negative: averaging those two corners (old behaviour) would leave both pieces
out2, st2 = clean(svg, (241, 238, 246))
assert st2["removed"] < 2, st2
print("PASS gradient")

# mask: interior gap (enclosed by a white ring) of bg colour must be KEPT, outside island of bg colour REMOVED
from PIL import ImageDraw as _D
from clean_bg import bg_mask
with tempfile.TemporaryDirectory() as td:
    im = Image.new("RGB", (895, 895), (232, 224, 243)); d = _D.Draw(im)
    d.ellipse((200, 200, 700, 700), fill=(255, 255, 255)); d.ellipse((260, 260, 640, 640), fill=(255, 199, 44))
    d.rectangle((420, 420, 480, 480), fill=(232, 224, 243))      # gap inside the character
    png = os.path.join(td, "m.png"); im.save(png)
    m = bg_mask(png)
    svg = ('<svg><path style="fill:#E8E0F3;" d="M800,800h5z"/>'   # outside island -> removed
           '<path style="fill:#E8E0F3;" d="M450,450h5z"/></svg>')  # inside gap -> kept
    out, st = clean(svg, [(232, 224, 243)], m)
    assert st["removed"] == 1 and "M450,450" in out and "M800,800" not in out, (st, out)
print("PASS mask")
