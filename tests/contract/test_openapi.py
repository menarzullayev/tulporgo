"""docs/openapi.json is the published HTTP contract; it must match the code (regenerate on every API change)."""
from tulporgo_api import export_openapi


def test_openapi_file_is_current():
    assert export_openapi.main(["--check"]) == 0, "run: uv run python -m tulporgo_api.export_openapi"


def test_stale_file_is_detected(tmp_path):
    stale = tmp_path / "openapi.json"
    stale.write_text(export_openapi.OUT.read_text(encoding="utf-8").replace('"/api/me"', '"/api/old-me"'),
                     encoding="utf-8")
    assert export_openapi.main(["--check"], out=stale) == 1      # negative: an outdated contract fails CI
    assert export_openapi.main(["--check"], out=tmp_path / "missing.json") == 1


def test_contract_has_the_mini_app_and_webhook_endpoints():
    paths = set(__import__("json").loads(export_openapi.render())["paths"])
    for p in ("/api/me", "/api/requests", "/api/share/{token}", "/api/payments/checkout",
              "/api/payments/click/prepare", "/api/payments/payme", "/api/userbot/login/start"):
        assert p in paths, p
