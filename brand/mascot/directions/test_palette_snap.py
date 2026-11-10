import os, subprocess, sys, tempfile
from palette_snap import snap, PALETTES

pal, interior = PALETTES["01"]
svg = ('<svg>'
       '<path style="fill:#FCFCFC;" d="M895,0h-5z"/>'      # bg on edge -> dropped
       '<path style="fill:#F8F7F7;" d="M300,300h5z"/>'     # white inside art -> kept as white
       '<path style="fill:#FBBD0E;" d="M10,10h5z"/>'       # yellow -> #FFC72C
       '<path style="fill:#10100E;" d="M20,20h5z"/>'       # black -> #111214
       '</svg>')
out, st = snap(svg, pal, interior)
assert st["shapes"] == 4 and st["dropped"] == 1, st
assert "#FCFCFC" not in out and "fill:#FFFFFF" in out and "#FFC72C" in out and "#111214" in out, out
assert not st["far"]

# negative 1: a colour far from every palette entry (pure blue) is reported
_, st = snap('<svg><path style="fill:#0000FF;" d="M5,5z"/></svg>', pal, interior)
assert st["far"] == {"#0000FF"}, st

# negative 2: CLI fails on an SVG with no inline fills, and on a far colour
here = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as td:
    a = os.path.join(td, "a.svg"); open(a, "w").write('<svg><path class="st0" d="M0,0z"/></svg>')
    b = os.path.join(td, "b.svg"); open(b, "w").write('<svg><path style="fill:#0000FF;" d="M5,5z"/></svg>')
    run = lambda f: subprocess.run([sys.executable, os.path.join(here, "palette_snap.py"), "01", f, f + ".o"],
                                   capture_output=True).returncode
    assert run(a) == 3 and run(b) == 4
print("PASS")

# bg_interior=None drops interior background shapes as well (used for 03's floor shadow)
out, st = snap('<svg><path style="fill:#E4E3E4;" d="M400,400h5z"/><path style="fill:#111214;" d="M1,1z"/></svg>', PALETTES["03"][0], None)
assert st["dropped"] == 1 and "#E4E3E4" not in out, st
print("PASS2")

# drop_below: interior bg shape low in the canvas is dropped, one higher up (eye white) is kept
svg = '<svg><path style="fill:#E4E3E4;" d="M400,860h5z"/><path style="fill:#E4E3E4;" d="M400,200h5z"/></svg>'
out, st = snap(svg, PALETTES["03"][0], "#F4F3F3", 800.0)
assert st["dropped"] == 1 and out.count("#F4F3F3") == 1, (st, out)
print("PASS3")
