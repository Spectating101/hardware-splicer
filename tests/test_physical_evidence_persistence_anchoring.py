from __future__ import annotations

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
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


AS_OF = "2026-08-04T04:00:00+00:00"


def _project(*, name: str = "Stored project") -> MachineProject:
    return MachineProject.model_validate(
        {
            "project_id": "anchored-save",
            "name": name,
            "purpose": "Verify persistence base anchoring.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["anchored-save"],
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
                    "supports": ["anchored-save"],
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


def _plan(*, name: str = "Stored project") -> dict:
    return {
        "candidate_revision": "r1",
        "machine_project": _project(name=name).model_dump(mode="json"),
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
        project_id="anchored-save",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["anchored-save"],
        procedure_id="power-test",
        passed=True,
        captured_at="2026-08-04T02:00:00+00:00",
        operator="operator",
        measured_values={"minimum_voltage_v": 4.91},
        acceptance_criteria={"minimum_voltage_v": {"minimum": 4.75}},
        instrument_ids=["dmm"],
        calibration_ids=["cal-dmm"],
        artifact_hashes={"release": "sha256:r1"},
        raw_refs=["lab://rail.csv"],
    )


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        authorization_id="auth-r1",
        status="authorized",
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="anchored-save",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["anchored-save"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Current-limited evidence supports this scope.",
        expires_at="2026-09-01T00:00:00+00:00",
    )


def _audit_payload() -> dict:
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-rail",
        record=_record(),
        raw_files=[
            {
                "ref": "lab://rail.csv",
                "content_hash": f"sha256:{'a' * 64}",
                "media_type": "text/csv",
            }
        ],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )
    ledger = build_authorization_ledger_entry(
        entry_id="entry-auth-r1",
        decision=_decision(),
        recorded_at="2026-08-04T02:35:00+00:00",
        recorded_by="release-clerk",
    )
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
        "envelopes": [envelope.model_dump(mode="json")],
        "ledger_entries": [ledger.model_dump(mode="json")],
        "requested_operations": ["bench_power"],
        "scope_id": "scope-r1",
        "expected_revision": 0,
        "as_of": AS_OF,
    }


def test_existing_project_requires_explicit_expected_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    initial = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=_audit_payload(),
    )
    assert initial.status_code == 200, initial.text

    replay = _audit_payload()
    replay.pop("expected_revision")
    response = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=replay,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "engineering_plan_revision_conflict"
    assert "expected_revision is required" in response.json()["detail"]["message"]
    assert store.load("anchored-save")["revision"] == 1


def test_existing_write_uses_stored_plan_not_caller_replacement(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    initial = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=_audit_payload(),
    )
    assert initial.status_code == 200, initial.text

    replay = _audit_payload()
    replay["expected_revision"] = 1
    replay["plan"] = _plan(name="Caller replacement must be ignored")
    response = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=replay,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["base_plan_source"] == "stored_revision"
    assert body["plan"]["machine_project"]["name"] == "Stored project"
    saved = store.load("anchored-save")["snapshot"]["engineeringPlan"]
    assert saved["machine_project"]["name"] == "Stored project"
    assert saved["audited_physical_evidence"]["envelopes"][0]["envelope_id"] == "envelope-rail"


def test_omitting_persisted_audit_history_is_rejected_before_save(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))
    initial = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=_audit_payload(),
    )
    assert initial.status_code == 200, initial.text

    attack = _audit_payload()
    attack["expected_revision"] = 1
    attack["plan"] = _plan()
    attack["envelopes"] = []
    attack["ledger_entries"] = []
    response = client.post(
        "/v1/engineering/physical-evidence/audited-apply-save",
        json=attack,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["type"] == "engineering_plan_revision_conflict"
    assert "append-only" in response.json()["detail"]["message"]
    assert store.load("anchored-save")["revision"] == 1
    saved = store.load("anchored-save")["snapshot"]["engineeringPlan"]
    assert saved["audited_physical_evidence"]["envelopes"][0]["envelope_id"] == "envelope-rail"
