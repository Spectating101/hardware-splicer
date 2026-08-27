from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _plan(blocker: bool) -> dict:
    findings = (
        [
            {
                "finding_id": "analysis-current",
                "category": "power",
                "status": "fail",
                "message": "Current margin is negative.",
                "target_ids": ["controller"],
                "missing_inputs": [],
                "blocking": True,
            }
        ]
        if blocker
        else []
    )
    return {
        "machine_project": {
            "project_id": "stored-diff",
            "components": [{"component_id": "controller"}],
            "interfaces": [],
            "artifacts": [],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {},
        },
        "robot_topology": {"links": [], "joints": [], "actuators": [], "sensors": [], "unresolved": []},
        "manufacturing_projection": {},
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "engineering_analysis": {"findings": findings},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "blocked" if blocker else "candidate"},
    }


def test_product_api_mounts_revision_diff_routes() -> None:
    paths = set(create_product_app().openapi()["paths"])

    assert "/v1/engineering/revisions/diff" in paths
    assert "/v1/engineering/revisions/diff/schema" in paths


def test_revision_api_loads_stored_revisions_and_reports_resolution(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save(
        "stored-diff",
        {
            "projectId": "stored-diff",
            "projectName": "Stored diff",
            "engineeringPlan": _plan(True),
        },
        expected_revision=0,
    )
    store.save(
        "stored-diff",
        {
            "projectId": "stored-diff",
            "projectName": "Stored diff",
            "engineeringPlan": _plan(False),
        },
        expected_revision=1,
    )
    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/revisions/diff",
        json={"project_id": "stored-diff"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["base_revision"] == 1
    assert body["candidate_revision"] == 2
    diff = body["engineering_revision_diff"]
    assert diff["summary"]["resolved_blocker_count"] == 1
    assert diff["resolved_blockers"][0]["blocker_id"] == "analysis-current"
    assert body["automatic_merge"] is False
    assert body["release_authorized"] is False


def test_revision_api_requires_prior_stored_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    store.save(
        "single-revision",
        {
            "projectId": "single-revision",
            "projectName": "Single",
            "engineeringPlan": _plan(True),
        },
        expected_revision=0,
    )
    response = TestClient(create_product_app(store)).post(
        "/v1/engineering/revisions/diff",
        json={"project_id": "single-revision"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "invalid_engineering_revision_diff"
