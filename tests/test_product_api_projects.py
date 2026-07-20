from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def test_product_api_mounts_engine_and_persistent_projects(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    app = create_product_app(project_store=store)
    assert app.state.project_store is store

    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/health" in paths
        assert "/v1/compose" in paths
        assert "/v1/projects" in paths
        assert "/v1/projects/{project_id}/snapshot" in paths

        saved = client.put(
            "/v1/projects/machine-1/snapshot",
            json={
                "snapshot": {
                    "projectId": "machine-1",
                    "projectName": "Inspection robot",
                    "mode": "greenfield",
                    "currentStage": "architecture",
                    "graph": {"nodes": [], "edges": [], "phrase": "inspection robot"},
                },
                "expected_revision": 0,
            },
        )
        assert saved.status_code == 200
        assert saved.json()["project"]["revision"] == 1

        listed = client.get("/v1/projects")
        assert listed.status_code == 200
        assert listed.json()["projects"][0]["project_id"] == "machine-1"
