from __future__ import annotations

from hardware_splicer.audited_physical_evidence_plan_update import (
    apply_audited_physical_evidence_to_plan,
)
from hardware_splicer.engineering_action import prepare_engineering_action
from hardware_splicer.engineering_status import build_engineering_status
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


def _plan() -> dict:
    project = MachineProject.model_validate(
        {
            "project_id": "candidate-revalidation",
            "name": "Candidate revalidation",
            "purpose": "Prevent physical authorization carryover.",
            "requested_release_state": "bench_ready",
            "verifications": [
                {
                    "verification_id": "design-verification",
                    "name": "Design verification",
                    "method_type": "analysis",
                    "status": "passed",
                    "target_ids": ["candidate-revalidation"],
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
                    "supports": ["candidate-revalidation"],
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


def _authorized_r1_plan() -> dict:
    record = PhysicalEvidenceRecord(
        evidence_id="rail-test",
        project_id="candidate-revalidation",
        candidate_revision="r1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["candidate-revalidation"],
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
            project_id="candidate-revalidation",
            candidate_revision="r1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["candidate-revalidation"],
            artifact_hashes={"release": "sha256:r1"},
            operating_envelope={"maximum_voltage_v": 5.0},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="reviewer",
        reviewed_at="2026-08-04T02:30:00+00:00",
        evidence_ids=["rail-test"],
        reason="Candidate r1 is supported for current-limited bench power.",
        # This fixture tests candidate revalidation, not wall-clock expiry.
        expires_at="2027-09-01T00:00:00+00:00",
    )
    entry = build_authorization_ledger_entry(
        entry_id="entry-r1",
        decision=decision,
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
        ledger_entries=[entry],
        requested_operations=[PhysicalOperation.BENCH_POWER],
        scope_id="scope-r1",
    )


def test_candidate_revision_change_invalidates_cached_authorization() -> None:
    plan = _authorized_r1_plan()
    initial = build_engineering_status(plan)
    assert initial.metadata["physical_scope_authorized"] is True

    changed = dict(plan)
    changed["candidate_revision"] = "r2"
    changed["change_impact"] = {
        **dict(plan.get("change_impact") or {}),
        "candidate_revision": "r2",
        "impacts": [],
        "unresolved": [],
    }
    # Deliberately preserve stale cached declarations.
    changed["audited_physical_evidence"] = dict(plan["audited_physical_evidence"])
    changed["audited_physical_evidence"]["applicable"] = True
    changed["scoped_release_assessment"] = dict(plan["scoped_release_assessment"])
    changed["scoped_release_assessment"]["allowed"] = True

    status = build_engineering_status(changed)

    assert status.overall_status == "blocked"
    assert status.metadata["physical_authorization_revalidated"] is True
    assert status.metadata["physical_scope_authorized"] is False
    assert status.metadata["authorized_operations"] == []
    assert any(
        "current candidate revision" in row.message
        or "candidate" in row.message.lower()
        for row in status.blockers
    )

    prepared = prepare_engineering_action(changed)
    assert prepared.action.category == "release"
    assert prepared.status == "blocked"
    assert prepared.payload["audited_authorization_applicable"] is False
    assert prepared.payload["automatic_authorization"] is False
