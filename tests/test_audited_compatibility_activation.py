from __future__ import annotations

from hardware_splicer.engineering_action import prepare_engineering_action
from hardware_splicer.engineering_revision_diff import diff_engineering_revisions


def _plan(*, envelope_hash: str, ledger_valid: bool, applicable: bool) -> dict:
    blockers = [] if applicable else ["Evidence envelope hash does not match its content."]
    return {
        "machine_project": {
            "project_id": "audit-compat",
            "components": [],
            "interfaces": [],
            "artifacts": [],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {},
            "metadata": {},
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
            "applicable": applicable,
            "blockers": blockers,
            "warnings": [],
            "envelopes": [
                {
                    "envelope_id": "env-1",
                    "envelope_hash": envelope_hash,
                    "record": {"evidence_id": "rail-test"},
                    "raw_files": [{"ref": "lab://rail.csv", "content_hash": "sha256:raw"}],
                    "created_at": "2026-08-04T02:00:00Z",
                    "created_by": "operator",
                }
            ],
            "ledger_entries": [
                {
                    "entry_id": "entry-1",
                    "entry_hash": "sha256:entry",
                    "previous_entry_hash": None,
                    "recorded_at": "2026-08-04T02:30:00Z",
                    "recorded_by": "release-clerk",
                    "decision": {
                        "authorization_id": "auth-1",
                        "status": "authorized" if applicable else "revoked",
                        "scope": {"scope_id": "scope-1", "candidate_revision": "r1"},
                    },
                }
            ],
            "ledger_assessment": {
                "valid": ledger_valid,
                "blockers": [] if ledger_valid else ["Ledger chain is invalid."],
                "warnings": [],
            },
            "physical_package": {
                "assessment": {
                    "applicable": applicable,
                    "authorized_operations": ["bench_power"] if applicable else [],
                    "blockers": blockers,
                    "warnings": [],
                }
            },
        },
        "scoped_release_assessment": {
            "allowed": applicable,
            "allowed_operations": ["bench_power"] if applicable else [],
            "blockers": blockers,
        },
    }


def test_release_action_contains_audited_routes_and_state() -> None:
    prepared = prepare_engineering_action(
        _plan(envelope_hash="sha256:bad", ledger_valid=False, applicable=False)
    )

    assert prepared.action.category == "release"
    assert prepared.status == "blocked"
    assert prepared.payload["audited_physical_evidence"]["applicable"] is False
    assert prepared.payload["authorization_ledger_valid"] is False
    assert prepared.payload["evidence_envelope_count"] == 1
    assert prepared.payload["audited_physical_assess_route"].endswith("/audited-assess")
    assert prepared.payload["audited_apply_save_route"].endswith("/audited-apply-save")
    assert prepared.payload["tamper_evident_envelopes_required"] is True
    assert prepared.payload["automatic_authorization"] is False


def test_revision_diff_includes_envelopes_ledger_and_audited_assessment() -> None:
    report = diff_engineering_revisions(
        _plan(envelope_hash="sha256:old", ledger_valid=True, applicable=True),
        _plan(envelope_hash="sha256:new", ledger_valid=False, applicable=False),
        base_revision="r1",
        candidate_revision="r2",
    )

    record_ids = {
        row["physical_record_id"] for row in report.physical_authorization_changes
    }
    assert "evidence_envelope:env-1" in record_ids
    assert "authorization_ledger:entry-1" in record_ids
    assert "authorization_ledger_assessment" in record_ids
    assert "audited_physical_assessment" in record_ids
    assert report.summary["physical_authorization_change_count"] >= 4


def test_nested_authority_scan_is_active_from_package_import() -> None:
    candidate = _plan(
        envelope_hash="sha256:current",
        ledger_valid=True,
        applicable=True,
    )
    candidate["machine_project"]["metadata"]["power_on_authorized"] = True
    candidate["machine_project"]["discipline_payloads"] = {
        "unsafe": {"motion_authorized": True}
    }

    report = diff_engineering_revisions(candidate, candidate)

    assert any(
        "machine_project.metadata.power_on_authorized=true" in row
        for row in report.authority_regressions
    )
    assert any(
        "machine_project.discipline_payloads.unsafe.motion_authorized=true" in row
        for row in report.authority_regressions
    )
    assert report.metadata["physical_authority_unchanged"] is False
