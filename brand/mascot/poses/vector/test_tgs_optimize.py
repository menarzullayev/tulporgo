import json
import pytest
from tgs_optimize import optimize, encode


def path(x):
    return {"ty": "sh", "ks": {"k": {"c": True, "i": [[0.4, 0.4]], "o": [[0.4, 0.4]], "v": [[x + 0.4, 10.6]]}, "a": 0}}


def grp(color, x, tr=None):
    t = tr or {"ty": "tr", "a": {"k": [0, 0]}, "p": {"k": [0, 0]}, "s": {"k": [100, 100]}, "r": {"k": 0}}
    return {"ty": "gr", "it": [path(x), {"ty": "fl", "c": {"k": color, "a": 0}, "o": {"k": 100}}, t]}


def doc(groups):
    return {"layers": [{"ty": 4, "shapes": groups}]}


def test_colours_survive_integer_rounding():      # regression: 0.988 must not become 1
    d = optimize(doc([grp([0.988, 0.89, 0.427, 1], 1), grp([1, 1, 1, 1], 2)]), 0)
    assert d["layers"][0]["shapes"][0]["it"][-2]["c"]["k"] == [0.988, 0.89, 0.427, 1]


def test_same_colour_merged_border_kept_last():
    Y, B, W = [1, 0.8, 0, 1], [0, 0, 0, 1], [1, 1, 1, 1]
    d = optimize(doc([grp(Y, 1), grp(B, 2), grp(Y, 3), grp(W, 4)]), 1)
    g = d["layers"][0]["shapes"]
    assert len(g) == 3                                   # Y merged, B, border
    assert sum(1 for x in g[0]["it"] if x["ty"] == "sh") == 2
    assert g[-1]["it"][-2]["c"]["k"] == W                # white border still painted last (at the back)


def test_non_identity_transform_refused():            # negative: merging would move shapes
    bad = {"ty": "tr", "a": {"k": [0, 0]}, "p": {"k": [5, 0]}, "s": {"k": [100, 100]}, "r": {"k": 0}}
    with pytest.raises(ValueError):
        optimize(doc([grp([1, 0, 0, 1], 1, bad), grp([1, 1, 1, 1], 2)]), 1)


def test_encode_is_gzip():
    assert encode({"a": 1})[:2] == b"\x1f\x8b"
