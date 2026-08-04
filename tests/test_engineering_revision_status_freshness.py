from __future__ import annotations

from hardware_splicer.engineering_revision_diff import diff_engineering_revisions


def _plan(*, failing: bool, cached_status: str) -> dict:
    findings = (
        [
            {
                "finding_id": "analysis-current",
                "category": "power",
                "status": "fail",
                "message": "Current margin is negative.",
                "target_ids": ["power"],
                "missing_inputs": [],
                "blocking": True,
            }
        ]
        if failing
        else []
    )
    return {
        "machine_project": {
            "project_id": "freshness-project",
            "components": [],
            "interfaces": [],
            "artifacts": [],
            "evidence": [],
            "verifications": [],
            "discipline_payloads": {},
        },
        "engineering_status": {
            "schema_version": "hardware_splicer.engineering_status.v1",
            "project_id": "freshness-project",
            "overall_status": cached_status,
            "current_phase": "release",
            "blockers": [],
            "advisories": [],
            "blocker_groups": {},
            "next_actions": [],
            "next_action_id": None,
            "summary": {},
            "metadata": {},
        },
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"links": [], "joints": [], "actuators": [], "sensors": [], "unresolved": []},
        "engineering_analysis": {"findings": findings},
        "manufacturing_closure": {"checks": []},
        "manufacturing_projection": {},
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "blocked" if failing else "candidate"},
    }


def test_revision_diff_recomputes_status_instead_of_trusting_cache() -> None:
    base = _plan(failing=True, cached_status="candidate")
    candidate = _plan(failing=False, cached_status="blocked")

    report = diff_engineering_revisions(base, candidate)

    assert [row.blocker_id for row in report.resolved_blockers] == ["analysis-current"]
    assert report.candidate_status.overall_status == "candidate"
    assert report.candidate_status.next_action_id == "next-release"
