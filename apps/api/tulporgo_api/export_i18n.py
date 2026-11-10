"""Export the Mini App dictionaries from `tulporgo_core.i18n` so texts stay in one place.

    uv run python -m tulporgo_api.export_i18n          # writes apps/miniapp/src/i18n/<lang>.json
    uv run python -m tulporgo_api.export_i18n --check  # exit 1 if the committed files are stale

Keys lose the `api.` prefix (`api.home.title` -> `home.title`). Placeholders such as {n} are left for the client.
"""
import json
import sys
from pathlib import Path

from tulporgo_core.enums import Lang
from tulporgo_core.i18n import catalog, t

PREFIX = "api."
DEFAULT_OUT = Path(__file__).resolve().parents[3] / "apps" / "miniapp" / "src" / "i18n"


def build() -> dict[str, dict[str, str]]:
    keys = sorted(k for k in catalog() if k.startswith(PREFIX))
    return {lg.value: {k[len(PREFIX):]: t(k, lg) for k in keys} for lg in Lang}


def render(d: dict[str, str]) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    out = DEFAULT_OUT
    stale = []
    for lang, texts in build().items():
        path = out / f"{lang}.json"
        text = render(texts)
        if "--check" in args:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
        else:
            out.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    if stale:
        print("stale: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
