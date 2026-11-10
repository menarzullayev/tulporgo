"""Optional MySQL (decision 46): aiomysql escapes binary parameters with PyMySQL's `escape_bytes_prefixed`. PyMySQL 1.2
replaced it with a string, which broke every insert of encrypted documents (CI MySQL job, 2026-11-10). Runs only where
the `mysql` extra is installed."""
import pytest

converters = pytest.importorskip("pymysql.converters")


def test_aiomysql_can_escape_bytes():
    assert callable(converters.escape_bytes_prefixed), "pin pymysql<1.2 in the mysql extra (pyproject.toml)"
    assert converters.escape_bytes_prefixed(b"\x00ab") == "_binary'\\0ab'"
