from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from hardware_splicer.machine_project import MachineProject
from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from hardware_splicer.physical_evidence_attestation import attest_raw_evidence_bytes
from hardware_splicer.physical_evidence_ledger import (
    build_authorization_ledger_entry,
    build_physical_evidence_envelope,
)
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


KEY = "z" * 48


def _project() -> MachineProject:
    return MachineProject.model_validate(
        {
            "project_id": "attested-save",
            "name": "Attested save",
            "purpose": "Persist server-attested physical evidence.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["attested-save"],
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
                    "supports": ["attested-save"],
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
        project_id="attested-save",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["attested-save"],
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
        raw_refs=["lab://rail.csv"],
    )


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        authorization_id="auth-r1",
        status="authorized",
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="attested-save",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["attested-save"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Server-attested bench evidence supports this scope.",
        expires_at="2026-09-01T00:00:00+00:00",
    )


def _file_ref(*, attested: bool):
    result = attest_raw_evidence_bytes(
        {
            "ref": "lab://rail.csv",
            "content_base64": base64.b64encode(
                b"time_s,voltage_v\n0.0,4.91\n"
            ).decode("ascii"),
            "media_type": "text/csv",
        }
    ).file_ref
    if attested:
        return result
    metadata = dict(result.metadata)
    metadata.pop("server_attestation")
    return result.model_copy(update={"metadata": metadata}, deep=True)


def _payload(*, attested: bool) -> dict:
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-rail",
        record=_record(),
        raw_files=[_file_ref(attested=attested)],
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
        "as_of": "2026-08-04T04:00:00+00:00",
    }


def test_attested_audited_apply_save_persists_strict_scope(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "save-key")
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))

    response = client.post(
        "/v1/engineering/physical-evidence/attested-audited-apply-save",
        json=_payload(attested=True),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 1
    assert body["authorization_applicable"] is True
    assert body["server_attestation_required"] is True
    assert body["server_attestation_valid"] is True
    assert body["scoped_release_assessment"]["allowed"] is True
    assert body["engineering_readiness"]["scoped_authorized_operations"] == ["bench_power"]
    assert body["power_on_authorized"] is False

    saved = store.load("attested-save")["snapshot"]["engineeringPlan"]
    assert saved["engineering_readiness"]["server_attestation_required"] is True
    assert saved["engineering_readiness"]["server_attestation_valid"] is True
    assert saved["scenario"]["audited_physical_authorization"]["authorized_operations"] == ["bench_power"]


def test_unsigned_evidence_persists_only_as_blocked_strict_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "save-key")
    store = ProjectStore(tmp_path / "projects")
    client = TestClient(create_product_app(store))

    response = client.post(
        "/v1/engineering/physical-evidence/attested-audited-apply-save",
        json=_payload(attested=False),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authorization_applicable"] is False
    assert body["server_attestation_required"] is True
    assert body["server_attestation_valid"] is False
    assert body["scoped_release_assessment"]["allowed"] is False
    assert body["engineering_readiness"]["status"] == "blocked"
    assert body["engineering_readiness"]["scoped_authorized_operations"] == []
    assert body["power_on_authorized"] is False
