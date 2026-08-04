from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.machine_project import MachineProject
from hardware_splicer.physical_evidence_persistence_api import (
    create_physical_evidence_persistence_router,
)
from hardware_splicer.project_store import ProjectStore


def _project() -> MachineProject:
    return MachineProject.model_validate(
        {
            "project_id": "physical-save",
            "name": "Physical save",
            "purpose": "Persist scoped physical evidence.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["physical-save"],
                    "evidence_ids": ["design-evidence"],
                    "procedure": "Run design verification.",
                    "acceptance_criteria": {"passed": True},
                    "authority": "verified",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "design-evidence",
                    "kind": "software_design_verification",
                    "basis": "Design verification passed.",
                    "supports": ["physical-save"],
                    "authority": "verified",
                    "simulated": True,
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "release",
                    "kind": "release_bundle",
                    "ref": "release/r1.zip",
                    "authority": "declared",
                    "metadata": {"content_hash": "sha256:r1"},
                }
            ],
        }
    )


def _plan() -> dict:
    return {
        "schema_version": "hardware_splicer.guided_engineering_plan.v1",
        "candidate_revision": "r1",
        "machine_project": _project().model_dump(mode="json"),
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


def _payload() -> dict:
    return {
        "plan": _plan(),
        "calibrations": [
            {
                "calibration_id": "cal-dmm",
                "instrument_id": "dmm",
                "calibrated_at": "2026-07-01T00:00:00+00:00",
                "expires_at": "2027-01-01T00:00:00+00:00",
            }
        ],
        "evidence": [
            {
                "evidence_id": "rail",
                "project_id": "physical-save",
                "candidate_revision": "r1",
                "kind": "electrical_measurement",
                "target_ids": ["physical-save"],
                "procedure_id": "power-test",
                "passed": True,
                "captured_at": "2026-08-04T02:00:00+00:00",
                "operator": "operator",
                "instrument_ids": ["dmm"],
                "calibration_ids": ["cal-dmm"],
                "artifact_hashes": {"release": "sha256:r1"},
                "fixture_state": {"current_limited": True},
                "interlock_state": {"emergency_stop_verified": True},
            }
        ],
        "decision": {
            "authorization_id": "auth-r1",
            "status": "authorized",
            "scope": {
                "scope_id": "scope-r1",
                "project_id": "physical-save",
                "candidate_revision": "r1",
                "operations": ["bench_power"],
                "target_ids": ["physical-save"],
                "artifact_hashes": {"release": "sha256:r1"},
                "operating_envelope": {"maximum_voltage_v": 5.0, "current_limited": True},
                "required_evidence_kinds": ["electrical_measurement"],
            },
            "reviewer": "reviewer",
            "reviewed_at": "2026-08-04T02:15:00+00:00",
            "evidence_ids": ["rail"],
            "reason": "Bench power is supported inside the stated envelope.",
            "expires_at": "2026-09-01T00:00:00+00:00",
        },
        "requested_operations": ["bench_power"],
        "expected_revision": 0,
        "as_of": "2026-08-04T03:00:00+00:00",
    }


def _client(store: ProjectStore) -> TestClient:
    app = FastAPI()
    app.include_router(create_physical_evidence_persistence_router(store))
    return TestClient(app)


def test_apply_save_creates_revision_with_full_physical_package(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    response = _client(store).post(
        "/v1/engineering/physical-evidence/apply-save",
        json=_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 1
    assert body["project_id"] == "physical-save"
    assert body["scoped_release_assessment"]["allowed"] is True
    assert body["engineering_readiness"]["scoped_authorized_operations"] == ["bench_power"]
    assert body["engineering_readiness"]["power_on_authorized"] is False
    assert body["automatic_authorization"] is False
    assert body["global_authority_flags_unchanged"] is True

    saved = store.load("physical-save")
    plan = saved["snapshot"]["engineeringPlan"]
    assert plan["physical_evidence_package"]["decision"]["authorization_id"] == "auth-r1"
    assert plan["physical_evidence_package"]["calibrations"][0]["calibration_id"] == "cal-dmm"
    assert plan["machine_project"]["discipline_payloads"]["physical_evidence"]["assessment"]["applicable"] is True
    assert plan["scenario"]["physical_authorization"]["authorized_operations"] == ["bench_power"]


def test_apply_save_rejects_stale_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = _client(store)
    payload = _payload()

    first = client.post("/v1/engineering/physical-evidence/apply-save", json=payload)
    second = client.post("/v1/engineering/physical-evidence/apply-save", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 409
    assert second.json()["detail"]["type"] == "engineering_plan_revision_conflict"
