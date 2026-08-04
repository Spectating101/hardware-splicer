from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def test_canonical_product_api_mounts_conversation_schema(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))

    response = client.get("/v1/engineering/ai/conversation/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "hardware_splicer.ai_project_conversation.v1"
    assert body["project_changes_are_typed_proposals"] is True
    assert body["conversation_is_project_truth"] is False
    assert body["automatic_execution"] is False
    assert body["physical_authority_unchanged"] is True
