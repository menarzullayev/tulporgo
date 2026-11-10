"""Side-by-side sheet: original raster vs Illustrator trace preview."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ["01-esport-emblema", "02-uchayotgan-minimal", "03-3d-haydovchi-maskot", "06-samarqand-islimi",
         "07-retro-70s-nishon", "08-ilova-ikonka", "09-chibi-stiker", "10-taksi-haydovchi"]
if len(sys.argv) > 1:
    NAMES = [n for n in NAMES if n[:2] in sys.argv[1:]]
C, P, CAP = 360, 16, 40
W = 4 * (2 * C + P) + 5 * P
rows = (len(NAMES) + 3) // 4
H = rows * (C + CAP + P) + P
sheet = Image.new("RGB", (W, H), "#2a2b2f")
d = ImageDraw.Draw(sheet)
f = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 20)
for i, n in enumerate(NAMES):
    r, c = divmod(i, 4)
    x = P + c * (2 * C + 2 * P)
    y = P + r * (C + CAP + P)
    a = Image.open(os.path.join(HERE, n + ".png")).convert("RGB").resize((C, C), Image.LANCZOS)
    b = Image.open(os.path.join(HERE, "vector", n + "-preview.png")).convert("RGB").resize((C, C), Image.LANCZOS)
    sheet.paste(a, (x, y)); sheet.paste(b, (x + C + 4, y))
    d.text((x + C, y + C + CAP // 2), n[:2] + "  asl  |  vektor", font=f, fill="#FFC72C", anchor="mm")
out = os.path.join(HERE, "vector", "compare.png")
sheet.save(out)
print(out, sheet.size)
