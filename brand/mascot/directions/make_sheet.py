"""Build a numbered contact sheet of the 10 TulporGo mascot directions."""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS = [
    ("01-esport-emblema.png", "Esport emblema"),
    ("02-uchayotgan-minimal.png", "Uchayotgan, minimal"),
    ("03-3d-haydovchi-maskot.png", "3D maskot, haydovchi"),
    ("04-qanot-G-monogramma.png", "Qanot = G harfi"),
    ("05-taksi-chirogi-negativ.png", "Taksi chirog'i, negativ"),
    ("06-samarqand-islimi.png", "Samarqand islimi"),
    ("07-retro-70s-nishon.png", "Retro 70-lar nishoni"),
    ("08-ilova-ikonka.png", "Ilova ikonkasi"),
    ("09-chibi-stiker.png", "Chibi stiker"),
    ("10-taksi-haydovchi.png", "Rulda, taksida"),
]
CELL, PAD, CAP, COLS = 420, 24, 64, 5
rows = (len(ITEMS) + COLS - 1) // COLS
W = COLS * CELL + (COLS + 1) * PAD
H = rows * (CELL + CAP) + (rows + 1) * PAD
sheet = Image.new("RGB", (W, H), "#111214")
draw = ImageDraw.Draw(sheet)


def font(size):
    for f in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


fnum, fcap = font(34), font(24)
for i, (fn, cap) in enumerate(ITEMS):
    r, c = divmod(i, COLS)
    x = PAD + c * (CELL + PAD)
    y = PAD + r * (CELL + CAP + PAD)
    img = Image.open(os.path.join(HERE, fn)).convert("RGB").resize((CELL, CELL), Image.LANCZOS)
    sheet.paste(img, (x, y))
    draw.rounded_rectangle((x + 10, y + 10, x + 66, y + 58), 10, fill="#FFC72C")
    draw.text((x + 38, y + 34), str(i + 1), font=fnum, fill="#111214", anchor="mm")
    draw.text((x + CELL // 2, y + CELL + CAP // 2), cap, font=fcap, fill="#FFFFFF", anchor="mm")

out = os.path.join(HERE, "tulpor-10-yonalish.png")
sheet.save(out, optimize=True)
print(out, sheet.size)
