"""Splice Agent v1 product-layer tests — API, version, UI mount.

Complements verify-splice-v1 (engine). Does not run full KiCad splice compile.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hardware_splicer import _version
from hardware_splicer.api import create_app


def test_version_single_source() -> None:
    assert _version.__version__
    parts = _version.__version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith('version = "'):
            pkg_version = line.split('"')[1]
            assert pkg_version == _version.__version__
            break
    else:
        pytest.fail("version not found in pyproject.toml")


def test_health_reports_package_version() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body.get("ok") is True
    assert body.get("version") == _version.__version__
    assert "llm_policy" in body
    assert "qwen_llm_first" in body["llm_policy"]


def test_compose_request_accepts_allow_llm_first() -> None:
    from hardware_splicer.api import ComposeRequest

    row = ComposeRequest(phrase="esp32 sensor board", allow_llm_first=True)
    assert row.allow_llm_first is True


def test_openapi_version_matches() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json().get("info", {}).get("version") == _version.__version__


def test_splice_product_routes_registered() -> None:
    pytest.importorskip("fastapi")

    paths = {getattr(route, "path", "") for route in create_app().routes}
    required = {
        "/health",
        "/v1/examples/splice-intakes",
        "/v1/examples/donor-fixtures",
        "/v1/examples/netlist-fixtures",
        "/v1/integrations/catalog",
        "/v1/modules/catalog",
        "/v1/intent/clarify",
        "/v1/jobs/splice-build",
        "/v1/jobs",
        "/v1/splice-bench/status",
        "/v1/splice-bench/submit",
        "/v1/splice-bench/submit-capture",
        "/v1/splice-bench/capture-template",
        "/v1/compose",
        "/v1/vision/capabilities",
        "/v1/vision/enrich-intake",
        "/v1/donor-board-vision",
    }
    missing = required - paths
    assert not missing, f"Missing routes: {sorted(missing)}"


def test_modules_catalog_returns_footprinted_modules() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    body = client.get("/v1/modules/catalog").json()
    assert body.get("ok") is True
    assert body.get("count", 0) >= 1
    first = body["modules"][0]
    assert first.get("id")
    assert first.get("pins")


def test_examples_return_intake_payloads() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    intakes = client.get("/v1/examples/splice-intakes").json()
    assert intakes["ok"] is True
    assert len(intakes["examples"]) >= 1
    assert intakes["examples"][0]["intake"].get("goal")

    fixtures = client.get("/v1/examples/donor-fixtures").json()
    assert fixtures["ok"] is True
    assert len(fixtures["fixtures"]) >= 1


def test_jobs_list_returns_ok() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.get("/v1/jobs?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body.get("ok") is True
    assert isinstance(body.get("jobs"), list)


def test_serve_ui_mount_when_dist_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    root = Path(__file__).resolve().parents[1]
    dist = root / "apps" / "splice-ui" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        pytest.skip("splice-ui dist not built — run make splice-ui-build")

    monkeypatch.setenv("HARDWARE_SPLICER_SERVE_UI", "1")
    client = TestClient(create_app())
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert "Hardware-Splicer" in root_response.text or "Splice Agent" in root_response.text

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        sample = next(assets_dir.glob("*.js"), None)
        if sample:
            asset_response = client.get(f"/assets/{sample.name}")
            assert asset_response.status_code == 200

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json().get("version") == _version.__version__


def test_v11_interface_routes() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    catalog = client.get("/v1/integrations/catalog").json()
    assert catalog.get("ok") is True
    assert catalog.get("wired_count", 0) >= 1
    assert len(catalog.get("integrations") or []) >= catalog["wired_count"]

    fixtures = client.get("/v1/examples/netlist-fixtures").json()
    assert fixtures.get("ok") is True
    dht = next(row for row in fixtures["fixtures"] if row["id"] == "usb_esp_dht22")
    assert dht.get("description")


def test_serve_ui_off_by_default() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    env = os.environ.pop("HARDWARE_SPLICER_SERVE_UI", None)
    try:
        client = TestClient(create_app())
        response = client.get("/")
        assert response.status_code in {404, 405}
    finally:
        if env is not None:
            os.environ["HARDWARE_SPLICER_SERVE_UI"] = env
