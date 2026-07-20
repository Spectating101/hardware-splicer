from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def test_release_api_allows_higher_achieved_authority_for_lower_request(tmp_path: Path) -> None:
    app = create_product_app(project_store=ProjectStore(tmp_path))
    project = {
        "project_id": "verified-machine",
        "name": "Verified machine",
        "purpose": "Exercise release ordering.",
        "verifications": [
            {
                "verification_id": "verify-machine",
                "name": "Machine acceptance test",
                "method_type": "test",
                "status": "passed",
                "target_ids": ["verified-machine"],
                "evidence_ids": ["evidence-machine"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "evidence-machine",
                "kind": "acceptance_test",
                "basis": "instrument",
                "supports": ["verified-machine"],
                "authority": "measured",
                "simulated": False,
            }
        ],
    }

    with TestClient(app) as client:
        response = client.post(
            "/v1/machine-projects/assess-release",
            json={"project": project, "requested_state": "design_ready"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["assessment"]["achieved_state"] == "operationally_authorized"
    assert body["assessment"]["requested_state"] == "design_ready"
    assert body["assessment"]["blockers"] == []
    assert body["allowed"] is True
