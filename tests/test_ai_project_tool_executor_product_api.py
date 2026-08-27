from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def test_product_api_mounts_ai_preview_executor_routes(tmp_path) -> None:
    app = create_product_app(ProjectStore(tmp_path / "projects"))
    paths = set(app.openapi()["paths"])

    assert "/v1/engineering/ai/tools/schema" in paths
    assert (
        "/v1/projects/{project_id}/ai-sessions/{session_id}/actions/{action_id}/execute-preview"
        in paths
    )

    response = TestClient(app).get("/v1/engineering/ai/tools/schema")
    assert response.status_code == 200
    assert response.json()["automatic_execution"] is False
    assert response.json()["device_access_authorized"] is False
