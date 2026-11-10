from head_rects import adjust


def test_shift_and_grow_stays_centred():
    assert adjust((100, 50, 400), (60, 10, 20)) == (150, 60, 420)


def test_clamped_inside_canvas():                 # negative: a big shift must not leave the canvas
    x, y, s = adjust((400, 400, 450), (300, 300, 0))
    assert x + s <= 895 and y + s <= 895 and x >= 0 and y >= 0
