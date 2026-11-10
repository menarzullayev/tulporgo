"""Compatibility shim: the converter lives in packages/core (tulporgo_core.text.alphabet) since 2026-11-10."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "core"))
from tulporgo_core.text.alphabet import *  # noqa: E402,F401,F403
from tulporgo_core.text.alphabet import _split, convert, leftovers  # noqa: E402,F401
