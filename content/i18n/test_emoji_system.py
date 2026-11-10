"""Decision 39 map: every interface/emotion name resolves to an id from the dedicated packs; no API call when cached."""
import json
import os

import pytest

import emoji_system as es


def no_api(*_a, **_k):
    raise AssertionError("unexpected Bot API call")


@pytest.mark.skipif(not os.path.exists(es.ACCENT_CACHE), reason="accent cache not built")
def test_every_role_resolves_from_the_packs_without_api_calls():
    m = es.build_map(no_api)
    for std in {**es.INTERFACE, **es.EMOTION}:
        assert m.get(std, "").isdigit(), std
    packs = json.load(open(es.PACK_IDS, encoding="utf-8"))
    assert m["👋"] == packs["reactions"]["09-01-salomlashadi"] and m["🚕"] == packs["icons"]["taxi"]


def test_no_reference_to_the_temporary_test_ids():
    # negative: the 15 test emoji are removed from tulporgo_emoji; nothing may point at them any more
    src = open(es.__file__, encoding="utf-8").read()
    assert "test_ids.json" not in src


def test_unknown_name_is_left_out(tmp_path, monkeypatch):
    p = tmp_path / "pack_ids.json"
    p.write_text(json.dumps({"icons": {"taxi": "1"}, "reactions": {}}), encoding="utf-8")
    monkeypatch.setattr(es, "PACK_IDS", str(p))
    monkeypatch.setattr(es, "resolve_accents", lambda call: {})
    assert es.build_map(no_api) == {"🚕": "1"}
