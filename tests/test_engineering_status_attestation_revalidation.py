from __future__ import annotations

import base64
import copy
import json

from hardware_splicer.audited_physical_evidence_plan_update import (
    apply_audited_physical_evidence_to_plan,
)
from hardware_splicer.engineering_status import build_engineering_status
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


KEY = "v" * 48


def _plan() -> dict:
    project = MachineProject.model_validate(
        {
            "project_id": "attestation-status",
            "name": "Attestation status",
            "purpose": "Revalidate persisted raw file attestations.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["attestation-status"],
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
                    "supports": ["attestation-status"],
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
    return {
        "candidate_revision": "r1",
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


def _record() -> PhysicalEvidenceRecord:
    return PhysicalEvidenceRecord(
        evidence_id="rail-test",
        project_id="attestation-status",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["attestation-status"],
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
            project_id="attestation-status",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["attestation-status"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Attested bench evidence supports this scope.",
        expires_at="2026-09-01T00:00:00+00:00",
    )


def _strict_plan(monkeypatch) -> dict:
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY", KEY)
    monkeypatch.setenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID", "status-key")
    file_ref = attest_raw_evidence_bytes(
        {
            "ref": "lab://rail.csv",
            "content_base64": base64.b64encode(
                b"time_s,voltage_v\n0.0,4.91\n"
            ).decode("ascii"),
            "media_type": "text/csv",
        }
    ).file_ref
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-rail",
        record=_record(),
        raw_files=[file_ref],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )
    ledger = build_authorization_ledger_entry(
        entry_id="entry-auth-r1",
        decision=_decision(),
        recorded_at="2026-08-04T02:35:00+00:00",
        recorded_by="release-clerk",
    )
    return apply_audited_physical_evidence_to_plan(
        _plan(),
        calibrations=[
            {
                "calibration_id": "cal-dmm",
                "instrument_id": "dmm",
                "calibrated_at": "2026-07-01T00:00:00+00:00",
                "expires_at": "2027-01-01T00:00:00+00:00",
                "authority": "verified",
            }
        ],
        envelopes=[envelope],
        ledger_entries=[ledger],
        requested_operations=[PhysicalOperation.BENCH_POWER],
        scope_id="scope-r1",
        require_server_attestation=True,
    )


def test_fresh_status_rejects_altered_attested_file_metadata(monkeypatch) -> None:
    plan = _strict_plan(monkeypatch)
    assert build_engineering_status(plan).metadata["physical_scope_authorized"] is True
    tampered = copy.deepcopy(plan)
    raw_file = tampered["audited_physical_evidence"]["envelopes"][0]["raw_files"][0]
    raw_file["media_type"] = "application/json"
    # Preserve stale cached declarations to prove they are not trusted.
    tampered["audited_physical_evidence"]["applicable"] = True
    tampered["scoped_release_assessment"]["allowed"] = True

    status = build_engineering_status(tampered)

    assert status.overall_status == "blocked"
    assert status.metadata["physical_scope_authorized"] is False
    assert status.metadata["server_attestation_required"] is True
    assert status.metadata["server_attestation_valid"] is False
    assert any(
        "signature is invalid" in row.message
        for row in status.blockers
    )


def test_missing_verification_key_blocks_fresh_status(monkeypatch) -> None:
    plan = _strict_plan(monkeypatch)
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY")
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID")
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_VERIFICATION_KEYS", raising=False)

    status = build_engineering_status(plan)

    assert status.overall_status == "blocked"
    assert status.metadata["server_attestation_valid"] is False
    assert any("No verification key" in row.message for row in status.blockers)


def test_rotated_verification_key_preserves_valid_status(monkeypatch) -> None:
    plan = _strict_plan(monkeypatch)
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY")
    monkeypatch.delenv("HARDWARE_SPLICER_EVIDENCE_SIGNING_KEY_ID")
    monkeypatch.setenv(
        "HARDWARE_SPLICER_EVIDENCE_VERIFICATION_KEYS",
        json.dumps({"status-key": KEY}),
    )

    status = build_engineering_status(plan)

    assert status.metadata["physical_scope_authorized"] is True
    assert status.metadata["server_attestation_valid"] is True
    assert status.metadata["authorized_operations"] == ["bench_power"]
