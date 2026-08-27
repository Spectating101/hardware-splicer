from __future__ import annotations

import copy

import pytest

import hardware_splicer  # noqa: F401
from hardware_splicer.audited_physical_evidence_plan_update import (
    apply_audited_physical_evidence_to_plan,
)
from hardware_splicer.engineering_plan_store import save_engineering_plan
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
from hardware_splicer.project_store import ProjectStore, RevisionConflict


def _base_plan(*, revision: str = "r1") -> dict:
    project = MachineProject.model_validate(
        {
            "project_id": "central-audit-guard",
            "name": "Central audit guard",
            "purpose": "Preserve physical audit history across full replans.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["central-audit-guard"],
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
                    "supports": ["central-audit-guard"],
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
        "candidate_revision": revision,
        "machine_project": project.model_dump(mode="json"),
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {
            "candidate_revision": revision,
            "impacts": [],
            "unresolved": [],
        },
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "scenario": {"compile_spec": {}},
    }


def _audited_r1_plan() -> dict:
    record = PhysicalEvidenceRecord(
        evidence_id="rail-test",
        project_id="central-audit-guard",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["central-audit-guard"],
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
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-r1",
        record=record,
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
    decision = AuthorizationDecision(
        authorization_id="auth-r1",
        status="authorized",
        scope=AuthorizationScope(
            scope_id="scope-r1",
            project_id="central-audit-guard",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["central-audit-guard"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0, "current_limited": True},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Candidate r1 is supported for current-limited bench power.",
        expires_at="2026-09-01T00:00:00+00:00",
    )
    ledger = build_authorization_ledger_entry(
        entry_id="entry-r1",
        decision=decision,
        recorded_at="2026-08-04T02:35:00+00:00",
        recorded_by="release-clerk",
    )
    return apply_audited_physical_evidence_to_plan(
        _base_plan(),
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
    )


def test_full_replan_carries_history_and_invalidates_old_scope(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    first = save_engineering_plan(
        store,
        _audited_r1_plan(),
        expected_revision=0,
    )
    assert first["revision"] == 1

    candidate = _base_plan(revision="r2")
    second = save_engineering_plan(
        store,
        candidate,
        expected_revision=1,
    )

    assert second["revision"] == 2
    saved = second["snapshot"]["engineeringPlan"]
    assert saved["audited_physical_evidence"]["envelopes"][0]["envelope_id"] == "envelope-r1"
    assert saved["audited_physical_evidence"]["ledger_entries"][0]["entry_id"] == "entry-r1"
    assert saved["audited_physical_evidence"]["applicable"] is False
    assert saved["scoped_release_assessment"]["allowed"] is False
    assert saved["engineering_readiness"]["physical_audit_history_preserved"] is True
    assert saved["engineering_readiness"]["physical_authorization_revalidated"] is True
    assert saved["engineering_readiness"]["scoped_authorized_operations"] == []
    assert saved["physical_audit_persistence_guard"]["authorization_carries_across_revisions"] is False


def test_full_replan_with_audit_history_requires_explicit_revision(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    save_engineering_plan(store, _audited_r1_plan(), expected_revision=0)

    with pytest.raises(RevisionConflict, match="expected_revision is required"):
        save_engineering_plan(store, _base_plan(revision="r2"))

    assert store.load("central-audit-guard")["revision"] == 1


def test_full_replan_rejects_historical_envelope_rewrite(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    original = _audited_r1_plan()
    save_engineering_plan(store, original, expected_revision=0)

    candidate = copy.deepcopy(original)
    candidate["audited_physical_evidence"]["envelopes"][0]["record"][
        "measured_values"
    ] = {"minimum_voltage_v": 3.2}

    with pytest.raises(RevisionConflict, match="rewrites persisted physical evidence envelope"):
        save_engineering_plan(store, candidate, expected_revision=1)

    assert store.load("central-audit-guard")["revision"] == 1


def test_full_replan_rejects_historical_ledger_rewrite(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects")
    original = _audited_r1_plan()
    save_engineering_plan(store, original, expected_revision=0)

    candidate = copy.deepcopy(original)
    candidate["audited_physical_evidence"]["ledger_entries"][0]["decision"][
        "reason"
    ] = "Rewritten historical rationale."

    with pytest.raises(RevisionConflict, match="rewrites the persisted prefix"):
        save_engineering_plan(store, candidate, expected_revision=1)

    assert store.load("central-audit-guard")["revision"] == 1
