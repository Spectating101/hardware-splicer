from __future__ import annotations

from hardware_splicer.engineering_revision_diff import diff_engineering_revisions
from hardware_splicer.engineering_status import build_engineering_status
from hardware_splicer.physical_evidence import (
    AuthorizationDecision,
    AuthorizationScope,
    AuthorizationStatus,
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
    PhysicalOperation,
)
from hardware_splicer.physical_evidence_ledger import (
    build_authorization_ledger_entry,
    build_physical_evidence_envelope,
)


RAW_HASH = "sha256:" + "1" * 64
ARTIFACT_HASH = "sha256:" + "2" * 64


def _audited_physical_evidence(*, valid: bool) -> dict:
    record = PhysicalEvidenceRecord(
        evidence_id="evidence-1",
        project_id="physical-status",
        candidate_revision="candidate-1",
        kind=PhysicalEvidenceKind.ELECTRICAL,
        target_ids=["controller"],
        procedure_id="bench-power-check",
        passed=True,
        captured_at="2026-08-11T12:00:00Z",
        operator="test-operator",
        measured_values={"logic_voltage_v": 5.0},
        acceptance_criteria={"logic_voltage_v": {"min": 4.75, "max": 5.25}},
        artifact_hashes={"controller-design": ARTIFACT_HASH},
        raw_refs=["evidence://physical-status/bench-power.csv"],
    )
    envelope = build_physical_evidence_envelope(
        envelope_id="env-1",
        record=record,
        raw_files=[
            {
                "ref": "evidence://physical-status/bench-power.csv",
                "content_hash": RAW_HASH,
                "media_type": "text/csv",
                "size_bytes": 128,
                "captured_at": "2026-08-11T12:00:00Z",
            }
        ],
        created_at="2026-08-11T12:01:00Z",
        created_by="test-operator",
    ).model_dump(mode="json")

    decision = AuthorizationDecision(
        authorization_id="auth-1",
        status=AuthorizationStatus.AUTHORIZED,
        scope=AuthorizationScope(
            scope_id="scope-1",
            project_id="physical-status",
            candidate_revision="candidate-1",
            operations=[PhysicalOperation.BENCH_POWER],
            target_ids=["controller"],
            artifact_hashes={"controller-design": ARTIFACT_HASH},
            operating_envelope={"logic_voltage_v": 5.0, "current_limit_a": 0.5},
            required_evidence_kinds=[PhysicalEvidenceKind.ELECTRICAL],
        ),
        reviewer="test-reviewer",
        reviewed_at="2026-08-11T12:05:00Z",
        evidence_ids=["evidence-1"],
        reason="Bench-power evidence meets the bounded test scope.",
    )
    ledger = build_authorization_ledger_entry(
        entry_id="entry-1",
        decision=decision,
        recorded_at="2026-08-11T12:06:00Z",
        recorded_by="test-reviewer",
    ).model_dump(mode="json")

    blockers: list[str] = []
    ledger_blockers: list[str] = []
    if not valid:
        envelope["envelope_hash"] = "sha256:" + "0" * 64
        blockers.append("Physical evidence envelope env-1 hash does not match its content.")

    return {
        "applicable": valid,
        "blockers": blockers,
        "warnings": [],
        "envelopes": [envelope],
        "ledger_entries": [ledger],
        "ledger_assessment": {
            "valid": not ledger_blockers,
            "entry_count": 1,
            "latest_entry_id": "entry-1",
            "latest_entry_hash": ledger["entry_hash"],
            "applicable_authorization_id": "auth-1" if valid else None,
            "applicable_scope_id": "scope-1" if valid else None,
            "blockers": ledger_blockers,
            "warnings": [],
            "metadata": {
                "tamper_evident_hash_chain": True,
                "automatic_authorization": False,
                "authorization_carries_across_revisions": False,
            },
        },
        "physical_package": {
            "assessment": {
                "project_id": "physical-status",
                "candidate_revision": "candidate-1",
                "status": "authorized" if valid else "blocked",
                "applicable": valid,
                "authorized_operations": ["bench_power"] if valid else [],
                "accepted_evidence_ids": ["evidence-1"] if valid else [],
                "blockers": blockers,
                "warnings": [],
                "artifact_hashes": {"controller-design": ARTIFACT_HASH},
                "metadata": {"automatic_authorization": False},
            }
        },
    }


def _plan(*, valid: bool) -> dict:
    blockers = [] if valid else ["Physical evidence envelope env-1 hash does not match its content."]
    return {
        "candidate_revision": "candidate-1",
        "machine_project": {
            "project_id": "physical-status",
            "components": [],
            "interfaces": [],
            "artifacts": [
                {
                    "artifact_id": "controller-design",
                    "kind": "schematic",
                    "ref": "design/controller.kicad_sch",
                    "authority": "verified",
                    "metadata": {"content_hash": ARTIFACT_HASH},
                }
            ],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {},
        },
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {"checks": []},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
        "audited_physical_evidence": _audited_physical_evidence(valid=valid),
        "scoped_release_assessment": {
            "allowed": valid,
            "allowed_operations": ["bench_power"] if valid else [],
            "blockers": blockers,
        },
        # Deliberately stale: the compiler must ignore this cached summary.
        "engineering_status": {
            "project_id": "physical-status",
            "overall_status": "candidate",
            "current_phase": "release",
            "blockers": [],
            "advisories": [],
            "blocker_groups": {},
            "next_actions": [],
            "summary": {},
            "metadata": {},
        },
    }


def test_tampered_audit_rebuilds_release_blocker_and_action() -> None:
    status = build_engineering_status(_plan(valid=False))

    assert status.overall_status == "blocked"
    assert status.current_phase == "release"
    blocker = next(
        row for row in status.blockers
        if row.blocker_id == "physical-authorization-scope"
    )
    assert "envelope" in blocker.message.lower()
    assert "valid authorization ledger" in blocker.required_inputs
    assert status.next_actions[0].category == "release"
    assert status.summary["physical_scope_authorized"] is False
    assert status.summary["authorization_ledger_valid"] is True
    assert status.metadata["authorized_operations"] == []
    assert status.metadata["automatic_authorization"] is False


def test_valid_audit_rebuilds_authorized_scope_without_broad_flags() -> None:
    status = build_engineering_status(_plan(valid=True))

    assert status.blockers == []
    assert status.summary["physical_scope_authorized"] is True
    assert status.summary["authorized_operation_count"] == 1
    assert status.summary["physical_evidence_envelope_count"] == 1
    assert status.metadata["authorized_operations"] == ["bench_power"]
    assert status.metadata["power_on_authorized"] is False
    assert status.next_actions[0].action_id == "next-release"


def test_revision_diff_rebuilds_physical_blocker_instead_of_trusting_cache() -> None:
    report = diff_engineering_revisions(
        _plan(valid=True),
        _plan(valid=False),
        base_revision="r1",
        candidate_revision="r2",
    )

    assert {
        row.blocker_id for row in report.opened_blockers
    } == {"physical-authorization-scope"}
    assert report.candidate_status.overall_status == "blocked"
    assert report.summary["opened_blocker_count"] == 1
