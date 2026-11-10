"""Copy the few brand files the Mini App needs into public/ at web sizes.

    uv run --group brand python apps/miniapp/scripts/make_assets.py

Sources are the approved files in brand/ (decisions 24, 31, 38, 39); nothing is redrawn here.
"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "apps" / "miniapp" / "public"
POSES = {                                                   # file -> name used by the app (decision 38 poses)
    "09-01-salomlashadi.png": "hello",
    "09-46-kutyapti.png": "waiting",
    "09-08-bosh-barmoq.png": "thumbs",
    "09-19-rulda.png": "driving",
    "09-34-xafa.png": "sad",
    "09-10-xarita.png": "map",
}


def cut_background(im: Image.Image, tol: int = 10) -> Image.Image:
    """The approved pose PNGs are opaque on a light grey studio background (~#EBEBEF) with a white sticker outline.
    Flood the background from the borders and make it transparent, so the mascot sits on any theme."""
    rgb = np.asarray(im.convert("RGB")).astype(int)
    bg = np.median(np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]), axis=0)
    near = (np.abs(rgb - bg).max(axis=2) <= tol)
    labels, _ = ndimage.label(near)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    outside = np.isin(labels, list(border))
    alpha = ndimage.gaussian_filter((~outside).astype(float), 0.8)         # soft 1 px edge
    out = im.convert("RGBA")
    out.putalpha(Image.fromarray((alpha * 255).astype("uint8")))
    return out


def main() -> None:
    (PUBLIC / "icons").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "mascot").mkdir(parents=True, exist_ok=True)
    for svg in (ROOT / "brand" / "icons" / "svg").glob("*.svg"):
        shutil.copy(svg, PUBLIC / "icons" / svg.name)
    for src, name in POSES.items():
        im = cut_background(Image.open(ROOT / "brand" / "mascot" / "poses" / src))
        im.thumbnail((360, 360), Image.LANCZOS)
        im.save(PUBLIC / "mascot" / f"{name}.webp", "WEBP", quality=88, method=6)
    logo = Image.open(ROOT / "brand" / "telegram" / "out" / "bot.png").convert("RGBA")
    logo.resize((192, 192), Image.LANCZOS).save(PUBLIC / "logo.png", optimize=True)
    logo.resize((64, 64), Image.LANCZOS).save(PUBLIC / "favicon.png", optimize=True)


if __name__ == "__main__":
    main()
