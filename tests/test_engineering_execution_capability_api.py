from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def test_product_api_mounts_execution_capability_route() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/execution/capabilities" in paths


def test_capability_api_reports_runtime_truth_without_physical_authority(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_EXECUTION_ENABLED", raising=False)
    monkeypatch.setattr(
        "hardware_splicer.engineering_execution_capability.shutil.which",
        lambda tool: "/usr/bin/ngspice" if tool == "ngspice" else None,
    )

    response = TestClient(create_product_app()).get(
        "/v1/engineering/execution/capabilities"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    report = body["execution_capability"]
    operations = {row["operation"]: row for row in report["operations"]}

    assert body["physical_operations_supported"] is False
    assert report["execution_enabled"] is False
    assert operations["artifact_hash"]["adapter_available"] is True
    assert operations["artifact_hash"]["tool_installed"] is True
    assert operations["artifact_hash"]["executable_under_host_policy"] is False
    assert operations["ngspice"]["tool_installed"] is True
    assert operations["kicad_erc"]["tool_installed"] is False
    assert all(row["preview_available"] is True for row in operations.values())
    assert all(row["physical_operation"] is False for row in operations.values())
    assert report["metadata"]["network_authorized"] is False
    assert report["metadata"]["network_isolation_enforced"] is False
    assert report["metadata"]["device_access_authorized"] is False
    assert report["metadata"]["flash_authorized"] is False
    assert report["metadata"]["power_on_authorized"] is False
    assert report["metadata"]["motion_authorized"] is False
    assert report["metadata"]["release_authorized"] is False
