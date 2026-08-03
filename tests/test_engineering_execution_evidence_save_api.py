from __future__ import annotations

from fastapi.testclient import TestClient

from hardware_splicer.engineering_execution import (
    ExecutionOperation,
    ExecutionResult,
    ExecutionStatus,
    execution_manifest,
)
from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


def _plan() -> dict:
    project = machine_project_from_intake(
        {
            "project_name": "execution-save-project",
            "goal": "Persist bounded execution evidence.",
            "available_parts": [{"name": "controller", "type": "controller"}],
        }
    )
    return {
        "schema_version": "hardware_splicer.guided_engineering_plan.v1",
        "project_name": "execution-save-project",
        "machine_project": project.model_dump(mode="json"),
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "scenario": {"compile_spec": {}},
    }


def _manifest() -> dict:
    return execution_manifest(
        ExecutionResult(
            execution_id="artifact-hash-release",
            operation=ExecutionOperation.ARTIFACT_HASH,
            status=ExecutionStatus.PASSED,
            argv=[],
            workspace="/workspace",
            target="/workspace/release.zip",
            tool_available=True,
            returncode=0,
            duration_s=0.1,
            output_hashes={"release.zip": "sha256:release"},
            metadata={
                "network_authorized": False,
                "device_access_authorized": False,
                "flash_authorized": False,
                "power_on_authorized": False,
                "motion_authorized": False,
            },
        )
    )


def test_execution_evidence_save_creates_revision_and_recomputes_status(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    response = client.post(
        "/v1/engineering/execution/evidence/save",
        json={
            "plan": _plan(),
            "execution": _manifest(),
            "expected_revision": 0,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 1
    assert body["project_id"] == "execution-save-project"
    assert body["plan"]["engineering_readiness"]["software_execution_evidence_count"] == 1
    assert body["plan"]["engineering_status"]["metadata"]["release_authorized"] is False
    saved = store.load("execution-save-project")
    snapshot = saved["snapshot"]
    assert snapshot["machineProject"]["discipline_payloads"]["engineering_execution_evidence"]["manifests"][0]["execution_id"] == "artifact-hash-release"
    assert snapshot["engineeringStatus"]["project_id"] == "execution-save-project"


def test_execution_evidence_save_rejects_stale_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    payload = {
        "plan": _plan(),
        "execution": _manifest(),
        "expected_revision": 0,
    }
    first = client.post("/v1/engineering/execution/evidence/save", json=payload)
    second = client.post("/v1/engineering/execution/evidence/save", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 409
    assert second.json()["detail"]["type"] == "engineering_plan_revision_conflict"
