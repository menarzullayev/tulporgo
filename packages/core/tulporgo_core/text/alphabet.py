"""Uzbek script conversion: current Latin (canonical source) -> new Latin alphabet and -> Cyrillic.

Decision 16: texts are written once in the current Latin alphabet and converted automatically, then checked
by hand. New Latin (decision 29, law of 2026-10-21): only o' -> ö, g' -> ğ, sh -> ş, ch -> ç; "ng" unchanged,
never the dotless ı. Brand names, @usernames, /commands, URLs and Telegram HTML tags are never converted.
"""
import re

APOS = "'‘’ʻʼ`"               # ' ‘ ’ ʻ ʼ `
KEEP_WORDS = ("TulporGo", "Telegram", "Mini App", "Click", "Payme", "Premium")
# tokens that must pass through unchanged: tags, entities, urls, @user, /command, brand words
PROTECT = re.compile(r"<[^>]+>|&\w+;|https?://\S+|t\.me/\S+|@\w+|(?<![\w'])/\w+|"
                     + "|".join(re.escape(w) for w in KEEP_WORDS))
A = f"[{APOS}]"

NEW = [(re.compile(f"O{A}"), "Ö"), (re.compile(f"o{A}"), "ö"), (re.compile(f"G{A}"), "Ğ"), (re.compile(f"g{A}"), "ğ"),
       (re.compile("SH"), "Ş"), (re.compile("Sh"), "Ş"), (re.compile("sh"), "ş"),
       (re.compile("CH"), "Ç"), (re.compile("Ch"), "Ç"), (re.compile("ch"), "ç")]

CYR_SINGLE = dict(zip("abdfghijklmnopqrstuvxyz", "абдфгҳижклмнопқрстувхйз"))
VOWELS = "aeiouAEIOUöÖ"


def _split(text):
    """Yield (is_protected, chunk)."""
    pos = 0
    for m in PROTECT.finditer(text):
        if m.start() > pos:
            yield False, text[pos:m.start()]
        yield True, m.group(0)
        pos = m.end()
    if pos < len(text):
        yield False, text[pos:]


def _new(s):
    for rx, rep in NEW:
        s = rx.sub(rep, s)
    return s


def _cyr(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c, nxt = s[i], s[i + 1] if i + 1 < n else ""
        lo, up = c.lower(), c.isupper()
        prev = s[i - 1] if i else ""

        def put(cyr, step):
            nonlocal i
            if up:
                both_up = nxt.isupper() if step > 1 and nxt.isalpha() else False
                cyr = cyr.upper() if both_up or step == 1 else cyr[0].upper() + cyr[1:]
            out.append(cyr)
            i += step

        if lo in "og" and nxt in APOS:                     # o' g'
            put("ў" if lo == "o" else "ғ", 2); continue
        if lo == "s" and nxt.lower() == "h":
            put("ш", 2); continue
        if lo == "c" and nxt.lower() == "h":
            put("ч", 2); continue
        if lo == "y" and nxt.lower() in "aoue" and not (i + 2 < n and s[i + 2] in APOS and nxt.lower() == "o"):
            put({"a": "я", "o": "ё", "u": "ю", "e": "е"}[nxt.lower()], 2); continue
        if lo == "e":                                      # э at word start or after a vowel
            put("э" if (not prev.isalpha() or prev in VOWELS) else "е", 1); continue
        if c in APOS:                                      # tutuq belgisi (ma'lumot, e'lon) -> ъ
            out.append("ъ" if prev.isalpha() else c); i += 1; continue
        if lo in CYR_SINGLE:
            put(CYR_SINGLE[lo], 1); continue
        out.append(c); i += 1
    return "".join(out)


def _latn(s):
    """Current Latin with the official signs: oʻ gʻ (U+02BB) and tutuq belgisi ʼ (U+02BC)."""
    s = re.sub(f"([oOgG]){A}", "\\1\u02bb", s)
    return re.sub(f"(?<=\\w)[{APOS.replace(chr(0x2bb), '')}]", "\u02bc", s)


def convert(text, script):
    """script: 'uz_new', 'uz_latn' or 'uz_cyrl'. Protected tokens are copied unchanged."""
    f = {"uz_new": _new, "uz_latn": _latn, "uz_cyrl": _cyr}[script]
    out = []
    for prot, chunk in _split(text):
        if not prot and script == "uz_latn" and out and out[-1][-1:].isalpha() and chunk[:1] in APOS:
            chunk = "ʼ" + chunk[1:]                  # Telegram'dan: suffix right after a protected word
        out.append(chunk if prot else f(chunk))
    return "".join(out)


def leftovers(text, script):
    """Characters that show a conversion was missed (for the review report)."""
    plain = "".join(c for p, c in _split(text) if not p)
    if script == "uz_new":
        return sorted(set(re.findall(f"[oOgG]{A}|[sScC][hH]|ı", plain)))
    if script == "uz_cyrl":
        return sorted(set(re.findall(r"[A-Za-z]", plain)))
    return []
