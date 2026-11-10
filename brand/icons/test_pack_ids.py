"""pack_ids.py maps the dedicated packs to names and refuses a pack whose size or order differs from the upload."""
import json
import os

import pytest

import pack_ids

HERE = os.path.dirname(os.path.abspath(__file__))


def icons(order=pack_ids.ICONS):
    return [{"emoji": pack_ids.ICON_EMOJI[n] + "️", "custom_emoji_id": f"id-{n}"} for n in order]


def heads(n=None):
    return [{"emoji": "👋", "custom_emoji_id": f"h-{i}"} for i in range(n if n is not None else len(pack_ids.HEADS))]


def test_maps_names_to_ids():
    d = pack_ids.build(icons(), heads())
    assert d["icons"]["taxi"] == "id-taxi" and d["icons"]["n3"] == "id-n3"
    assert d["reactions"][pack_ids.HEADS[0]] == "h-0" and len(d["reactions"]) == 24


def test_wrong_size_refused():
    with pytest.raises(SystemExit):
        pack_ids.build(icons()[:-1], heads())
    with pytest.raises(SystemExit):
        pack_ids.build(icons(), heads(23))


def test_wrong_order_refused():
    swapped = list(pack_ids.ICONS)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    with pytest.raises(SystemExit, match="order"):
        pack_ids.build(icons(swapped), heads())


def test_committed_file_is_complete():
    d = json.load(open(os.path.join(HERE, "pack_ids.json"), encoding="utf-8"))
    assert set(d["icons"]) == set(pack_ids.ICONS) and list(d["reactions"]) == pack_ids.HEADS
    assert all(v.isdigit() for v in [*d["icons"].values(), *d["reactions"].values()])
