from __future__ import annotations

import pytest

from hardware_splicer.machine_project import MachineProject
from hardware_splicer.mechanical_fit_plan_update import apply_mechanical_fit_to_plan


def _plan() -> dict:
    project = MachineProject.model_validate(
        {
            "project_id": "fit-plan",
            "name": "Fit plan",
            "purpose": "Track bounded mechanical fit closure.",
        }
    )
    return {
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


def _report(*, status: str = "fail", project_id: str = "fit-plan") -> dict:
    blocked = status != "pass"
    return {
        "project_id": project_id,
        "geometry_report_schema": "hardware_splicer.mechanical_geometry.v1",
        "status": "blocked" if blocked else "candidate",
        "checks": [
            {
                "check_id": "clearance-arm-enclosure",
                "category": "aabb_clearance",
                "status": status,
                "message": (
                    "AABB clearance is below the declared requirement."
                    if blocked
                    else "AABB clearance meets the declared requirement."
                ),
                "target_ids": ["arm", "enclosure"],
                "unresolved_fields": ["relative_transform"] if status == "unknown" else [],
                "blocking": True,
                "metadata": {"aabb_only": True},
            }
        ],
        "metadata": {
            "full_brep_collision": False,
            "structural_analysis": False,
            "thread_strength_verified": False,
            "fabrication_authorized": False,
        },
    }


def test_fit_failure_rebuilds_manufacturing_status_and_next_action() -> None:
    updated = apply_mechanical_fit_to_plan(_plan(), _report())
    status = updated["engineering_status"]

    assert status["overall_status"] == "blocked"
    assert status["current_phase"] == "manufacturing"
    blocker = next(
        row for row in status["blockers"]
        if row["blocker_id"] == "mechanical-fit-clearance-arm-enclosure"
    )
    assert blocker["target_ids"] == ["arm", "enclosure"]
    assert status["next_actions"][0]["category"] == "manufacturing"
    assert status["next_actions"][0]["route"] == "/v1/engineering/manufacturing-closure"
    assert updated["engineering_readiness"]["mechanical_fit_blocker_count"] == 1
    assert updated["scenario"]["mechanical_fit_acceptance"]["fabrication_authorized"] is False
    assert updated["scenario"]["compile_spec"]["mechanical_fit"]["status"] == "blocked"


def test_unknown_fit_remains_blocking_and_requests_missing_transform() -> None:
    updated = apply_mechanical_fit_to_plan(_plan(), _report(status="unknown"))
    blocker = next(
        row for row in updated["engineering_status"]["blockers"]
        if row["blocker_id"] == "mechanical-fit-clearance-arm-enclosure"
    )

    assert blocker["required_inputs"] == ["relative_transform"]
    assert updated["engineering_readiness"]["status"] == "blocked"


def test_reapplying_fit_report_replaces_synthetic_closure_rows() -> None:
    once = apply_mechanical_fit_to_plan(_plan(), _report())
    twice = apply_mechanical_fit_to_plan(once, _report(status="pass"))
    fit_rows = [
        row for row in twice["manufacturing_closure"]["checks"]
        if (row.get("metadata") or {}).get("source_kind") == "mechanical_fit"
    ]

    assert len(fit_rows) == 1
    assert fit_rows[0]["status"] == "pass"
    assert not any(
        row["blocker_id"] == "mechanical-fit-clearance-arm-enclosure"
        for row in twice["engineering_status"]["blockers"]
    )
    assert twice["engineering_readiness"]["mechanical_fit_blocker_count"] == 0


def test_fit_report_must_match_machine_project_identity() -> None:
    with pytest.raises(ValueError, match="project_id does not match"):
        apply_mechanical_fit_to_plan(_plan(), _report(project_id="other"))
