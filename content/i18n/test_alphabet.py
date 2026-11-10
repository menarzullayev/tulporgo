import pytest

from alphabet import convert, leftovers


@pytest.mark.parametrize("src,new,cyr", [
    ("Qo'shrabot", "Qöşrabot", "Қўшработ"),
    ("O'zbekiston", "Özbekiston", "Ўзбекистон"),
    ("haydovchi", "haydovçi", "ҳайдовчи"),
    ("Samarqand", "Samarqand", "Самарқанд"),
    ("taksi chaqirish", "taksi çaqiriş", "такси чақириш"),
    ("bog'", "boğ", "боғ"),
    ("SHAHAR", "ŞAHAR", "ШАҲАР"),
    ("Shahar", "Şahar", "Шаҳар"),
])
def test_known_words(src, new, cyr):
    assert convert(src, "uz_new") == new
    assert convert(src, "uz_cyrl") == cyr


def test_curly_apostrophes_count_too():
    assert convert("o‘zbek gʻalla", "uz_new") == "özbek ğalla"
    assert convert("o‘zbek", "uz_cyrl") == "ўзбек"


def test_e_at_word_start_and_after_vowel_is_e_reversed():
    assert convert("eshik kelishadi", "uz_cyrl") == "эшик келишади"
    assert convert("shoir", "uz_cyrl") == "шоир"


def test_yo_before_apostrophe_is_y_plus_o_apostrophe():
    # negative: "yo'l" must not become "ё'л" (yo digraph would eat the o of o')
    assert convert("yo'l yo'lovchi", "uz_cyrl") == "йўл йўловчи"
    assert convert("yordam ya'ni yuk yetkazadi", "uz_cyrl") == "ёрдам яъни юк етказади"


def test_tutuq_belgisi_becomes_hard_sign():
    assert convert("e'lon ma'lumot san'at", "uz_cyrl") == "эълон маълумот санъат"


def test_protected_tokens_unchanged():
    # negative: usernames, commands, urls, brand and HTML tags never converted
    s = 'TulporGo: @tulporgobot /qatnovlarim https://t.me/tulporgo <b>shu</b> <tg-emoji emoji-id="5">🚕</tg-emoji>'
    n, c = convert(s, "uz_new"), convert(s, "uz_cyrl")
    for keep in ("TulporGo", "@tulporgobot", "/qatnovlarim", "https://t.me/tulporgo", "<b>", '<tg-emoji emoji-id="5">'):
        assert keep in n and keep in c
    assert "<b>şu</b>" in n and "<b>шу</b>" in c


def test_slash_inside_word_is_not_a_command():
    assert convert("kecha/bugun", "uz_new") == "keça/bugun"


def test_no_dotless_i_ever():
    assert "ı" not in convert("Ishchi bilim qishloq", "uz_new")


def test_current_latin_gets_official_signs():
    assert convert("O'zbekiston bog' e'lon ma'lumot", "uz_latn") == "Oʻzbekiston bogʻ eʼlon maʼlumot"
    # negative: an apostrophe not after a letter is left alone, protected tokens too. Known limit: a closing
    # ASCII quote after a word reads as tutuq belgisi -> texts use «» for quotations (checked in build_texts.py)
    assert convert("'salom' @tulporgobot", "uz_latn") == "'salomʼ @tulporgobot"


def test_suffix_after_protected_word():
    # negative: the apostrophe right after a protected brand word was left as ASCII in uz_latn
    assert convert("Telegram'dan TulporGo'ga", "uz_latn") == "Telegramʼdan TulporGoʼga"
    assert convert("@tulporgobot 'salom'", "uz_latn").startswith("@tulporgobot 'salom")


def test_leftovers_report_misses():
    # negative: leftovers() must flag unconverted text
    assert leftovers("o'z shahar", "uz_new") == ["o'", "sh"]
    assert leftovers("öz şahar", "uz_new") == []
    assert leftovers("salom", "uz_cyrl") != []
    assert leftovers(convert("salom @tulporgobot", "uz_cyrl"), "uz_cyrl") == []
