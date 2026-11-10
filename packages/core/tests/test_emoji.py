from tulporgo_core.emoji import decorate


def test_decorate_wraps_known_and_keeps_unknown():
    m = {"🚕": "111", "1️⃣": "222"}
    out = decorate("1️⃣ Taksi 🚕 va 🙂", m)
    assert '<tg-emoji emoji-id="222">1️⃣</tg-emoji>' in out and '<tg-emoji emoji-id="111">🚕</tg-emoji>' in out
    assert "🙂" in out and out.count("tg-emoji emoji-id") == 2


def test_decorate_is_idempotent():
    # negative: decorating twice must not nest tags
    m = {"🚕": "111"}
    once = decorate("🚕", m)
    assert decorate(once, m) == once


def test_mixed_decorated_and_plain():
    m = {"🚕": "111"}
    out = decorate('<tg-emoji emoji-id="111">🚕</tg-emoji> va 🚕', m)
    assert out.count('<tg-emoji emoji-id="111">🚕</tg-emoji>') == 2


def test_variation_selector_forms():
    m = {"🛡": "9"}
    assert decorate("🛡️ xavfsiz", m).startswith('<tg-emoji emoji-id="9">🛡</tg-emoji>')
