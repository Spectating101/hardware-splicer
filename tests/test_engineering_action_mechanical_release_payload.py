from __future__ import annotations

from hardware_splicer.engineering_action import prepare_engineering_action
from hardware_splicer.machine_project import MachineProject


def _base_plan() -> dict:
    project = MachineProject.model_validate(
        {
            "project_id": "action-context",
            "name": "Action context",
            "purpose": "Verify prepared action context.",
        }
    )
    return {
        "machine_project": project.model_dump(mode="json"),
        "engineering_source_graph": {"unresolved_source_ids": [], "conflicts": []},
        "robot_topology": {"topology_id": "generic", "unresolved": []},
        "engineering_analysis": {"findings": []},
        "manufacturing_closure": {
            "schema_version": "hardware_splicer.manufacturing_closure.v1",
            "project_id": "action-context",
            "checks": [],
            "identity_matrix": {},
            "required_evidence": [],
            "metadata": {},
        },
        "engineering_execution_plan": {"unresolved": []},
        "change_impact": {"impacts": [], "unresolved": []},
        "missing_info": [],
        "engineering_readiness": {"status": "candidate"},
    }


def test_manufacturing_action_includes_geometry_fit_and_routes() -> None:
    plan = _base_plan()
    plan["mechanical_geometry"] = {"project_id": "action-context", "status": "candidate"}
    plan["mechanical_fit"] = {"project_id": "action-context", "status": "blocked"}
    plan["manufacturing_closure"]["checks"] = [
        {
            "check_id": "mechanical-fit-clearance",
            "category": "mechanical_aabb_clearance",
            "status": "fail",
            "severity": "error",
            "message": "Clearance is below requirement.",
            "source_ids": [],
            "target_ids": ["arm", "enclosure"],
            "unresolved_fields": [],
            "evidence_ids": [],
            "metadata": {"source_kind": "mechanical_fit"},
        }
    ]

    prepared = prepare_engineering_action(plan)

    assert prepared.action.category == "manufacturing"
    assert prepared.status == "blocked"
    assert prepared.payload["mechanical_geometry"]["status"] == "candidate"
    assert prepared.payload["mechanical_fit"]["status"] == "blocked"
    assert prepared.payload["fit_check_route"] == "/v1/engineering/mechanical/fit/check"
    assert prepared.payload["fit_apply_route"] == "/v1/engineering/mechanical/fit/apply"
    assert prepared.payload["full_brep_collision"] is False
    assert prepared.payload["fabrication_authorized"] is False


def test_release_action_surfaces_scoped_physical_assessment() -> None:
    plan = _base_plan()
    plan["physical_evidence_package"] = {
        "project_id": "action-context",
        "candidate_revision": "r2",
        "evidence": [],
    }
    plan["scoped_release_assessment"] = {
        "authorized": False,
        "blockers": [{"message": "Calibrated current measurement is missing."}],
        "authorized_operations": [],
    }

    prepared = prepare_engineering_action(plan)

    assert prepared.action.category == "release"
    assert prepared.status == "blocked"
    assert prepared.payload["physical_evidence_package"]["candidate_revision"] == "r2"
    assert prepared.payload["scoped_release_assessment"]["authorized"] is False
    assert prepared.payload["physical_release_assess_route"] == "/v1/engineering/physical-evidence/release-assess"
    assert prepared.payload["automatic_authorization"] is False
    assert "Calibrated current measurement is missing." in prepared.blockers
