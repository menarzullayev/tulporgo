"""Generate the original TulporGo mascot (3/4 head, feather-mane crescent) as SVG.

Usage: python gen_tulpor.py <out.svg> [bg]
Everything is constructed here from geometry; no traced artwork.
"""
import math, sys

INK = '#111214'
Y, Y2, Y3, YH = '#FFC72C', '#E0A100', '#B87F00', '#FFE08A'
DARK, DARK2 = '#2A2C31', '#1A1B1F'


def feather(cx, cy, ang, r0, r1, w, sweep):
    """Curved tapered feather: base on radius r0, tip on radius r1, bent backwards by `sweep` degrees."""
    a0 = math.radians(ang)
    a1 = math.radians(ang + sweep)
    bx, by = cx + r0 * math.cos(a0), cy + r0 * math.sin(a0)
    tx, ty = cx + r1 * math.cos(a1), cy + r1 * math.sin(a1)
    # perpendicular at base
    nx, ny = -math.sin(a0), math.cos(a0)
    b1 = (bx + nx * w / 2, by + ny * w / 2)
    b2 = (bx - nx * w / 2, by - ny * w / 2)
    am = math.radians(ang + sweep * 0.55)
    rm = (r0 + r1) / 2
    mx, my = cx + rm * math.cos(am), cy + rm * math.sin(am)
    c1 = (mx + nx * w * 0.55, my + ny * w * 0.55)
    c2 = (mx - nx * w * 0.35, my - ny * w * 0.35)
    f = lambda p: f'{p[0]:.1f} {p[1]:.1f}'
    return f'M{f(b1)} Q{f(c1)} {tx:.1f} {ty:.1f} Q{f(c2)} {f(b2)} Z'


def build(bg='#FFFFFF'):
    cx, cy = 500, 520
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000">',
           f'<rect width="1000" height="1000" fill="{bg}"/>']
    # feather-mane crescent around the back of the head (angles: 0 = right, 90 = down)
    feathers = []
    spec = [(-118, 360, 0.0), (-138, 410, 1), (-158, 430, 0), (178, 440, 1), (154, 430, 0), (130, 400, 1), (108, 350, 0)]
    for i, (ang, r1, alt) in enumerate(spec):
        feathers.append((feather(cx, cy, ang, 190, r1, 120, -16), Y if alt == 0 else Y2))
    out.append(f'<g stroke="{INK}" stroke-width="22" stroke-linejoin="round">')
    for d, col in feathers:
        out.append(f'<path d="{d}" fill="{col}"/>')
    out.append('</g>')
    # feather highlight veins
    for ang, r1, alt in spec:
        a = math.radians(ang - 6)
        x0, y0 = cx + 250 * math.cos(a), cy + 250 * math.sin(a)
        a2 = math.radians(ang - 12)
        x1, y1 = cx + (r1 - 40) * math.cos(a2), cy + (r1 - 40) * math.sin(a2)
        out.append(f'<path d="M{x0:.1f} {y0:.1f} L{x1:.1f} {y1:.1f}" stroke="{YH}" stroke-width="10" stroke-linecap="round" opacity="0.85"/>')

    # neck + head silhouette (3/4 view facing right)
    head = ('M455 255 C 520 225, 600 235, 640 285 '      # skull top
            'C 700 360, 760 470, 805 545 '                # nose bridge
            'C 840 575, 868 610, 860 652 '                # muzzle front
            'C 852 700, 810 725, 760 722 '                # muzzle bottom
            'C 730 720, 705 712, 690 702 '                # upper lip to mouth corner
            'C 690 735, 668 765, 628 772 '                # chin
            'C 600 776, 580 770, 562 760 '                # under jaw
            'C 548 810, 560 870, 610 925 '                # throat to neck cut
            'L 470 890 L 360 930 '                        # angular neck cut
            'C 330 820, 325 700, 345 590 '                # back of neck
            'C 360 430, 395 300, 455 255 Z')
    out.append(f'<g stroke="{INK}" stroke-width="22" stroke-linejoin="round">')
    # ears
    out.append(f'<path d="M430 300 L 392 120 C 440 160, 480 205, 500 250 Z" fill="{Y2}"/>')
    out.append(f'<path d="M585 250 C 600 190, 630 150, 668 122 C 676 180, 668 240, 645 292 Z" fill="{Y}"/>')
    out.append(f'<path d="{head}" fill="{Y}"/>')
    out.append('</g>')
    # inner ears
    out.append(f'<path d="M438 270 L 412 165 C 442 196, 466 226, 478 254 Z" fill="{Y3}"/>')
    out.append(f'<path d="M604 252 C 616 210, 636 180, 658 160 C 660 200, 654 238, 640 270 Z" fill="{Y3}"/>')
    # far-side shading: back of neck and under jaw
    out.append(f'<path d="M345 590 C 325 700, 330 820, 360 922 L 430 896 C 405 800, 400 700, 420 600 C 432 520, 450 450, 480 400 C 430 420, 370 480, 345 590 Z" fill="{Y2}"/>')
    out.append(f'<path d="M562 760 C 548 810, 560 870, 604 918 L 540 896 C 520 850, 515 800, 530 755 Z" fill="{Y2}"/>')
    # jaw: soft volume only (no ink arc)
    out.append(f'<path d="M482 660 C 525 628, 592 626, 640 664 C 660 686, 662 714, 650 735 C 620 760, 590 768, 562 760 C 528 738, 498 704, 482 660 Z" fill="{Y2}"/>')
    out.append(f'<path d="M482 660 C 525 628, 592 626, 640 664 C 600 646, 540 646, 492 672 Z" fill="{Y3}"/>')
    # muzzle lighter tone
    out.append(f'<path d="M760 520 C 800 560, 865 600, 860 652 C 852 700, 810 725, 760 722 C 730 720, 705 712, 690 702 C 712 650, 735 580, 760 520 Z" fill="#FFD766"/>')
    # nose-bridge highlight
    out.append(f'<path d="M630 300 C 680 360, 735 450, 778 530 L 755 545 C 712 470, 660 385, 612 320 Z" fill="{YH}"/>')
    # nostril (curl) and mouth
    out.append(f'<path d="M805 610 C 828 596, 852 610, 850 636 C 838 624, 818 622, 808 634 C 800 626, 800 616, 805 610 Z" fill="{INK}"/>')
    out.append(f'<path d="M690 702 C 728 700, 770 708, 812 694 C 790 712, 750 720, 700 716 Z" fill="{INK}"/>')
    # forelock (dark, spiky) between the ears
    out.append(f'<path d="M470 262 C 500 230, 540 220, 575 232 L 548 250 C 580 262, 605 290, 612 330 L 580 312 C 590 345, 588 375, 575 400 C 560 360, 535 330, 500 315 L 512 300 C 490 290, 470 280, 455 280 Z" fill="{DARK}" stroke="{INK}" stroke-width="12" stroke-linejoin="round"/>')
    # near eye: top edge slopes DOWN toward the nose = determined
    out.append(f'<path d="M540 448 L 668 478 C 660 514, 628 532, 594 526 C 562 520, 542 494, 540 448 Z" fill="#FFFFFF" stroke="{INK}" stroke-width="12" stroke-linejoin="round"/>')
    out.append(f'<circle cx="612" cy="490" r="21" fill="{INK}"/>')
    out.append(f'<circle cx="620" cy="482" r="7" fill="#FFFFFF"/>')
    out.append(f'<path d="M506 420 C 560 400, 636 418, 698 462 C 640 440, 580 432, 520 436 Z" fill="{INK}"/>')
    # far eye: smaller, same slope, partly behind the nose bridge
    out.append(f'<path d="M716 470 L 758 482 C 754 500, 742 508, 728 504 C 718 500, 714 488, 716 470 Z" fill="#FFFFFF" stroke="{INK}" stroke-width="10" stroke-linejoin="round"/>')
    out.append(f'<circle cx="738" cy="488" r="8" fill="{INK}"/>')
    out.append(f'<path d="M700 452 C 728 448, 756 458, 776 478 C 752 466, 728 462, 704 464 Z" fill="{INK}"/>')
    out.append('</svg>')
    return '\n'.join(out)


if __name__ == '__main__':
    open(sys.argv[1], 'w', encoding='utf-8').write(build(sys.argv[2] if len(sys.argv) > 2 else '#FFFFFF'))
