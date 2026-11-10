import pytest
from tulporgo_core.i18n import catalog, lang_of, t


def test_every_key_has_uz_ru_en():
    missing = [k for k, v in catalog().items() if not all(v.get(x) for x in ("uz", "ru", "en"))]
    assert missing == []


def test_derived_uzbek_scripts():
    assert t("common.error", "uz_new").startswith("Xatolik")
    assert "ko'ring" in t("common.error", "uz_latn").replace("ʻ", "'").replace("ʼ", "'")
    assert t("common.error", "uz_cyrl").startswith("Хатолик")


def test_placeholders_survive_cyrillic():
    # negative: {price} must not become {прице}
    assert t("common.price", "uz_cyrl", price="30 000") == "30 000 сўм"
    assert t("common.price", "ru", price="30 000") == "30 000 сум"


def test_language_codes():
    assert lang_of("ru") == "ru" and lang_of("en-US") == "en" and lang_of("uz") == "uz_new"
    assert lang_of(None) == "uz_new" and lang_of("tr") == "uz_new" and lang_of("uz_cyrl") == "uz_cyrl"


def test_unknown_key_is_visible_not_crash():
    assert t("no.such.key", "ru") == "no.such.key"


def test_duplicate_keys_rejected(monkeypatch):
    import types

    from tulporgo_core import i18n
    fake_a = types.SimpleNamespace(TEXTS={"x.k": {"uz": "a", "ru": "a", "en": "a"}})
    fake_b = types.SimpleNamespace(TEXTS={"x.k": {"uz": "b", "ru": "b", "en": "b"}})
    mods = iter([fake_a, fake_b])
    monkeypatch.setattr(i18n.pkgutil, "iter_modules", lambda p: [types.SimpleNamespace(name="a"), types.SimpleNamespace(name="b")])
    monkeypatch.setattr(i18n.importlib, "import_module", lambda n: next(mods))
    i18n.catalog.cache_clear()
    with pytest.raises(ValueError, match="duplicate"):
        i18n.catalog()
    i18n.catalog.cache_clear()


def test_cyrillic_conversion_survives_text_ending_in_y_o_g():
    # regression: a chunk ending in y/o/g (e.g. before a {placeholder} or at the end of a text) crashed or
    # produced a wrong letter because an empty "next char" is `in` every string
    from tulporgo_core.text.alphabet import convert
    assert convert("so'm / oy", "uz_cyrl").endswith("ой")
    assert convert("{n} yo'l bo", "uz_cyrl").endswith("бо")
    assert convert("Reyting {rating}", "uz_cyrl") == "Рейтинг {rating}"
