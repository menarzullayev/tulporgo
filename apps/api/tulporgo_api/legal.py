"""Public legal pages (privacy policy §8/§11, `/terms` in the bot): `https://tulporgo.uz/legal/<doc>?lang=uz|ru`,
rendered from `docs/legal/<doc>.<lang>.md` so the repository stays the single source. Raw HTML in the Markdown is
escaped, only the three known documents are served, and the "QORALAMA / ЧЕРНОВИК" banner stays until the lawyer-approved
text replaces the draft (decision 51)."""
import html
import os
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
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


def legal_dir() -> Path:
    env = os.environ.get("TULPORGO_LEGAL_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "docs" / "legal"


@lru_cache(maxsize=32)
def _render(path: Path, mtime: float, doc: str, lang: str) -> str:
    body = _LINK.sub(lambda m: f'href="/legal/{m.group(1)}?lang={m.group(2)}"', _md.render(path.read_text("utf-8")))
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
async def legal_page(doc: str, lang: str = "uz") -> HTMLResponse:
    if doc not in DOCS:
        raise HTTPException(status_code=404)
    lang = lang if lang in LANGS else "uz"
    path = legal_dir() / f"{doc}.{lang}.md"
    if not path.is_file():
        raise HTTPException(status_code=404)
    page = _render(path, path.stat().st_mtime, doc, lang)
    return HTMLResponse(page, headers={"Cache-Control": "public, max-age=300"})
