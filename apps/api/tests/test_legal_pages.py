"""Public legal pages at /legal/<doc>?lang=uz|ru (the bot's /terms link points here)."""
import html
import re
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from tulporgo_api import legal
from tulporgo_api.main import create_app
from tulporgo_core.config import Settings
from tulporgo_core.events import InMemoryBus

DRAFT_BANNER = re.compile(r"QORALAMA|ЧЕРНОВИК")


@pytest.fixture
def client():
    with TestClient(create_app(Settings.model_validate({}), None, InMemoryBus())) as c:
        yield c


@pytest.mark.parametrize("doc", legal.DOCS)
@pytest.mark.parametrize("lang", legal.LANGS)
def test_every_document_in_both_languages(client, doc, lang):
    r = client.get(f"/legal/{doc}", params={"lang": lang})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert f'<html lang="{lang}">' in r.text
    assert not DRAFT_BANNER.search(r.text)                               # decision 68: lawyer-reviewed, no draft banner
    assert ("Tahrir: 2026-11-11" if lang == "uz" else "Редакция от 11.11.2026") in r.text


def test_uzbek_is_the_default_and_unknown_language_falls_back(client):
    assert "Foydalanish shartlari" in client.get("/legal/terms").text
    assert '<html lang="uz">' in client.get("/legal/terms", params={"lang": "de"}).text


def test_links_between_documents_point_to_the_pages(client):
    page = client.get("/legal/terms").text
    assert 'href="/legal/privacy?lang=uz"' in page and ".md\"" not in page


@pytest.mark.parametrize("path", ["/legal/README", "/legal/..%2F..%2Fpyproject", "/legal/terms.uz.md", "/legal/"])
def test_only_the_three_documents_are_served(client, path):
    assert client.get(path).status_code == 404                           # negative: no other files, no traversal


def test_raw_html_in_markdown_is_escaped(client, tmp_path, monkeypatch):
    (tmp_path / "terms.uz.md").write_text("# T\n\n<script>alert(1)</script>\n", encoding="utf-8")
    monkeypatch.setenv("TULPORGO_LEGAL_DIR", str(tmp_path))
    page = client.get("/legal/terms").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_the_bot_terms_link_lands_here():
    from tulporgo_payments.bot import TERMS_URL
    assert urlsplit(TERMS_URL).path == "/legal/terms"


def test_not_part_of_the_api_contract(client):
    assert not any(p.startswith("/legal") for p in client.get("/openapi.json").json()["paths"])


LAWYER_PLACEHOLDER = re.compile(r"\[(yurist|юрист):")


@pytest.mark.parametrize("doc", legal.DOCS)
@pytest.mark.parametrize("lang", legal.LANGS)
def test_no_lawyer_placeholder_is_left(client, doc, lang):
    page = client.get(f"/legal/{doc}", params={"lang": lang}).text
    assert not LAWYER_PLACEHOLDER.search(page)                           # decision 67: all nine questions answered


def test_placeholder_check_catches_a_leftover(client, tmp_path, monkeypatch):
    (tmp_path / "terms.uz.md").write_text("# T\n\nQaytarish: `[yurist: N]` kun.\n", encoding="utf-8")
    monkeypatch.setenv("TULPORGO_LEGAL_DIR", str(tmp_path))
    assert LAWYER_PLACEHOLDER.search(client.get("/legal/terms").text)    # negative: a leftover is caught
    assert LAWYER_PLACEHOLDER.search("[юрист: N]")


@pytest.mark.parametrize(("doc", "lang", "facts"), [
    ("terms", "uz", ["16 yosh", "kamida 7 kun oldin", "axborot vositachisi", "qonunchilikda nazarda tutilgan hollar"]),
    ("terms", "ru", ["16 лет", "не менее чем за 7 дней", "информационный посредник", "кроме случаев, предусмотренных"]),
    ("privacy", "uz", ["Javob muddati — 10 kun", "16 yoshga to'lmagan", "O'zbekistondan tashqarida"]),
    ("privacy", "ru", ["Срок ответа — 10 дней", "младше 16 лет", "за пределами Узбекистана"]),
])
def test_owner_answers_are_in_the_pages(client, doc, lang, facts):
    page = client.get(f"/legal/{doc}", params={"lang": lang}).text
    assert [f for f in facts if f not in page] == []                     # decision 67 values, as published


OWNER_PLACEHOLDER = re.compile(r"\[(ega|владелец):")


def _client(**settings):
    return TestClient(create_app(Settings.model_validate(settings), None, InMemoryBus()))


@pytest.mark.parametrize("lang", legal.LANGS)
def test_operator_details_come_from_the_settings(lang):
    with _client(operator_name="Testov Test Testovich", operator_address="Samarqand viloyati, Qo'shrabot tumani") as c:
        for doc in ("terms", "privacy"):
            page = html.unescape(c.get(f"/legal/{doc}", params={"lang": lang}).text)
            assert "Testov Test Testovich" in page and "Samarqand viloyati, Qo'shrabot tumani" in page
            assert not OWNER_PLACEHOLDER.search(page)                    # decision 67: nothing left to fill


def test_without_the_settings_the_placeholders_stay_visible(client):
    page = client.get("/legal/terms").text                              # negative: a missing setting is not hidden
    assert "[ega: F.I.Sh.]" in page and "[ega: pochta manzili]" in page


def test_operator_details_are_plain_text():
    with _client(operator_name="<script>alert(1)</script> *bold* [x](https://evil.example)",
                 operator_address="`code`\n\n# heading") as c:
        page = c.get("/legal/terms").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "<em>bold</em>" not in page and 'href="https://evil.example"' not in page
    assert "<code>code</code>" not in page and "<h1>heading" not in page
    assert "*bold* [x](https://evil.example)" in html.unescape(page)


def test_draft_banner_check_catches_a_draft(client, tmp_path, monkeypatch):
    (tmp_path / "terms.uz.md").write_text("# T\n\n> **QORALAMA, 2026-11-10.**\n", encoding="utf-8")
    monkeypatch.setenv("TULPORGO_LEGAL_DIR", str(tmp_path))
    assert DRAFT_BANNER.search(client.get("/legal/terms").text)          # negative: a draft would be noticed


@pytest.mark.parametrize(("doc", "lang", "facts"), [
    ("privacy", "uz", ["Guruh xabarlari (73-qaror)", "o'sha guruh a'zosi bo'lgan", "2 soatdan keyin o'chiriladi"]),
    ("privacy", "ru", ["Сообщения в группах (решение 73)", "которые состоят в этой же группе", "удаляется через 2 часа"]),
    ("userbot-consent", "uz", ["TulporGo haydovchilari", "faqat o'qiydi"]),
    ("userbot-consent", "ru", ["для водителей TulporGo", "только читает"]),
])
def test_group_reading_is_disclosed(client, doc, lang, facts):
    page = html.unescape(client.get(f"/legal/{doc}", params={"lang": lang}).text)
    assert [f for f in facts if f not in page] == []                     # decision 73, as published
