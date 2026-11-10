"""UI texts in 5 languages (decision 16). Each workstream owns one catalog module in tulporgo_core/locales/
(bot.py — W1, userbot.py — W2, payments.py — W4, common.py — shared). A catalog maps key → {"uz", "ru", "en"} where
"uz" is the current Latin source; uz_new / uz_latn / uz_cyrl are derived with the alphabet converter (decision 29:
new alphabet is the default Uzbek), so nobody writes three Uzbek variants by hand.
"""
import importlib
import pkgutil
from functools import lru_cache

from . import locales
from .enums import Lang
from .text.alphabet import convert

DEFAULT = Lang.UZ_NEW


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for m in pkgutil.iter_modules(locales.__path__):
        mod = importlib.import_module(f"{locales.__name__}.{m.name}")
        for k, v in getattr(mod, "TEXTS", {}).items():
            if k in merged:
                raise ValueError(f"duplicate i18n key {k!r} in locales/{m.name}.py")
            merged[k] = v
    return merged


def lang_of(code: str | None) -> Lang:
    """Telegram language_code or a stored choice → Lang. Unknown → Uzbek (new alphabet)."""
    if code in {lg.value for lg in Lang}:
        return Lang(code)
    return {"ru": Lang.RU, "en": Lang.EN, "uz": Lang.UZ_NEW}.get((code or "")[:2], DEFAULT)


def t(key: str, lang: str | Lang | None = None, **kw) -> str:
    entry = catalog().get(key)
    if entry is None:
        return key                                         # visible in UI and caught by tests, never a crash
    lg = lang_of(lang)
    if lg in (Lang.RU, Lang.EN):
        text = entry.get(lg.value) or entry["uz"]
    else:
        text = convert(entry["uz"], lg.value)              # uz_new | uz_latn | uz_cyrl; {placeholders} protected
    return text.format(**kw) if kw else text
