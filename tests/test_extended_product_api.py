from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.extended_product_api import create_extended_product_app
from hardware_splicer.project_store import ProjectStore


def test_extended_product_app_mounts_physical_evidence_routes(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    app = create_extended_product_app(store)
    paths = set(app.openapi()["paths"])

    assert "/v1/engineering/status" in paths
    assert "/v1/engineering/actions/prepare" in paths
    assert "/v1/engineering/execution/capabilities" in paths
    assert "/v1/engineering/physical-evidence/schema" in paths
    assert "/v1/engineering/physical-evidence/assess" in paths
    assert "/v1/engineering/physical-evidence/attach" in paths
    assert "/v1/engineering/physical-evidence/release-assess" in paths
    assert "/v1/engineering/physical-evidence/apply-save" in paths


def test_extended_product_schema_discloses_human_authorization_requirement(tmp_path) -> None:
    client = TestClient(create_extended_product_app(ProjectStore(tmp_path / "projects")))

    response = client.get("/v1/engineering/physical-evidence/schema")

    assert response.status_code == 200, response.text
    assert response.json()["automatic_authorization"] is False
