from build_texts import check


def bot(**kw):
    base = dict(scope="bot", limit=120, uz="Taksi chaqirish", ru="Такси", en="Taxi")
    base.update(kw)
    return base


def test_real_texts_pass():
    from telegram_texts import TEXTS
    built, problems = check(TEXTS)
    assert problems == [], problems
    assert built["bot.start"]["text"]["uz_new"].startswith("Xuş kelibsiz")
    assert set(built["bot.description"]["text"]) == {"uz_new", "uz_latn", "uz_cyrl", "ru", "en"}


def test_over_limit_fails():
    # negative: Cyrillic/new Latin can be longer or equal; any variant over the limit is reported
    _, p = check({"x": bot(limit=10, uz="Yo'lovchi uchun bepul")})
    assert any("x.uz_new" in s for s in p) and any("x.uz_cyrl" in s for s in p)


def test_chat_limit_counts_uz_plus_ru():
    # negative: uz alone fits 255, but uz + ru (what members see) does not
    _, p = check({"c.description": dict(scope="chat", limit=30, uz="Taksi xizmati yangiliklari", ru="Новости такси")})
    assert any("c.description.composed" in s for s in p)


def test_bad_command_name_fails():
    _, p = check({"cmd": bot(command="E'lon")})
    assert any("bad command name" in s for s in p)


def test_long_button_fails():
    _, p = check({"b": bot(buttons=[dict(uz="Ko'p beriladigan savollar ro'yxati", ru="Вопросы", en="FAQ")])})
    assert any(".button.uz_latn" in s for s in p)


def test_more_than_one_accent_fails():
    # negative (decision 39): two animated accents in one message is noise
    _, p = check({"a": bot(uz="Tez orada 🚀 bayram 🎉", ru="Скоро 🚀", en="Soon 🚀")})
    assert any("a.uz: 2 animated accents" in s for s in p)
    _, p = check({"a": bot(uz="Tez orada 🚀 1️⃣ 2️⃣ ✅", ru="Скоро 🚀", en="Soon 🚀")})   # interface icons don't count
    assert not p


def test_repeated_accent_counts_twice():
    _, p = check({"a": bot(uz="🚀 Tez orada 🚀", ru="Скоро", en="Soon")})
    assert any("2 animated accents" in s for s in p)


def test_ascii_quotes_fail():
    # negative: 'quoted' text would turn the closing quote into tutuq belgisi in uz_latn
    _, p = check({"q": bot(uz="'Taksi' tugmasini bosing")})
    assert any("ASCII quotation" in s for s in p)
    _, p = check({"q": bot(uz="«Taksi» tugmasini bosing, o'zingiz tanlang")})
    assert not p
