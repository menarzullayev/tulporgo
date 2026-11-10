import json
import re
from pathlib import Path

import pytest
from tulporgo_api import export_i18n
from tulporgo_core import i18n
from tulporgo_core.enums import Lang
from tulporgo_core.locales import api as api_locale

ROOT = Path(__file__).resolve().parents[3]
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# error codes raised by core services that the Mini App can never trigger (admin/complaint/billing internals)
SERVER_ONLY = {"admin_only", "cannot_block_self", "complaint_closed", "complaint_too_short", "documents_missing",
               "payment_closed", "bad_months", "driver_only"}


def test_no_duplicate_keys_in_the_api_catalog():
    keys = [f"api.{k}" for k, *_ in api_locale._ROWS]
    assert len(keys) == len(set(keys))


def test_every_text_exists_in_every_language_with_the_same_placeholders():
    for key, entry in api_locale.TEXTS.items():
        assert set(entry) == {"uz", "ru", "en"}, key
        assert all(v.strip() for v in entry.values()), key
        assert {frozenset(PLACEHOLDER.findall(v)) for v in entry.values()} == {frozenset(PLACEHOLDER.findall(entry["uz"]))}, key


def test_uzbek_source_uses_plain_apostrophes():
    for key, entry in api_locale.TEXTS.items():
        assert not re.search("[ʻʼ‘’`]", entry["uz"]), key


def test_uzbek_source_has_no_latin_technical_tokens_that_the_converter_would_mangle():
    """JPEG / FloodWait / "30 A 123 BC" turn into nonsense in the Cyrillic variant, so they must come in through
    {placeholders} (protected) or be left out of the texts."""
    from tulporgo_core.text.alphabet import PROTECT
    for key, entry in api_locale.TEXTS.items():
        plain = PROTECT.sub("", entry["uz"])
        assert not re.search(r"\b[A-Z]{2,}\b|[A-Za-z]+_[A-Za-z]+|\b[A-Z][a-z]+[A-Z]\w*\b", plain), key


def test_the_technical_token_check_catches_bad_texts():
    from tulporgo_core.text.alphabet import PROTECT
    bad = re.compile(r"\b[A-Z]{2,}\b|[A-Za-z]+_[A-Za-z]+|\b[A-Z][a-z]+[A-Z]\w*\b")
    for text in ("Fayl JPEG bo'lsin", "xato PEER_FLOOD", "FloodWait kuting"):
        assert bad.search(PROTECT.sub("", text)), text
    assert not bad.search(PROTECT.sub("", "TulporGo {example} 8 MB".replace("MB", "mb")))


def test_every_error_code_the_api_can_return_has_a_text():
    code_re = re.compile(r'(?:Forbidden|Invalid|Conflict|NotFound|DomainError|TooLarge|NotConfigured|UploadFailed)\("([a-z_]+)"')
    sources = list((ROOT / "packages" / "core" / "tulporgo_core" / "services").glob("*.py"))
    sources += list((ROOT / "apps" / "api" / "tulporgo_api").rglob("*.py"))
    codes = {c for f in sources for c in code_re.findall(f.read_text(encoding="utf-8"))} - SERVER_ONLY
    missing = sorted(c for c in codes if f"api.err.{c}" not in i18n.catalog())
    assert not missing, f"no api.err.* text for: {missing}"


def test_missing_error_text_would_be_caught(monkeypatch):
    """Negative control for the check above: a key that is absent is reported by `t` as the key itself."""
    assert i18n.t("api.err.definitely_not_a_code", "ru") == "api.err.definitely_not_a_code"


def test_export_covers_all_five_languages_and_matches_t():
    built = export_i18n.build()
    assert set(built) == {lg.value for lg in Lang}
    assert len({frozenset(d) for d in built.values()}) == 1                       # identical key sets
    assert built["ru"]["home.title"] == "Куда поедем?" and built["en"]["home.title"] == "Where to?"
    assert built["uz_latn"]["home.title"] == i18n.t("api.home.title", "uz_latn")
    assert built["uz_new"]["home.title"] != built["uz_cyrl"]["home.title"]
    assert "{n}" in built["uz_cyrl"]["home.offers_count"]                          # placeholders survive conversion


def test_committed_dictionaries_are_up_to_date():
    stale = []
    for lang, texts in export_i18n.build().items():
        path = ROOT / "apps" / "miniapp" / "src" / "i18n" / f"{lang}.json"
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != texts:
            stale.append(lang)
    assert not stale, f"run `npm run i18n` in apps/miniapp ({stale})"


def test_check_mode_detects_stale_files(tmp_path, monkeypatch):
    monkeypatch.setattr(export_i18n, "DEFAULT_OUT", tmp_path)
    assert export_i18n.main(["--check"]) == 1                                      # nothing written yet
    assert export_i18n.main([]) == 0
    assert export_i18n.main(["--check"]) == 0
    (tmp_path / "ru.json").write_text("{}", encoding="utf-8")
    assert export_i18n.main(["--check"]) == 1


@pytest.mark.parametrize("lang", ["uz_new", "uz_latn", "uz_cyrl", "ru", "en"])
def test_exported_json_has_no_untranslated_key_names(lang):
    texts = export_i18n.build()[lang]
    assert all(v != f"api.{k}" for k, v in texts.items())
