from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient

import hardware_splicer.project_engineering_plan_api as project_plan_api
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_engineering_plan_api import (
    create_project_engineering_plan_router,
)
from hardware_splicer.project_store import ProjectStore


def _seed(store: ProjectStore) -> None:
    store.save(
        "rover-r1",
        {
            "projectId": "rover-r1",
            "projectName": "Rover R1",
            "mode": "greenfield",
            "currentStage": "source_intake",
            "engineeringSourceUploads": [
                {
                    "source_id": "upload-abc",
                    "content_hash": "sha256:abc",
                    "blob_ref": "sources/sha256/ab/abc",
                }
            ],
            "engineeringSources": [
                {
                    "source_id": "upload-abc",
                    "source_type": "cad",
                    "uri": "hs-project://rover-r1/sources/sha256/ab/abc",
                    "revision": "sha256:abc",
                    "content_hash": "sha256:abc",
                    "authority_ceiling": "declared",
                }
            ],
            "futureExtension": {"preserve": True},
        },
        expected_revision=0,
        metadata={"source": "test"},
    )


def _plan(project_id: str = "rover-r1") -> Dict[str, Any]:
    return {
        "schema_version": "hardware_splicer.guided_engineering_plan.v1",
        "project_name": project_id,
        "machine_project": {"project_id": project_id, "name": "Rover R1"},
        "engineering_context": {"normalized_mode": "greenfield"},
        "engineering_source_graph": {"sources": [], "claims": [], "conflicts": []},
        "robot_topology": {},
        "engineering_analysis": {},
        "change_impact": {},
        "engineering_identity_map": {},
        "verification_bridge": {},
        "engineering_artifact_projection": {},
        "manufacturing_projection": {},
        "manufacturing_closure": {},
        "engineering_execution_plan": {},
        "operator_guide": {"steps": []},
        "ordered_steps": [],
        "source_adapter": {},
        "engineering_readiness": {
            "status": "blocked",
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
        "engineering_status": {"overall_status": "blocked", "blockers": []},
        "missing_info": [],
    }


def test_project_plan_uses_registered_sources_and_preserves_project_registry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path)
    _seed(store)
    captured: Dict[str, Any] = {}

    def fake_planner(
        intake,
        *,
        engineering_sources,
        declared_conflicts,
        baseline_project,
        skip_vision,
    ):
        captured["intake"] = intake
        captured["engineering_sources"] = list(engineering_sources)
        captured["declared_conflicts"] = list(declared_conflicts)
        captured["baseline_project"] = baseline_project
        captured["skip_vision"] = skip_vision
        return _plan()

    monkeypatch.setattr(project_plan_api, "plan_guided_engineering_project", fake_planner)
    app = FastAPI()
    app.include_router(create_project_engineering_plan_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/rover-r1/engineering/plan",
        json={
            "expected_revision": 1,
            "intake": {
                "project_name": "rover-r1",
                "goal": "Prepare a bounded indoor inspection rover.",
                "mode": "greenfield",
            },
            "additional_engineering_sources": [
                {
                    "source_id": "manual-a",
                    "source_type": "manual",
                    "revision": "rev-a",
                    "authority_ceiling": "declared",
                },
                {
                    "source_id": "upload-abc",
                    "source_type": "cad",
                    "content_hash": "sha256:abc",
                    "authority_ceiling": "declared",
                },
            ],
            "skip_vision": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["revision"] == 2
    assert payload["persisted_source_count"] == 1
    assert payload["combined_source_count"] == 2
    assert payload["authority_unchanged"] is True
    assert len(captured["engineering_sources"]) == 2
    assert captured["engineering_sources"][0]["source_id"] == "upload-abc"
    assert captured["skip_vision"] is True

    saved = store.load("rover-r1", revision=2)
    snapshot = saved["snapshot"]
    assert snapshot["futureExtension"] == {"preserve": True}
    assert snapshot["engineeringSourceUploads"][0]["source_id"] == "upload-abc"
    assert len(snapshot["engineeringSources"]) == 2
    assert snapshot["engineeringPlan"]["schema_version"] == "hardware_splicer.guided_engineering_plan.v1"
    assert saved["metadata"]["automatic_execution"] is False
    assert saved["metadata"]["physical_authority_unchanged"] is True


def test_project_plan_rejects_stale_revision_before_planning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ProjectStore(tmp_path)
    _seed(store)
    called = False

    def fake_planner(*args, **kwargs):
        nonlocal called
        called = True
        return _plan()

    monkeypatch.setattr(project_plan_api, "plan_guided_engineering_project", fake_planner)
    app = FastAPI()
    app.include_router(create_project_engineering_plan_router(store))
    client = TestClient(app)

    response = client.post(
        "/v1/projects/rover-r1/engineering/plan",
        json={
            "expected_revision": 7,
            "intake": {"project_name": "rover-r1", "goal": "Plan rover"},
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "project_engineering_plan_revision_conflict"
    assert called is False
    assert store.load("rover-r1")["revision"] == 1


def test_canonical_product_app_mounts_project_plan_route(tmp_path: Path) -> None:
    app = create_product_app(ProjectStore(tmp_path))
    assert "/v1/projects/{project_id}/engineering/plan" in app.openapi()["paths"]
