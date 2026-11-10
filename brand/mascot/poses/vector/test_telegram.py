import os
from PIL import Image
from telegram_check import check_image, check_video
from telegram_export import fit, hop_frames, encode_webm


def test_good_sticker_passes(tmp_path):
    p = tmp_path / "s.webp"
    fit(Image.new("RGBA", (300, 200), (255, 200, 0, 255)), 512).save(p, "WEBP")
    assert check_image(str(p), 512, 512) == []


def test_wrong_size_sticker_fails(tmp_path):      # negative
    p = tmp_path / "s.png"
    Image.new("RGBA", (600, 400), (0, 0, 0, 0)).save(p)
    assert any(x.startswith("size") for x in check_image(str(p), 512, 512))


def test_opaque_background_fails(tmp_path):       # negative
    p = tmp_path / "e.png"
    Image.new("RGBA", (100, 100), (255, 255, 255, 255)).save(p)
    assert "opaque corner" in check_image(str(p), 100, 512, exact=True)


def test_border_hole_fails_and_export_fill_passes(tmp_path):
    # negative: a sticker with a hole in its white border is rejected; after png_holes.fill it passes
    import numpy as np
    from png_holes import fill
    a = np.zeros((512, 512, 4), np.uint8)
    a[40:472, 40:472] = (255, 255, 255, 255)
    a[150:362, 150:362] = (255, 200, 0, 255)
    a[60:70, 60:70] = 0
    bad = tmp_path / "bad.webp"
    Image.fromarray(a).save(bad, "WEBP", quality=90)
    assert "1 border holes" in check_image(str(bad), 512, 512, holes=True)
    assert check_image(str(bad), 512, 512) == []                 # the check is opt-in
    good = tmp_path / "good.webp"
    fill(Image.fromarray(a))[0].save(good, "WEBP", quality=90)
    assert check_image(str(good), 512, 512, holes=True) == []


def test_video_roundtrip_and_limits(tmp_path):
    p = str(tmp_path / "v.webm")
    im = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    im.paste((255, 200, 0, 255), (100, 100, 300, 300))
    assert encode_webm(hop_frames(im, 512), p, 256) is not None
    assert check_video(p, 512, 256) == []
    assert any("KB" in x for x in check_video(p, 512, 0))        # negative: size limit is enforced
    assert any(x.startswith("size") for x in check_video(p, 100, 256, exact=True))  # negative


def _tgs(tmp_path, name, layers=None, **root):
    import gzip, json
    d = {"tgs": 1, "w": 512, "h": 512, "fr": 60, "ip": 0, "op": 180, "assets": [],
         "layers": layers if layers is not None else [{"ty": 4, "sr": 1, "shapes": []}]}
    d.update(root)
    p = tmp_path / name
    p.write_bytes(gzip.compress(json.dumps(d).encode()))
    return str(p)


def test_tgs_forbidden_features_each_caught(tmp_path):
    # negative: every AE feature Telegram forbids must be reported (core.telegram.org/stickers)
    from telegram_check import check_tgs
    cases = {
        "text layer": [{"ty": 5}], "solid layer": [{"ty": 1}], "image layer": [{"ty": 2}],
        "mask": [{"ty": 4, "masksProperties": [{"mode": "a"}]}], "layer effect": [{"ty": 4, "ef": [{"ty": 5}]}],
        "time remapping": [{"ty": 4, "tm": {"a": 0, "k": 0}}], "time stretching": [{"ty": 4, "sr": 2}],
        "auto-orient": [{"ty": 4, "ao": 1}], "3D layer": [{"ty": 4, "ddd": 1}],
        "merge paths": [{"ty": 4, "shapes": [{"ty": "gr", "it": [{"ty": "mm"}]}]}],
        "star shape": [{"ty": 4, "shapes": [{"ty": "sr"}]}], "gradient stroke": [{"ty": 4, "shapes": [{"ty": "gs"}]}],
        "repeater": [{"ty": 4, "shapes": [{"ty": "gr", "it": [{"ty": "gr", "it": [{"ty": "rp"}]}]}]}],
        "expression": [{"ty": 4, "ks": {"p": {"a": 0, "k": [0, 0], "x": "wiggle(2,5)"}}}],
    }
    for feature, layers in cases.items():
        assert f"forbidden: {feature}" in check_tgs(_tgs(tmp_path, feature.replace(" ", "_") + ".tgs", layers)), feature
    assert "forbidden: image asset" in check_tgs(_tgs(tmp_path, "img.tgs", assets=[{"id": "i", "p": "a.png", "u": ""}]))


def test_tgs_clean_file_and_precomp_pass(tmp_path):
    from telegram_check import check_tgs
    ok = _tgs(tmp_path, "ok.tgs", [{"ty": 4, "sr": 1, "shapes": [{"ty": "gr", "it": [{"ty": "sh"}, {"ty": "fl"}, {"ty": "tm"}]}]}],
              assets=[{"id": "comp", "layers": [{"ty": 4}]}])
    assert check_tgs(ok) == []      # trim paths ("tm" shape) and precomp assets are allowed
    bad = _tgs(tmp_path, "pre.tgs", assets=[{"id": "comp", "layers": [{"ty": 5}]}])
    assert "forbidden: text layer" in check_tgs(bad)   # negative: forbidden layer hidden inside a precomp


def test_tgs_limits(tmp_path):
    import gzip, json
    from telegram_check import check_tgs
    good = tmp_path / "g.tgs"
    good.write_bytes(gzip.compress(json.dumps({"tgs": 1, "w": 512, "h": 512, "fr": 60, "ip": 0, "op": 60}).encode()))
    assert check_tgs(str(good)) == []
    bad = tmp_path / "b.tgs"                      # negative: wrong canvas, 30 fps, 5 s, no tgs flag
    bad.write_bytes(gzip.compress(json.dumps({"w": 100, "h": 100, "fr": 30, "ip": 0, "op": 150}).encode()))
    pr = check_tgs(str(bad))
    assert {"canvas 100x100", "fps 30", "duration", "no tgs flag"} <= set(pr)
