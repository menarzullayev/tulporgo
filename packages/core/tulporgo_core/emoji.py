"""Decision 39: standard emoji placeholders in texts → TulporGo custom emoji (icons, tulpor head, ≤1 animated accent).
The id map is built by content/i18n (emoji_system.py → build/emoji_map.json); custom emoji only render in messages
(HTML parse mode), never in profile/description fields."""
import json
import re
from functools import lru_cache
from pathlib import Path

DEFAULT_MAP = Path(__file__).resolve().parents[3] / "content" / "i18n" / "build" / "emoji_map.json"


@lru_cache(maxsize=4)
def load(path: str | None = None) -> dict[str, str]:
    p = Path(path) if path else DEFAULT_MAP
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


TAG = re.compile(r"(<tg-emoji[^>]*>.*?</tg-emoji>)", re.S)


def decorate(html: str, mapping: dict[str, str] | None = None) -> str:
    """Wrap known emoji in <tg-emoji>; unknown emoji stay as they are (old apps see the plain emoji anyway).
    Text already inside a <tg-emoji> tag is left alone, so decorating twice is a no-op."""
    m = load() if mapping is None else mapping
    if not m:
        return html
    forms = sorted({f: std for std in m for f in {std, std.replace("️", ""), std + "️"}
                    if f and not f.isascii()}.items(), key=lambda kv: -len(kv[0]))
    rx = re.compile("|".join(re.escape(f) for f, _ in forms))
    lookup = dict(forms)
    parts = TAG.split(html)
    for i in range(0, len(parts), 2):                    # even parts are outside existing tags
        parts[i] = rx.sub(lambda mt: f'<tg-emoji emoji-id="{m[lookup[mt.group(0)]]}">{lookup[mt.group(0)]}</tg-emoji>',
                          parts[i])
    return "".join(parts)
