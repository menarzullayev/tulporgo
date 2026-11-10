"""Simplify prep/<n>.png for emoji tracing: smooth + quantise to K colours (magenta background stays pure),
so the trace has far fewer shapes and the TGS fits Telegram's 64 KB limit.
Writes prep_em/<n>.png. Usage: python prep_emoji.py <K> <names...>"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter

V = os.path.dirname(os.path.abspath(__file__))
MED = 9


def simplify(im, k):
    im = im.convert("RGB")
    a = np.asarray(im)
    bg = (a[:, :, 0] == 255) & (a[:, :, 1] == 0) & (a[:, :, 2] == 255)
    sm = im.filter(ImageFilter.MedianFilter(MED))
    q = np.asarray(sm.quantize(k, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")).copy()
    q[bg] = (255, 0, 255)
    # a quantised colour that drifted to magenta-ish inside the art would be deleted later: nudge it
    mag = (q[:, :, 0] > 180) & (q[:, :, 2] > 180) & (q[:, :, 1] < 110) & ~bg
    q[mag] = (230, 120, 230)
    return Image.fromarray(q)


if __name__ == "__main__":
    k = int(sys.argv[1])
    os.makedirs(os.path.join(V, "prep_em"), exist_ok=True)
    for n in sys.argv[2:]:
        simplify(Image.open(os.path.join(V, "prep", n + ".png")), k).save(os.path.join(V, "prep_em", n + ".png"))
