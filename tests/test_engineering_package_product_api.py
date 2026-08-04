from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def test_canonical_product_api_mounts_engineering_package_schema(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))

    response = client.get("/v1/engineering/packages/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "hardware_splicer.engineering_package.v1"
    assert body["deterministic_zip"] is True
    assert body["raw_source_bytes_included"] is False
    assert body["package_authority_effect"] == "none"
