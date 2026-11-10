import json, os
from datetime import datetime, timedelta, timezone

import pytest

import attempt_guard as g

TZ = timezone(timedelta(hours=5))
T0 = datetime(2026, 11, 11, 10, 0, tzinfo=TZ)
SET = "tulporgo_reactions_by_tulporgobot"


@pytest.fixture
def state(tmp_path):
    return str(tmp_path / "create_attempts.json")


def test_first_claim_is_recorded(state):
    assert g.claim(SET, T0, state, 20, False) == "2026-11-11T10:00:00+05:00"
    assert json.load(open(state))[SET] == ["2026-11-11T10:00:00+05:00"]
    assert not os.path.exists(state + ".lock")


def test_second_claim_inside_cooldown_is_refused(state):
    # negative: the scheduled task at 10:00 and a backup run at 10:15 must not both call the API
    g.claim(SET, T0, state, 20, False)
    with pytest.raises(g.Refused, match="next allowed after 2026-11-12T06:00"):
        g.claim(SET, T0 + timedelta(minutes=15), state, 20, False)
    assert len(json.load(open(state))[SET]) == 1  # refused attempt is not recorded
    assert not os.path.exists(state + ".lock")


def test_real_history_blocks_today_and_allows_tomorrow_10(state):
    # seed = last real attempt (MUAMMOLAR #26); the scheduled 2026-11-11 10:00 run must pass
    json.dump({SET: ["2026-11-10T04:08:00+05:00"]}, open(state, "w"))
    with pytest.raises(g.Refused):
        g.claim(SET, datetime(2026, 11, 10, 12, 0, tzinfo=TZ), state, 20, False)
    g.claim(SET, T0, state, 20, False)


def test_after_cooldown_allowed_and_sets_independent(state):
    g.claim(SET, T0, state, 20, False)
    g.claim("other_by_tulporgobot", T0, state, 20, False)
    g.claim(SET, T0 + timedelta(hours=20), state, 20, False)
    assert len(json.load(open(state))[SET]) == 2


def test_force_overrides_cooldown(state):
    g.claim(SET, T0, state, 20, False)
    g.claim(SET, T0 + timedelta(minutes=1), state, 20, True)


def test_corrupt_state_fails_closed(state):
    # negative: an unreadable history must not be treated as "no attempts yet"
    open(state, "w").write("{not json")
    with pytest.raises(g.Refused, match="unreadable"):
        g.claim(SET, T0, state, 20, False)
    open(state, "w").write("[]")
    with pytest.raises(g.Refused, match="unreadable"):
        g.claim(SET, T0, state, 20, False)


def test_held_lock_refuses_even_with_force(state):
    # negative: a concurrent runner holds the lock
    open(state + ".lock", "w").close()
    with pytest.raises(g.Refused, match="holds"):
        g.claim(SET, T0, state, 20, True)
    assert os.path.exists(state + ".lock")  # someone else's lock is left alone


def test_stale_lock_is_cleared(state):
    lock = state + ".lock"
    open(lock, "w").close()
    old = os.path.getmtime(lock) - g.STALE_LOCK_S - 5
    os.utime(lock, (old, old))
    g.claim(SET, T0, state, 20, False)


def test_script_refuses_before_any_api_call():
    # negative, end to end: create_sticker_sets.make() must stop before createNewStickerSet
    import sys, types
    sys.modules.setdefault("send_variants", types.SimpleNamespace(call=None, owner_chat=None))
    import create_sticker_sets as css
    sent = []
    css.call = lambda method, *a, **k: sent.append(method) or (_ for _ in ()).throw(SystemExit("STICKERSET_INVALID"))
    orig = g.claim
    g.claim = lambda name: (_ for _ in ()).throw(g.Refused("test"))
    try:
        with pytest.raises(SystemExit, match="not sent"):
            css.make("reactions", 1, "tulporgobot")
    finally:
        g.claim = orig
    assert sent == ["getStickerSet"]
