import subprocess, sys, os, tempfile
from brandify import brandify

GOOD = '<svg><path style="fill:#FDFDFD;" d="M0"/><path style="fill:#FDBD1B;" d="M1"/><path style="fill:#1B1B1B;" d="M2"/></svg>'
out, st = brandify(GOOD)
assert st["shapes"] == 3 and st["dropped"] == 1 and not st["unknown"], st
assert "#FFC72C" in out and "#111214" in out and "#FDFDFD" not in out

# negative 1: off-palette colour must be reported
_, st = brandify('<svg><path style="fill:#1FA3A3;" d="M0"/></svg>')
assert st["unknown"] == {"#1FA3A3"}, st

# negative 2: SVG without inline fills (the bug that passed silently) must fail the CLI
here = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as td:
    src = os.path.join(td, "cls.svg")
    open(src, "w").write('<svg><style>.st0{fill:#FDBD1B;}</style><path class="st0" d="M0"/></svg>')
    r = subprocess.run([sys.executable, os.path.join(here, "brandify.py"), src, os.path.join(td, "o.svg")])
    assert r.returncode == 3, r.returncode
print("PASS")
