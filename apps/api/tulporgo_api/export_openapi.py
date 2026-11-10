"""The HTTP API contract as a file (GOAL.md §2 docs/): `docs/openapi.json`, generated from the running app.

    uv run python -m tulporgo_api.export_openapi            # write
    uv run python -m tulporgo_api.export_openapi --check    # exit 1 when the file is stale (CI)
"""
import json
import sys
from pathlib import Path

from tulporgo_core.config import Settings
from tulporgo_core.events import InMemoryBus

from .main import create_app

OUT = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"


def render() -> str:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")   # no secrets, no DB needed
    app = create_app(settings, None, InMemoryBus())
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None, out: Path = OUT) -> int:
    args = sys.argv[1:] if argv is None else argv
    text = render()
    if "--check" in args:
        ok = out.exists() and out.read_text(encoding="utf-8") == text
        print("openapi: up to date" if ok else "openapi: STALE — run `uv run python -m tulporgo_api.export_openapi`")
        return 0 if ok else 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"openapi: wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
