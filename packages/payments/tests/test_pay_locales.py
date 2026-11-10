import re
import string

import pytest
from tulporgo_core.enums import Lang
from tulporgo_core.i18n import catalog, t
from tulporgo_core.locales.payments import TEXTS

FIELDS = lambda text: {f for _, f, _, _ in string.Formatter().parse(text) if f}  # noqa: E731


def test_keys_are_namespaced_and_in_the_global_catalog():
    assert TEXTS and all(k.startswith("pay.") for k in TEXTS)
    assert set(TEXTS) <= set(catalog())


@pytest.mark.parametrize("key", sorted(TEXTS))
def test_every_key_has_three_languages_with_same_placeholders(key):
    entry = TEXTS[key]
    assert all(entry.get(lg, "").strip() for lg in ("uz", "ru", "en")), key
    assert FIELDS(entry["uz"]) == FIELDS(entry["ru"]) == FIELDS(entry["en"]), key


@pytest.mark.parametrize("key", sorted(TEXTS))
@pytest.mark.parametrize("lang", list(Lang))
def test_every_key_renders_in_all_five_languages(key, lang):
    kw = {f: "X" for f in FIELDS(TEXTS[key]["uz"])}
    out = t(key, lang, **kw)
    assert out and "{" not in out


def test_missing_placeholder_is_a_visible_error_not_silent():
    with pytest.raises(KeyError):
        t("pay.success", "en", plan="Pro")                   # date missing


def test_no_invented_discounts_prices_or_promises():
    blob = " ".join(v for e in TEXTS.values() for v in e.values()).lower()
    for bad in ("chegirma", "скидк", "discount", "% ", "cashback", "kafolat", "guarantee", "bepul sinov"):
        assert bad not in blob, bad
    assert not re.findall(r"\b\d{2,3}[  ]?\d{3}\b", blob)          # no hard-coded prices in texts


def test_price_placeholders_not_mangled_by_the_cyrillic_converter():
    out = t("pay.btn.plan", Lang.UZ_CYRL, plan="Pro", price="59 000")
    assert "59 000" in out
    p2p = t("pay.p2p.instructions", Lang.UZ_CYRL, plan="Pro", months=1, price="59 000", card="8600 0000 0000 0000",
            holder="X", ref="TG000123")
    assert "TG000123" in p2p and "8600 0000 0000 0000" in p2p and "<code>" in p2p


def test_free_period_text_never_asks_to_pay():
    for lang in Lang:
        text = t("pay.status.free", lang, date="31.12.2026")
        assert "31.12.2026" in text
        assert "/obuna" not in text and "pay:" not in text


@pytest.mark.parametrize("key,cyr", [("pay.plan.pro", "Про"), ("pay.plan.basic", "Асосий"), ("pay.plan.business", "Бизнес")])
def test_plan_names_at_end_of_string_survive_cyrillic_conversion(key, cyr):
    # regression: the converter used to crash on / mangle text ending in y, o or g (empty look-ahead char)
    assert t(key, Lang.UZ_CYRL) == cyr
