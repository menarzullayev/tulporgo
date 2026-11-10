from fill_holes import process

SQ = "M0,0 L100,0 L100,100 L0,100 Z"
SMALL = "M40,40 L41,40 L41,41 L40,41 Z"         # 1 unit^2 hole
BIG = "M10,10 L60,10 L60,60 L10,60 Z"            # 2500 unit^2 opening (25 %)


def svg(d):
    return f'<g id="sticker-border">\n<path style="fill:#FFFFFF;" d="{d}"/></g>'


def test_small_hole_removed():
    out, k = process(svg(SQ + " " + SMALL))
    assert k == 1 and "M40,40" not in out


def test_big_opening_kept():                     # negative: gap between legs must stay transparent
    out, k = process(svg(SQ + " " + BIG))
    assert k == 0 and "M10,10" in out


def test_zero_length_subpath_does_not_crash():
    # negative: svg/09-13 has a subpath "M502.9,863.3 C502.9,863.3 502.9,863.3 502.9,863.3" inside the
    # outline; svgpathtools.Path.point() raised RuntimeError on it and the whole run stopped
    dot = "M40,40 C40,40 40,40 40,40"
    out, k = process(svg(SQ + " " + SMALL + " " + dot))
    assert k == 2 and "M40,40" not in out and "M0,0" in out


def test_no_border_group():
    assert process("<svg/>")[1] == -1


def test_separate_hole_path_and_degenerate_first_path():
    s = '<g id="sticker-border">\n<path style="fill:#FFFFFF;" d="M5,5 L5,5 Z"/>\n' \
        f'<path style="fill:#FFFFFF;" d="{SQ} {SMALL}"/></g>'
    out, k = process(s)
    assert k == 1 and "M40,40" not in out and SQ.split()[0] in out   # degenerate path draws nothing: left as is
