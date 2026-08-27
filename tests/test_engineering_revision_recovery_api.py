from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _plan(label: str) -> dict:
    return {
        "machine_project": {
            "project_id": "recovery-diff",
            "components": [{"component_id": label}],
            "interfaces": [],
            "artifacts": [],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {},
        },
        "robot_topology": {"links": [], "joints": [], "actuators": [], "sensors": [], "unresolved": []},
        "manufacturing_projection": {},
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
    }


def _snapshot(plan: dict) -> dict:
    return {
        "projectId": "recovery-diff",
        "projectName": "Recovery diff",
        "engineeringPlan": plan,
    }


def test_revision_diff_recovers_from_corrupt_latest_snapshot(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save("recovery-diff", _snapshot(_plan("base")), expected_revision=0)
    store.save("recovery-diff", _snapshot(_plan("candidate")), expected_revision=1)
    store.save("recovery-diff", _snapshot(_plan("corrupt")), expected_revision=2)

    store._revision_path("recovery-diff", 3).write_text("{not-json", encoding="utf-8")

    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/revisions/diff",
        json={"project_id": "recovery-diff"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["base_revision"] == 1
    assert body["candidate_revision"] == 2
    assert body["recovery"]["used"] is True
    assert body["recovery"]["requested_revision"] == 3
    assert body["recovery"]["loaded_revision"] == 2
    assert body["recovery"]["quarantined_revisions"] == [3]
    assert body["engineering_revision_diff"]["summary"]["identity_change_category_count"] == 1
