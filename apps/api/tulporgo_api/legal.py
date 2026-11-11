"""Public legal pages (privacy policy §8/§11, `/terms` in the bot): `https://tulporgo.uz/legal/<doc>?lang=uz|ru`,
rendered from `docs/legal/<doc>.<lang>.md` so the repository stays the single source. Raw HTML in the Markdown is
escaped and only the three known documents are served. The texts were reviewed by a licensed lawyer and the draft
banner was removed on 2026-11-11 (decisions 51, 68). The operator's name and postal address come from the server's environment
(`TULPORGO_OPERATOR_NAME` / `_ADDRESS`, decision 67), so they never enter the public repository: the Markdown keeps
`[ega: F.I.Sh.]` / `[ega: pochta manzili]` (ru: `[владелец: ФИО]` / `[владелец: почтовый адрес]`) and the page fills
them in."""
import html
import os
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from markdown_it import MarkdownIt

DOCS = ("terms", "privacy", "userbot-consent")
LANGS = ("uz", "ru")
TITLES = {"terms": ("Foydalanish shartlari", "Условия использования"),
          "privacy": ("Maxfiylik siyosati", "Политика конфиденциальности"),
          "userbot-consent": ("Avto-e'lon roziligi", "Согласие на автообъявления")}

router = APIRouter()
_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
_LINK = re.compile(r'href="(terms|privacy|userbot-consent)\.(uz|ru)\.md"')
_OWNER_NAME = re.compile(r"`\[(?:ega: F\.I\.Sh\.|владелец: ФИО)\]`")
_OWNER_ADDRESS = re.compile(r"`\[(?:ega: pochta manzili|владелец: почтовый адрес)\]`")
_MD_PUNCT = re.compile(r"([!-/:-@\[-`{-~])")                # CommonMark: any ASCII punctuation may be backslash-escaped


def _plain(value: str) -> str:
    """A setting as literal Markdown text: one line, every ASCII punctuation escaped (no links, emphasis or code)."""
    return _MD_PUNCT.sub(r"\\\1", " ".join(value.split()))


def fill_owner(text: str, name: str, address: str) -> str:
    """Put the operator's details into the Markdown; an empty setting leaves its placeholder visible."""
    for pattern, value in ((_OWNER_NAME, name), (_OWNER_ADDRESS, address)):
        if value.strip():
            text = pattern.sub(_plain(value).replace("\\", "\\\\"), text)   # template: backslashes doubled
    return text


def legal_dir() -> Path:
    env = os.environ.get("TULPORGO_LEGAL_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "docs" / "legal"


@lru_cache(maxsize=32)
def _render(path: Path, mtime: float, doc: str, lang: str, owner_name: str = "", owner_address: str = "") -> str:
    source = fill_owner(path.read_text("utf-8"), owner_name, owner_address)
    body = _LINK.sub(lambda m: f'href="/legal/{m.group(1)}?lang={m.group(2)}"', _md.render(source))
    other = "ru" if lang == "uz" else "uz"
    nav = " · ".join(f'<a href="/legal/{d}?lang={lang}">{html.escape(TITLES[d][LANGS.index(lang)])}</a>' for d in DOCS)
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(TITLES[doc][LANGS.index(lang)])} — TulporGo</title>
<style>
:root{{--bg:#fff;--fg:#111214;--mut:#5b5f66;--ac:#FFC72C;--line:#e6e6e6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111214;--fg:#fff;--mut:#a9adb4;--line:#2a2c30}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:16px}}
header{{display:flex;justify-content:space-between;align-items:center;gap:12px;border-bottom:3px solid var(--ac);
padding-bottom:8px;margin-bottom:8px}}
header b{{font-size:18px}} a{{color:inherit}} nav{{font-size:14px;color:var(--mut);margin-bottom:16px}}
blockquote{{margin:12px 0;padding:8px 12px;border-left:4px solid var(--ac);background:rgba(255,199,44,.12)}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{border:1px solid var(--line);padding:6px;text-align:left}}
code{{font-size:.92em;white-space:pre-wrap;overflow-wrap:anywhere}}
main{{overflow-wrap:anywhere}} table{{table-layout:fixed}} h1{{font-size:clamp(22px,6vw,32px);line-height:1.25}}
</style></head>
<body><main>
<header><b>TulporGo</b><a href="/legal/{doc}?lang={other}">{other.upper()}</a></header>
<nav>{nav}</nav>
{body}
</main></body></html>"""


@router.get("/legal/{doc}", response_class=HTMLResponse, include_in_schema=False)
async def legal_page(request: Request, doc: str, lang: str = "uz") -> HTMLResponse:
    if doc not in DOCS:
        raise HTTPException(status_code=404)
    lang = lang if lang in LANGS else "uz"
    path = legal_dir() / f"{doc}.{lang}.md"
    if not path.is_file():
        raise HTTPException(status_code=404)
    settings = getattr(request.app.state, "settings", None)
    page = _render(path, path.stat().st_mtime, doc, lang,
                   getattr(settings, "operator_name", ""), getattr(settings, "operator_address", ""))
    return HTMLResponse(page, headers={"Cache-Control": "public, max-age=300"})
