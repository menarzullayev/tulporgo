"""Integration wiring of the bot process: other workstreams' jobs are started, and a missing one is skipped."""
import importlib

import pytest
from tulporgo_bot import main
from tulporgo_core.config import Settings
from tulporgo_core.events import InMemoryBus


class FakeBot:
    async def send_message(self, *a, **kw):
        return None


async def test_payments_jobs_are_started_and_get_the_sessionmaker():
    import tulporgo_payments.bot as paybot
    maker = object()
    paybot.STATE.pop("maker", None)
    handles = main.start_optional_jobs(FakeBot(), maker, Settings(), InMemoryBus())
    try:
        assert len(handles) == 1
        # without this the Stars subscription observer (no context middleware) silently does nothing
        assert paybot.STATE["maker"] is maker
    finally:
        for h in handles:
            h.cancel()


async def test_missing_jobs_module_is_skipped(monkeypatch):
    monkeypatch.setattr(main, "OPTIONAL_JOBS", [("tulporgo_not_installed.jobs", "setup_jobs")])
    assert main.start_optional_jobs(FakeBot(), object(), Settings(), InMemoryBus()) == []


async def test_broken_import_inside_a_jobs_module_is_not_hidden(monkeypatch):
    # negative: only "module absent" is tolerated; an ImportError of a dependency must surface
    real = importlib.import_module

    def fake(name, *a, **kw):
        if name == "tulporgo_payments.jobs":
            raise ModuleNotFoundError("No module named 'some_dependency'", name="some_dependency")
        return real(name, *a, **kw)

    monkeypatch.setattr(main.importlib, "import_module", fake)
    with pytest.raises(ModuleNotFoundError):
        main.start_optional_jobs(FakeBot(), object(), Settings(), InMemoryBus())
