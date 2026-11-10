"""Operations CLI: migrate, seed-places (idempotent) and the health check used after a deploy."""
import os

import pytest
from alembic import command
from tulporgo_core import manage


def _url(tmp_path):
    return os.environ.get("TULPORGO_TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{(tmp_path / 'ops.db').as_posix()}"


@pytest.fixture
def url(tmp_path):
    u = _url(tmp_path)
    command.downgrade(manage.alembic_config(u), "base")      # clean slate on a shared PostgreSQL/MySQL test DB
    yield u
    command.downgrade(manage.alembic_config(u), "base")


def test_check_fails_before_migrate(url, capsys):
    # negative: an empty database is not "healthy"
    assert manage.main(["check", "--url", url]) == 1
    assert "!= head" in capsys.readouterr().out


def test_migrate_then_check_ok(url, capsys):
    assert manage.main(["migrate", "--url", url]) == 0
    assert manage.main(["check", "--url", url]) == 0
    assert "ok, revision" in capsys.readouterr().out


def test_seed_places_is_idempotent(url, capsys):
    manage.main(["migrate", "--url", url])
    capsys.readouterr()
    assert manage.main(["seed-places", "--url", url]) == 0
    first = capsys.readouterr().out
    assert manage.main(["seed-places", "--url", url]) == 0
    second = capsys.readouterr().out
    n = int(first.split()[1])
    assert n > 1000                                           # regions + districts + Samarqand mahallas
    assert first == second                                    # second run adds nothing


def test_check_unreachable_database(tmp_path, capsys):
    # negative: a URL that cannot be opened reports unreachable, never "ok"
    bad = f"sqlite+aiosqlite:///{(tmp_path / 'missing' / 'x.db').as_posix()}"
    assert manage.main(["check", "--url", bad]) == 1
    assert "unreachable" in capsys.readouterr().out


def test_unknown_command_rejected():
    with pytest.raises(SystemExit) as e:
        manage.main(["drop-everything"])
    assert e.value.code == 2
