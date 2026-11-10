import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prep_src import prep, MAG

# near-white bg + white sticker border + BLACK outline + cream body + lavender gap inside the outline
im = Image.new("RGB", (400, 400), (252, 252, 252)); d = ImageDraw.Draw(im)
d.ellipse((70, 70, 330, 330), fill=(255, 255, 255))            # sticker border (to be removed by design)
d.ellipse((96, 96, 304, 304), fill=(17, 18, 20))                # black outline
d.ellipse((104, 104, 296, 296), fill=(250, 244, 238))           # cream body
d.rectangle((190, 190, 210, 210), fill=(232, 224, 243))         # gap inside the body
d.ellipse((20, 20, 60, 60), fill=(255, 199, 44))                # confetti outside, no outline
out, pct = prep(im)
assert out.getpixel((5, 5)) == MAG and out.getpixel((80, 200)) == MAG, "bg and old white border must be painted"
assert out.getpixel((200, 120)) == (250, 244, 238), "cream body behind black outline must stay"
assert out.getpixel((200, 200)) == (232, 224, 243), "gap inside the outline must stay"
assert out.getpixel((40, 40)) == (255, 199, 44), "yellow confetti must stay"
print("PASS prep", round(pct, 1))

# negative: a body with a GAP in its black outline leaks -> interior gets painted (shows why outline matters)
im2 = Image.new("RGB", (400, 400), (252, 252, 252)); d2 = ImageDraw.Draw(im2)
d2.ellipse((96, 96, 304, 304), fill=(17, 18, 20)); d2.ellipse((104, 104, 296, 296), fill=(250, 244, 238))
d2.rectangle((195, 90, 205, 200), fill=(250, 244, 238))
out2, _ = prep(im2)
assert out2.getpixel((200, 200)) == MAG, "broken outline must leak (expected)"
print("PASS negative")


def test_low_threshold_keeps_light_detail():
    # light-grey bg (234) with a near-white flake (245): default thresh 40 eats it, thresh 12 keeps it
    from PIL import Image, ImageDraw
    from prep_src import prep, MAG
    im = Image.new("RGB", (120, 120), (234, 233, 236))
    ImageDraw.Draw(im).ellipse((50, 50, 70, 70), fill=(245, 245, 247))  # PIL thresh = sum of channel diffs: 34
    eaten, _ = prep(im, thresh=40)
    kept, _ = prep(im, thresh=12)
    assert eaten.getpixel((60, 60)) == MAG          # negative: the old setting loses the flake
    assert kept.getpixel((60, 60)) != MAG


def test_overrides_parse(tmp_path):
    from prep_src import overrides
    f = tmp_path / "o.txt"
    f.write_text("# comment\n09-25-x 12\nbad line here\n", encoding="utf-8")
    assert overrides(str(f)) == {"09-25-x": 12}
