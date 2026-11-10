import copy, gzip, json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "mascot", "poses", "vector"))
from telegram_check import check_tgs, tgs_forbidden  # noqa: E402
from icons_tgs import NAMES, SYMMETRY, build, loop_problems, write  # noqa: E402


@pytest.mark.parametrize("name", NAMES)
def test_icon_meets_telegram_rules(name, tmp_path):
    assert check_tgs(write(name, str(tmp_path))) == []


@pytest.mark.parametrize("name", NAMES)
def test_icon_frame0_is_rest_state_and_loop_is_seamless(name):
    assert loop_problems(build(name), SYMMETRY.get(name, 360)) == []


def test_icon_is_animated_and_vector():
    for n in NAMES:
        d = build(n)
        assert '"a": 1' in json.dumps(d), n                  # every icon moves
        assert all(l["ty"] == 4 for l in d["layers"]), n      # shape layers only (vector)


def test_late_start_fails():
    # negative: the old number pop started at 60 % -> first frame was a shrunken digit
    d = build("n1")
    s = d["layers"][0]["shapes"][0]["it"][-1]["s"]
    s["k"][0]["s"] = [60, 60]
    assert any("[60, 60] -> [100, 100]" in p for p in loop_problems(d))


def test_unfinished_rotation_fails_and_symmetry_is_respected():
    d = build("star")
    assert loop_problems(d, 72) == []
    assert loop_problems(d, 360)                              # negative: 0 -> 72 is not a full turn


def test_first_key_not_at_zero_fails():
    # negative: the old check draw-on started empty on frame 0
    d2 = copy.deepcopy(build("check"))
    tm = next(x for x in d2["layers"][0]["shapes"][0]["it"] if x.get("ty") == "tm")
    tm["e"]["k"] = [{"t": 0, "s": [0], "o": {"x": [0.33], "y": [0]}, "i": {"x": [0.67], "y": [1]}}, {"t": 24, "s": [100]}]
    assert any("[0] -> [100]" in p for p in loop_problems(d2))
