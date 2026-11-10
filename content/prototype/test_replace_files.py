import sys, types

import pytest

sys.modules.setdefault("send_variants", types.SimpleNamespace(call=None, owner_chat=None))
import create_sticker_sets as css


def fake_api(order=None):
    """In-memory sticker set in names.txt order; replaceStickerInSet swaps the file_unique_id."""
    names = order or css.NAMES
    st = [{"file_id": f"id{i}", "file_unique_id": f"u{i}", "emoji": css.emoji_for(n)} for i, n in enumerate(names)]
    log = []

    def call(method, fields=None, files=None):
        log.append((method, fields, files))
        if method == "getStickerSet":
            return {"stickers": [dict(x) for x in st]}
        if method == "replaceStickerInSet":
            i = next(k for k, x in enumerate(st) if x["file_id"] == fields["old_sticker"])
            st[i] = dict(st[i], file_id=f"new{i}", file_unique_id=f"newu{i}")
            return True
        raise AssertionError(method)
    return call, log


def test_only_listed_poses_are_replaced(monkeypatch):
    call, log = fake_api()
    monkeypatch.setattr(css, "call", call)
    a, b = css.NAMES[12], css.NAMES[43]
    assert css.replace_files("static", 1, "tulporgobot", [a, b])
    rep = [x for x in log if x[0] == "replaceStickerInSet"]
    assert [r[1]["old_sticker"] for r in rep] == ["id12", "id43"]
    assert rep[0][2]["f0"].endswith(a + ".webp") and '"format": "static"' in rep[0][1]["sticker"]


def test_video_uses_webm(monkeypatch):
    call, log = fake_api()
    monkeypatch.setattr(css, "call", call)
    assert css.replace_files("video", 1, "tulporgobot", [css.NAMES[0]])
    rep = [x for x in log if x[0] == "replaceStickerInSet"][0]
    assert rep[2]["f0"].endswith(".webm") and '"format": "video"' in rep[1]["sticker"]


def test_wrong_order_refuses_before_any_replace(monkeypatch):
    # negative: if the set's order is not names.txt, position i is not pose i -> replace nothing
    order = list(css.NAMES)
    order[1], order[2] = order[2], order[1]
    call, log = fake_api(order)
    monkeypatch.setattr(css, "call", call)
    with pytest.raises(SystemExit, match="order differs"):
        css.replace_files("static", 1, "tulporgobot", [css.NAMES[12]])
    assert not [x for x in log if x[0] == "replaceStickerInSet"]


def test_unknown_name_refuses(monkeypatch):
    # negative: a typo in a pose name must not silently replace nothing and report success
    call, log = fake_api()
    monkeypatch.setattr(css, "call", call)
    with pytest.raises(SystemExit, match="unknown names"):
        css.replace_files("static", 1, "tulporgobot", ["09-13-soyabon-typo"])
    assert not [x for x in log if x[0] == "replaceStickerInSet"]
