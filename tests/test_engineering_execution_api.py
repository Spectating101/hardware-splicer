from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app


def test_product_api_mounts_execution_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/execution/schema" in paths
    assert "/v1/engineering/execution/preview" in paths
    assert "/v1/engineering/execution/run" in paths


def test_execution_preview_cannot_authorize_physical_operations(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ROOT", str(tmp_path))
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"preview")
    response = TestClient(create_product_app()).post(
        "/v1/engineering/execution/preview",
        json={
            "execution_id": "preview",
            "operation": "artifact_hash",
            "workspace": ".",
            "target": "artifact.bin",
            "execute": True,
        },
    )

    assert response.status_code == 200, response.text
    execution = response.json()["execution"]
    assert execution["status"] == "planned"
    assert execution["metadata"]["flash_authorized"] is False
    assert execution["metadata"]["power_on_authorized"] is False
    assert execution["metadata"]["motion_authorized"] is False


def test_execution_run_is_blocked_by_default_host_policy(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_EXECUTION_ENABLED", raising=False)
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"blocked")
    response = TestClient(create_product_app()).post(
        "/v1/engineering/execution/run",
        json={
            "execution_id": "blocked-run",
            "operation": "artifact_hash",
            "workspace": ".",
            "target": "artifact.bin",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False
    assert body["execution"]["status"] == "blocked"
    assert body["flash_authorized"] is False
    assert body["power_on_authorized"] is False
    assert body["motion_authorized"] is False


def test_execution_api_rejects_path_escape(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ROOT", str(tmp_path))
    response = TestClient(create_product_app()).post(
        "/v1/engineering/execution/preview",
        json={
            "execution_id": "escape",
            "operation": "artifact_hash",
            "workspace": ".",
            "target": "../outside.bin",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "execution_policy_error"
