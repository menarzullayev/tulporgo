"""TulporGo interface icons (concept v1): yellow rounded square #FFC72C, black glyph #111214, 24-unit grid.
Made for custom emoji at text size (~20 px): one bold glyph, no thin details.
Writes svg/<name>.svg and png100/<name>.png (100x100, transparent, rendered 4x in headless Edge then downscaled).
Usage: python icons.py
"""
import os, subprocess, tempfile
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
Y, K = "#FFC72C", "#111214"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# name: (alt emoji for Telegram, glyph)
ICONS = {
    "taxi": ("🚕", f'<rect x="9" y="4.6" width="6" height="2.6" rx=".8" fill="{K}"/><path d="M5 15.5V12l2-4h10l2 4v3.5z" fill="{K}"/>'
                   f'<rect x="8" y="9.2" width="8" height="2.4" rx=".6" fill="{Y}"/><circle cx="8" cy="16.5" r="2" fill="{K}"/><circle cx="16" cy="16.5" r="2" fill="{K}"/>'),
    "driver": ("🚘", f'<circle cx="12" cy="12" r="6.6" stroke="{K}" stroke-width="2.4" fill="none"/><circle cx="12" cy="12" r="1.9" fill="{K}"/>'
                     f'<path d="M5.6 11h4.6M13.8 11h4.6M12 13.6v4.8" stroke="{K}" stroke-width="2.2" stroke-linecap="round"/>'),
    "check": ("✅", f'<path d="M6 12.5l4 4 8-9" stroke="{K}" stroke-width="2.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'),
    "pin": ("📍", f'<path d="M12 4.5a5.5 5.5 0 0 1 5.5 5.5c0 4-5.5 9.5-5.5 9.5S6.5 14 6.5 10A5.5 5.5 0 0 1 12 4.5z" fill="{K}"/><circle cx="12" cy="10" r="2.2" fill="{Y}"/>'),
    "shield": ("🛡", f'<path d="M12 4l6.5 2.5v5c0 4-3 7-6.5 8.5C8.5 18.5 5.5 15.5 5.5 11.5v-5z" fill="{K}"/>'
                     f'<path d="M9 12l2.2 2.2L15.5 10" stroke="{Y}" stroke-width="2" fill="none" stroke-linecap="round"/>'),
    "chat": ("💬", f'<path d="M5 6.5h14v9H10l-4 3v-3H5z" fill="{K}"/><circle cx="9" cy="11" r="1.1" fill="{Y}"/><circle cx="12" cy="11" r="1.1" fill="{Y}"/><circle cx="15" cy="11" r="1.1" fill="{Y}"/>'),
    "question": ("❓", f'<path d="M9.2 9.3a2.9 2.9 0 1 1 4.3 2.5c-1 .6-1.5 1.1-1.5 2.4" stroke="{K}" stroke-width="2.5" fill="none" stroke-linecap="round"/><circle cx="12" cy="17.4" r="1.5" fill="{K}"/>'),
    "megaphone": ("📣", f'<path d="M5 10h3l7-4v12l-7-4H5z" fill="{K}"/><path d="M8.5 14.5l1 4h2l-1-4" fill="{K}"/><path d="M17.5 9.5a3.5 3.5 0 0 1 0 5" stroke="{K}" stroke-width="1.8" fill="none" stroke-linecap="round"/>'),
    "card": ("💳", f'<rect x="4.5" y="7" width="15" height="10.5" rx="2" fill="{K}"/><rect x="4.5" y="9.2" width="15" height="2" fill="{Y}"/><rect x="6.8" y="13.6" width="4.5" height="1.6" rx=".8" fill="{Y}"/>'),
    "star": ("⭐", f'<path d="M12 4.6l2.2 4.6 5 .7-3.6 3.5.9 5-4.5-2.4-4.5 2.4.9-5L4.8 9.9l5-.7z" fill="{K}"/>'),
    "clock": ("⏳", f'<circle cx="12" cy="12" r="6.8" fill="{K}"/><path d="M12 8v4.3l2.8 1.8" stroke="{Y}" stroke-width="2" fill="none" stroke-linecap="round"/>'),
    **{f"n{n}": (f"{n}\ufe0f\u20e3", f'<text x="12" y="17.2" text-anchor="middle" font-family="Arial Black,Arial" font-weight="900" font-size="14.5" fill="{K}">{n}</text>')
       for n in (1, 2, 3)},
}


def svg(glyph):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="100" height="100">'
            f'<rect x="1" y="1" width="22" height="22" rx="6" fill="{Y}"/>{glyph}</svg>')


def main():
    os.makedirs(os.path.join(HERE, "svg"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "png100"), exist_ok=True)
    names = list(ICONS)
    for n in names:
        open(os.path.join(HERE, "svg", n + ".svg"), "w", encoding="utf-8").write(svg(ICONS[n][1]))
    tmp = tempfile.mkdtemp()
    page = os.path.join(tmp, "p.html")
    cells = "".join(svg(ICONS[n][1]) for n in names)
    open(page, "w", encoding="utf-8").write(
        '<html><body style="margin:0;background:transparent;line-height:0;white-space:nowrap">' + cells.replace("<svg ", '<svg style="display:inline-block" ') + "</body></html>")
    shot = os.path.join(tmp, "s.png")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=4",
                    "--default-background-color=00000000", f"--window-size={100 * len(names)},100",
                    f"--screenshot={shot}", "file:///" + page.replace("\\", "/")], capture_output=True, check=True)
    im = Image.open(shot).convert("RGBA")
    for i, n in enumerate(names):
        tile = im.crop((i * 400, 0, i * 400 + 400, 400)).resize((100, 100), Image.LANCZOS)
        tile.save(os.path.join(HERE, "png100", n + ".png"), optimize=True)
    print(len(names), "icons ->", os.path.join(HERE, "png100"))


if __name__ == "__main__":
    main()
