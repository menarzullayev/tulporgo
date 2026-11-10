"""Public legal pages at /legal/<doc>?lang=uz|ru (the bot's /terms link points here)."""
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from tulporgo_api import legal
from tulporgo_api.main import create_app
from tulporgo_core.config import Settings
from tulporgo_core.events import InMemoryBus


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
    assert ("QORALAMA" if lang == "uz" else "ЧЕРНОВИК") in r.text          # draft banner until the lawyer approves


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
