import numpy as np
from PIL import Image

from png_holes import fill, hole_mask

YELLOW = (255, 200, 0, 255)


def sticker(hole=None, opening=None):
    """200x200: transparent outside, white border disc-ish square 20..180, yellow art 60..140."""
    a = np.zeros((200, 200, 4), np.uint8)
    a[20:180, 20:180] = (255, 255, 255, 255)
    a[60:140, 60:140] = YELLOW
    if hole:
        y0, y1, x0, x1 = hole
        a[y0:y1, x0:x1] = 0
    if opening:
        y0, y1, x0, x1 = opening
        a[y0:y1, x0:x1] = 0
    return a


def test_small_hole_filled_white():
    a = sticker(hole=(30, 36, 30, 36))                          # 36 px hole in the border ring
    out, n, px = fill(Image.fromarray(a))
    o = np.array(out)
    assert (n, px) == (1, 36)
    assert (o[30:36, 30:36] == (255, 255, 255, 255)).all()
    assert hole_mask(o[..., 3])[1] == 0


def test_rest_of_image_untouched():
    a = sticker(hole=(30, 36, 30, 36))
    o = np.array(fill(Image.fromarray(a))[0])
    far = np.ones((200, 200), bool)
    far[27:39, 27:39] = False                                   # hole grown by GROW=3
    assert (o[far] == a[far]).all()


def test_big_opening_kept():
    # negative: an opening >= 2 % of the opaque area (gap between legs, poses 40/47) stays transparent
    a = sticker(opening=(150, 175, 70, 130))                    # 1500 px, ~6 % of 25600-1500
    out, n, _ = fill(Image.fromarray(a))
    assert n == 0 and (np.array(out)[150:175, 70:130, 3] == 0).all()


def test_outside_background_not_filled():
    # negative: transparency that reaches the image edge is the background, never a hole
    a = sticker()
    a[0:100, 0:40] = 0                                          # notch from the edge into the border
    out, n, _ = fill(Image.fromarray(a))
    assert n == 0 and (np.array(out)[:, :, 3] == a[:, :, 3]).all()


def test_small_pocket_on_image_edge_not_filled():
    # negative: a small transparent pocket open to the image edge is outside, even though it is < 2 %
    a = np.zeros((200, 200, 4), np.uint8)
    a[:, :] = (255, 255, 255, 255)
    a[0:5, 90:100] = 0
    out, n, _ = fill(Image.fromarray(a))
    assert n == 0 and (np.array(out)[0:5, 90:100, 3] == 0).all()


def test_hole_joined_by_semi_transparent_hairline_is_filled():
    # pose 18: the hole touches the outside only through anti-aliased pixels (alpha 128..249)
    a = sticker(hole=(30, 38, 30, 38))
    a[33, 0:30, 3] = 200
    o = np.array(fill(Image.fromarray(a))[0])
    assert (o[30:38, 30:38, 3] == 255).all()
    assert (o[33, 0:20, 3] == 200).all()                        # outside part of the hairline untouched


def test_grow_never_paints_outside():
    # negative: hole next to the outer edge of a 2 px border; growing must not whiten the background
    a = np.zeros((100, 100, 4), np.uint8)
    a[10:90, 10:90] = (255, 255, 255, 255)
    a[30:70, 30:70] = YELLOW
    a[12:16, 12:16] = 0                                         # hole 2 px from the outside
    o = np.array(fill(Image.fromarray(a))[0])
    assert (o[0:10, :, 3] == 0).all() and (o[:, 0:10, 3] == 0).all()
    assert (o[12:16, 12:16, 3] == 255).all()


def test_rim_is_composited_over_white():
    a = sticker(hole=(30, 36, 30, 36))
    a[29, 30:36] = (0, 0, 0, 100)                               # dark anti-aliased rim pixel above the hole
    o = np.array(fill(Image.fromarray(a))[0])
    assert tuple(o[29, 32]) == (155, 155, 155, 255)             # 0*100/255 + 255*(1-100/255) = 155
