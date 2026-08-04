from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer.machine_project import MachineProject
from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from hardware_splicer.physical_evidence_ledger import (
    build_authorization_ledger_entry,
    build_physical_evidence_envelope,
)
from hardware_splicer.physical_evidence_persistence_api import (
    create_physical_evidence_persistence_router,
)
from hardware_splicer.project_store import ProjectStore


AS_OF = "2026-08-04T04:00:00+00:00"


def _project() -> MachineProject:
    return MachineProject.model_validate(
        {
            "project_id": "audited-save",
            "name": "Audited save",
            "purpose": "Persist tamper-evident physical evidence.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["audited-save"],
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
                    "supports": ["audited-save"],
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


def _record() -> PhysicalEvidenceRecord:
    return PhysicalEvidenceRecord(
        evidence_id="rail-test",
        project_id="audited-save",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["audited-save"],
        procedure_id="power-test",
        passed=True,
        captured_at="2026-08-04T02:00:00+00:00",
        operator="operator",
        measured_values={"minimum_voltage_v": 4.91},
        acceptance_criteria={"minimum_voltage_v": {"minimum": 4.75}},
        instrument_ids=["dmm"],
        calibration_ids=["cal-dmm"],
        artifact_hashes={"release": "sha256:r1"},
        fixture_state={"current_limited": True},
        interlock_state={"emergency_stop_verified": True},
        raw_refs=["lab://rail/run.csv"],
    )


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        authorization_id="auth-r1",
        status="authorized",
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="audited-save",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["audited-save"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Current-limited bench power is supported by retained evidence.",
        expires_at="2026-09-01T00:00:00+00:00",
    )


def _envelope() -> dict:
    return build_physical_evidence_envelope(
        envelope_id="envelope-rail",
        record=_record(),
        raw_files=[
            {
                "ref": "lab://rail/run.csv",
                "content_hash": f"sha256:{'a' * 64}",
                "media_type": "text/csv",
            }
        ],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    ).model_dump(mode="json")


def _ledger_entry() -> dict:
    return build_authorization_ledger_entry(
        entry_id="entry-auth-r1",
        decision=_decision(),
        recorded_at="2026-08-04T02:35:00+00:00",
        recorded_by="release-clerk",
    ).model_dump(mode="json")


def _payload() -> dict:
    return {
        "plan": _plan(),
        "calibrations": [
            {
                "calibration_id": "cal-dmm",
                "instrument_id": "dmm",
                "calibrated_at": "2026-07-01T00:00:00+00:00",
                "expires_at": "2027-01-01T00:00:00+00:00",
                "authority": "verified",
            }
        ],
        "envelopes": [_envelope()],
        "ledger_entries": [_ledger_entry()],
        "requested_operations": ["bench_power"],
        "scope_id": "scope-r1",
        "expected_revision": 0,
        "as_of": AS_OF,
    }


def _client(store: ProjectStore) -> TestClient:
    app = FastAPI()
    app.include_router(create_physical_evidence_persistence_router(store))
    return TestClient(app)


def test_audited_apply_save_persists_envelopes_ledger_and_scope(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    response = _client(store).post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 1
    assert body["authorization_applicable"] is True
    assert body["tamper_evident_envelopes_validated"] is True
    assert body["authorization_ledger_validated"] is True
    assert body["scoped_release_assessment"]["allowed"] is True
    assert body["engineering_readiness"]["scoped_authorized_operations"] == ["bench_power"]
    assert body["power_on_authorized"] is False
    assert body["automatic_authorization"] is False

    saved = store.load("audited-save")["snapshot"]["engineeringPlan"]
    audited = saved["audited_physical_evidence"]
    assert audited["envelopes"][0]["envelope_id"] == "envelope-rail"
    assert audited["ledger_entries"][0]["entry_id"] == "entry-auth-r1"
    assert audited["ledger_assessment"]["valid"] is True
    assert saved["scenario"]["audited_physical_authorization"]["authorized_operations"] == ["bench_power"]


def test_tampered_envelope_is_persisted_only_as_blocked_state(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    payload = _payload()
    tampered = payload["envelopes"][0]
    tampered["record"]["measured_values"]["minimum_voltage_v"] = 3.2

    response = _client(store).post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=payload,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authorization_applicable"] is False
    assert body["tamper_evident_envelopes_validated"] is False
    assert body["scoped_release_assessment"] is None
    assert body["engineering_readiness"]["status"] == "blocked"
    assert body["engineering_readiness"]["scoped_authorized_operations"] == []
    assert body["power_on_authorized"] is False


def test_audited_apply_save_rejects_stale_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = _client(store)
    payload = _payload()

    first = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=payload,
    )
    second = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=payload,
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409
    assert second.json()["detail"]["type"] == "engineering_plan_revision_conflict"
