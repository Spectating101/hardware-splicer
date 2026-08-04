from __future__ import annotations

from hardware_splicer.engineering_revision_diff import diff_engineering_revisions
from hardware_splicer.engineering_status import build_engineering_status


def _plan(*, valid: bool) -> dict:
    blockers = [] if valid else ["Physical evidence envelope hash does not match its content."]
    return {
        "machine_project": {
            "project_id": "physical-status",
            "components": [],
            "interfaces": [],
            "artifacts": [],
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
        "audited_physical_evidence": {
            "applicable": valid,
            "blockers": blockers,
            "warnings": [],
            "envelopes": [{"envelope_id": "env-1"}],
            "ledger_entries": [{"entry_id": "entry-1"}],
            "ledger_assessment": {
                "valid": valid,
                "blockers": [] if valid else ["Authorization ledger entry is invalid."],
                "warnings": [],
            },
            "physical_package": {
                "assessment": {
                    "applicable": valid,
                    "authorized_operations": ["bench_power"] if valid else [],
                    "blockers": blockers,
                    "warnings": [],
                }
            },
        },
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
    assert "envelope hash" in blocker.message
    assert "valid authorization ledger" in blocker.required_inputs
    assert status.next_actions[0].category == "release"
    assert status.summary["physical_scope_authorized"] is False
    assert status.summary["authorization_ledger_valid"] is False
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
