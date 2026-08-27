from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.physical_evidence_api import create_physical_evidence_router


PLAN = {
    "candidate_revision": "r1",
    "machine_project": {
        "project_id": "physical-api",
        "artifacts": [
            {
                "artifact_id": "release",
                "kind": "release_bundle",
                "ref": "release/r1.zip",
                "authority": "declared",
                "metadata": {"content_hash": "sha256:r1"},
            }
        ],
    },
}

MACHINE_PROJECT = {
    "project_id": "physical-api",
    "name": "Physical API",
    "purpose": "Test scoped release API.",
    "requested_release_state": "bench_ready",
    "verifications": [
        {
            "verification_id": "design-verification",
            "name": "Design verification",
            "method_type": "analysis",
            "status": "passed",
            "target_ids": ["physical-api"],
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
            "supports": ["physical-api"],
            "authority": "verified",
            "simulated": True,
        }
    ],
}

CALIBRATIONS = [
    {
        "calibration_id": "cal-dmm",
        "instrument_id": "dmm",
        "calibrated_at": "2026-07-01T00:00:00+00:00",
        "expires_at": "2027-01-01T00:00:00+00:00",
    }
]

EVIDENCE = [
    {
        "evidence_id": "rail",
        "project_id": "physical-api",
        "candidate_revision": "r1",
        "kind": "electrical_measurement",
        "target_ids": ["physical-api"],
        "procedure_id": "power-test",
        "passed": True,
        "captured_at": "2026-08-04T02:00:00+00:00",
        "operator": "operator",
        "measured_values": {"minimum_voltage_v": 4.9},
        "acceptance_criteria": {"minimum_voltage_v": {"minimum": 4.75}},
        "instrument_ids": ["dmm"],
        "calibration_ids": ["cal-dmm"],
        "artifact_hashes": {"release": "sha256:r1"},
        "fixture_state": {"current_limited": True},
        "interlock_state": {"emergency_stop_verified": True},
    }
]

DECISION = {
    "authorization_id": "auth-r1",
    "status": "authorized",
    "scope": {
        "scope_id": "scope-r1",
        "project_id": "physical-api",
        "candidate_revision": "r1",
        "operations": ["bench_power"],
        "target_ids": ["physical-api"],
        "artifact_hashes": {"release": "sha256:r1"},
        "operating_envelope": {"maximum_voltage_v": 5.0, "current_limited": True},
        "required_evidence_kinds": ["electrical_measurement"],
    },
    "reviewer": "reviewer",
    "reviewed_at": "2026-08-04T02:15:00+00:00",
    "evidence_ids": ["rail"],
    "reason": "Bench power is supported within the scoped envelope.",
    "expires_at": "2026-09-01T00:00:00+00:00",
}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_physical_evidence_router())
    return TestClient(app)


def test_physical_evidence_schema_discloses_no_automatic_authorization() -> None:
    response = _client().get("/v1/engineering/physical-evidence/schema")

    assert response.status_code == 200, response.text
    assert response.json()["automatic_authorization"] is False


def test_assess_endpoint_validates_exact_human_scope() -> None:
    response = _client().post(
        "/v1/engineering/physical-evidence/assess",
        json={
            "plan": PLAN,
            "calibrations": CALIBRATIONS,
            "evidence": EVIDENCE,
            "decision": DECISION,
            "as_of": "2026-08-04T03:00:00+00:00",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authorization_applicable"] is True
    assert body["authorized_operations"] == ["bench_power"]
    assert body["automatic_authorization"] is False


def test_release_assess_rejects_operation_outside_scope() -> None:
    response = _client().post(
        "/v1/engineering/physical-evidence/release-assess",
        json={
            "plan": PLAN,
            "machine_project": MACHINE_PROJECT,
            "calibrations": CALIBRATIONS,
            "evidence": EVIDENCE,
            "decision": DECISION,
            "requested_operations": ["field_release"],
            "as_of": "2026-08-04T03:00:00+00:00",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["allowed"] is False
    assert body["automatic_authorization"] is False
    assert any(
        "field_release" in row
        for row in body["scoped_release"]["blockers"]
    )


def test_attach_endpoint_retains_non_simulated_physical_evidence() -> None:
    response = _client().post(
        "/v1/engineering/physical-evidence/attach",
        json={
            "plan": PLAN,
            "machine_project": MACHINE_PROJECT,
            "calibrations": CALIBRATIONS,
            "evidence": EVIDENCE,
            "decision": None,
            "as_of": "2026-08-04T03:00:00+00:00",
        },
    )

    assert response.status_code == 200, response.text
    project = response.json()["machine_project"]
    physical = [
        row for row in project["evidence"]
        if row["kind"] == "physical_evidence_record"
    ]
    assert len(physical) == 1
    assert physical[0]["simulated"] is False
    assert project["metadata"]["physical_authorization_applicable"] is False
    assert response.json()["automatic_authorization"] is False
