"""Find and fill small holes in the white sticker border of a raster pose (png/, png_ns/).

Raster twin of fill_holes.py. The Illustrator PNGs were exported before fill_holes existed, so holes in the
border show as dark blobs on a dark chat background (13, 17, 18, 24, 26, 31, 38, 42, 44). A hole is a
transparent component (alpha < THR) that does not touch the image edge and is smaller than MAX_FRAC of
the opaque area; the same 2 % rule as the vector border, so big openings (between the legs in 40, 47) stay.
Filling = the pixels composited over white, on the hole grown by GROW px to cover its anti-aliased rim, but
never onto outside background. Usage: python png_holes.py <dir>   prints holes per file, exit 1 if any.
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage

THR = 128          # below: transparent. 128 (not 250) so a hole joined to the outside only by a
MAX_FRAC = 0.02    # semi-transparent hairline (pose 18) still counts as enclosed
GROW = 3


def hole_mask(alpha, thr=THR, max_frac=MAX_FRAC):
    """Boolean mask of small enclosed transparent components and their count."""
    tr = alpha < thr
    lab, n = ndimage.label(tr)
    if not n:
        return np.zeros_like(tr), 0
    sizes = ndimage.sum(tr, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes < max_frac * (~tr).sum()
    keep[np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))] = False
    keep[0] = False
    return keep[lab], int(keep.sum())


def fill(im, thr=THR, max_frac=MAX_FRAC, grow=GROW):
    """Return (filled RGBA image, holes, hole pixels). Pixels outside the grown holes are untouched."""
    a = np.array(im.convert("RGBA"))
    mask, n = hole_mask(a[..., 3], thr, max_frac)
    if not n:
        return Image.fromarray(a), 0, 0
    m = ndimage.binary_dilation(mask, iterations=grow) & (mask | (a[..., 3] >= thr))
    al = a[..., 3:4] / 255.0
    over = a[..., :3] * al + 255 * (1 - al)
    out = a.copy()
    out[m, :3] = np.round(over[m]).astype(np.uint8)
    out[m, 3] = 255
    return Image.fromarray(out), n, int(mask.sum())


def count(path):
    return hole_mask(np.array(Image.open(path).convert("RGBA"))[..., 3])[1]


if __name__ == "__main__":
    d = sys.argv[1]
    bad = 0
    for f in sorted(os.listdir(d)):
        if f.endswith(".png"):
            k = count(os.path.join(d, f))
            bad += bool(k)
            if k:
                print(f, "holes=%d" % k)
    print(d, "files with holes:", bad)
    sys.exit(1 if bad else 0)
