"""TulporGo Telegram avatars (decision 31): mark 02 on a different background per chat.

  bot      yellow #FFC72C  + mark 02 in solid black (the yellow body would vanish on yellow)
  channel  black  #111214  + mark 02-dark (yellow body, white wings)
  chat     white  #FFFFFF  + yellow ring + mark 02 (ring chosen 2026-11-10: plain white vanished on light themes)
  drivers  black  #111214  + mark 02-dark + steering-wheel badge
Telegram crops avatars to a circle and shows them down to ~32 px, so the mark is centred inside the circle with a
safe margin and every avatar is previewed at 640/160/48/32 px. Output: out/<name>.png + .jpg (1024 px), preview.png
Usage: python avatars.py
"""
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
MARKS = os.path.join(HERE, "..", "mascot", "directions", "vector")
OUT = os.path.join(HERE, "out")
S = 1024
Y, K, W = (255, 199, 44), (17, 18, 20), (255, 255, 255)
MARK_W = 0.70                      # mark width as a share of the avatar side (fits inside the circle)


def mark(variant):
    name = {"light": "02-uchayotgan-minimal-brand-1024.png", "dark": "02-uchayotgan-minimal-brand-dark-1024.png"}[variant]
    im = Image.open(os.path.join(MARKS, name)).convert("RGBA")
    return im.crop(im.getbbox())


def solid(im, color):
    a = np.array(im)
    a[..., :3] = color
    return Image.fromarray(a)


def badge(d):
    """Steering wheel: yellow disc with black ring, hub and three spokes, drawn 4x and downsampled."""
    big = Image.new("RGBA", (d * 4, d * 4), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    D = d * 4
    g.ellipse([0, 0, D - 1, D - 1], fill=K)                       # black outer ring = separation from the mark
    m = D * 0.07
    g.ellipse([m, m, D - m, D - m], fill=Y)
    c, r = D / 2, D * 0.30
    w = int(D * 0.075)
    g.ellipse([c - r, c - r, c + r, c + r], outline=K, width=w)
    hub = D * 0.075
    g.ellipse([c - hub, c - hub, c + hub, c + hub], fill=K)
    for x0, y0, x1, y1 in ((c - r, c - r * 0.15, c - hub, c - r * 0.15), (c + hub, c - r * 0.15, c + r, c - r * 0.15),
                           (c, c + hub, c, c + r)):
        g.line([x0, y0, x1, y1], fill=K, width=w)
    return big.resize((d, d), Image.LANCZOS)


def compose(bg, m, with_badge=False, ring=None):
    im = Image.new("RGBA", (S, S), bg + (255,))
    if ring:                                                   # visible edge on a white chat list
        g = ImageDraw.Draw(im)
        big = Image.new("L", (S * 4, S * 4), 0)
        ImageDraw.Draw(big).ellipse([0, 0, S * 4 - 1, S * 4 - 1], fill=255)
        t = int(S * 4 * 0.045)
        ImageDraw.Draw(big).ellipse([t, t, S * 4 - 1 - t, S * 4 - 1 - t], fill=0)
        im.paste(Image.new("RGBA", (S, S), ring + (255,)), (0, 0), big.resize((S, S), Image.LANCZOS))
    w = int(S * (MARK_W - (0.06 if ring else 0)))
    h = int(m.height * w / m.width)
    mm = m.resize((w, h), Image.LANCZOS)
    dx, dy = (-int(S * 0.04), -int(S * 0.05)) if with_badge else (0, 0)
    im.alpha_composite(mm, ((S - w) // 2 + dx, (S - h) // 2 - int(S * 0.01) + dy))
    if with_badge:
        d = int(S * 0.26)
        cx = cy = int(S / 2 + S * 0.205)                        # inside the circle crop: |c - centre| + d/2 < S/2
        im.alpha_composite(badge(d), (cx - d // 2, cy - d // 2))
    return im


AVATARS = {
    "bot": lambda: compose(Y, solid(mark("light"), K)),
    "channel": lambda: compose(K, mark("dark")),
    "chat": lambda: compose(W, mark("light"), ring=Y),          # white + yellow ring (chosen 2026-11-10)
    "drivers": lambda: compose(K, mark("dark"), with_badge=True),
}


def circle(im, size):
    im = im.resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(m).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), m.resize((size, size), Image.LANCZOS))
    return out


def preview(images):
    """Rows per avatar: 160 px circle, then 48 and 32 px on Telegram dark and light chat-list backgrounds."""
    rowh, sheet = 200, Image.new("RGBA", (760, 200 * len(images) + 20), (255, 255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.rectangle([380, 0, 760, sheet.height], fill=(23, 33, 43, 255))
    for i, (name, im) in enumerate(images.items()):
        y = 20 + i * rowh
        sheet.alpha_composite(circle(im, 160), (20, y))
        d.text((200, y + 4), name, fill=(17, 18, 20, 255))
        for x0, fg in ((200, (17, 18, 20, 255)), (420, (255, 255, 255, 255))):
            sheet.alpha_composite(circle(im, 48), (x0, y + 30))
            sheet.alpha_composite(circle(im, 32), (x0 + 60, y + 38))
            d.text((x0 + 100, y + 40), "TulporGo", fill=fg)
    return sheet


def main():
    os.makedirs(OUT, exist_ok=True)
    images = {}
    for name, make in AVATARS.items():
        im = make()
        im.save(os.path.join(OUT, name + ".png"), optimize=True)
        im.convert("RGB").save(os.path.join(OUT, name + ".jpg"), quality=95)
        images[name] = im
    preview(images).convert("RGB").save(os.path.join(HERE, "avatars-preview.png"))
    print("avatars:", ", ".join(images), "->", OUT)


if __name__ == "__main__":
    main()
