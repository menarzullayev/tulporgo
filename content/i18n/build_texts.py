"""Build all language variants of telegram_texts.TEXTS, check Telegram limits, write JSON + review report.

  bot  items -> uz_new, uz_latn, uz_cyrl (converted from uz), ru, en
  chat items -> uz_new (converted) + ru; the composed text (what members see) is checked against the limit:
                descriptions "uz_new\\nru", messages "uz_new\\n\\nru" (ru goes into an expandable quote)
Checks: length limits, unconverted letters, ASCII quotation marks, command names, button length (<= 24),
at most 1 animated accent emoji per message (decision 39).
Usage: python build_texts.py      exit 1 if any problem.
"""
import json, os, re, sys

from alphabet import convert, leftovers
from emoji_system import MAX_ACCENTS, accents_in

HERE = os.path.dirname(os.path.abspath(__file__))
BUTTON_MAX = 24
CMD = re.compile(r"^[a-z0-9_]{1,32}$")


def variants(item):
    uz = item["uz"]
    if item["scope"] == "bot":
        v = {s: convert(uz, s) for s in ("uz_new", "uz_latn", "uz_cyrl")}
        v.update(ru=item["ru"], en=item["en"])
        return v
    return {"uz_new": convert(uz, "uz_new"), "ru": item["ru"]}


def composed(key, item, v):
    if item["scope"] == "bot":
        return {}
    sep = "\n" if key.endswith(".description") else "\n\n"
    return {"composed": v["uz_new"] + sep + v["ru"]}


def check(texts):
    """Return (built, problems)."""
    built, problems = {}, []
    for key, item in texts.items():
        v = variants(item)
        v.update(composed(key, item, v))
        limited = ["composed"] if item["scope"] == "chat" else list(v)
        for name in limited:
            if len(v[name]) > item["limit"]:
                problems.append(f"{key}.{name}: {len(v[name])} > {item['limit']}")
        for s in ("uz_new", "uz_cyrl"):
            if s in v and leftovers(v[s], s):
                problems.append(f"{key}.{s}: unconverted {leftovers(v[s], s)}")
        for lang in ("uz", "ru", "en"):
            if lang in item and len(accents_in(item[lang])) > MAX_ACCENTS:
                problems.append(f"{key}.{lang}: {len(accents_in(item[lang]))} animated accents > {MAX_ACCENTS} (decision 39)")
        if '"' in item["uz"] or re.search(r"(?<!\w)'|'(?=\s|$)", item["uz"]):
            problems.append(f"{key}: ASCII quotation marks — use «»")
        if "command" in item and not CMD.match(item["command"]):
            problems.append(f"{key}: bad command name {item['command']!r}")
        btns = []
        for b in item.get("buttons", []):
            bv = variants(dict(b, scope=item["scope"], limit=BUTTON_MAX)) if item["scope"] == "bot" else \
                 {"uz_new": convert(b["uz"], "uz_new"), "ru": b["ru"]}
            for name, label in bv.items():
                if len(label) > BUTTON_MAX:
                    problems.append(f"{key}.button.{name}: {label!r} {len(label)} > {BUTTON_MAX}")
            btns.append(dict({k: b[k] for k in b if k not in ("uz", "ru", "en")}, labels=bv))
        built[key] = dict({k: item[k] for k in item if k not in ("uz", "ru", "en", "buttons")}, text=v, buttons=btns)
    return built, problems


def report(built):
    names = {"uz_new": "O'zbek (yangi alifbo)", "uz_latn": "O'zbek (joriy lotin)", "uz_cyrl": "O'zbek (kirill)",
             "ru": "Rus", "en": "Ingliz", "composed": "Ko'rinadigan matn (uz + ru)"}
    out = ["# TulporGo Telegram matnlari — 1-bosqich (QORALAMA)", "",
           "Manba: `content/i18n/telegram_texts.py` (joriy lotin + ru + en). Qolganlari `alphabet.py` bilan o'girilgan.",
           "Tekshiruv: `python build_texts.py` — limitlar, o'girilmagan harflar, buyruq nomlari, tugma uzunligi.", ""]
    for key, b in built.items():
        out += [f"## {key}  (limit {b['limit']})", "", "| Variant | Uzunlik | Matn |", "|---|---|---|"]
        for name, t in b["text"].items():
            out.append(f"| {names[name]} | {len(t)} | {t.replace(chr(10), '<br>').replace('|', '¦')} |")
        for i, btn in enumerate(b["buttons"], 1):
            labels = " · ".join(btn["labels"].values())
            out.append(f"| Tugma {i} ({btn.get('style', 'oddiy')}) | — | {labels} |")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    from telegram_texts import TEXTS
    built, problems = check(TEXTS)
    os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
    with open(os.path.join(HERE, "build", "telegram_texts.json"), "w", encoding="utf-8") as f:
        json.dump(built, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "telegram-texts-review.md"), "w", encoding="utf-8") as f:
        f.write(report(built))
    for p in problems:
        print("PROBLEM", p)
    print(f"{len(built)} items, {len(problems)} problems")
    sys.exit(1 if problems else 0)
