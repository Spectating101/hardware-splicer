from __future__ import annotations

from hardware_splicer.engineering_revision_diff import diff_engineering_revisions
from hardware_splicer.machine_project import MachineProject
from hardware_splicer.mechanical_geometry_plan_update import apply_mechanical_geometry_to_plan
from hardware_splicer.step_geometry import build_mechanical_geometry_report, parse_step_model


STEP_R1 = """ISO-10303-21;
HEADER;
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=PRODUCT('fixture','Fixture','',());
#2=SI_UNIT(.MILLI.,.METRE.);
#3=CARTESIAN_POINT('',(0.0,0.0,0.0));
#4=CARTESIAN_POINT('',(100.0,50.0,10.0));
ENDSEC;
END-ISO-10303-21;
"""

STEP_R2 = STEP_R1.replace("100.0,50.0,10.0", "110.0,50.0,10.0")


def _plan() -> dict:
    project = MachineProject.model_validate(
        {
            "project_id": "mechanical-plan",
            "name": "Mechanical plan",
            "purpose": "Track STEP and mount identity.",
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


def _report(step: str, *, spacing: float = 40.0):
    models = [
        parse_step_model(step, source_id="left.step", model_id="left"),
        parse_step_model(step, source_id="right.step", model_id="right"),
    ]
    mounts = [
        {
            "interface_id": "left-mount",
            "part_id": "left-part",
            "cad_model_id": "left",
            "mount_type": "flat_flange",
            "mates_with": "right-mount",
            "datum_frame": "left-frame",
            "origin_mm": [10.0, 10.0, 5.0],
            "normal": [0.0, 0.0, 1.0],
            "hole_pattern": {
                "count": 4,
                "spacing_x_mm": 40.0,
                "spacing_y_mm": 20.0,
                "hole_diameter_mm": 3.2,
            },
            "fastener_spec": "M3",
        },
        {
            "interface_id": "right-mount",
            "part_id": "right-part",
            "cad_model_id": "right",
            "mount_type": "flat_flange",
            "mates_with": "left-mount",
            "datum_frame": "right-frame",
            "origin_mm": [10.0, 10.0, 5.0],
            "normal": [0.0, 0.0, -1.0],
            "hole_pattern": {
                "count": 4,
                "spacing_x_mm": spacing,
                "spacing_y_mm": 20.0,
                "hole_diameter_mm": 3.2,
            },
            "fastener_spec": "M3",
        },
    ]
    return build_mechanical_geometry_report(
        project_id="mechanical-plan",
        models=models,
        mounts=mounts,
    )


def test_candidate_geometry_attaches_step_artifacts_without_authority() -> None:
    updated = apply_mechanical_geometry_to_plan(_plan(), _report(STEP_R1))
    project = MachineProject.model_validate(updated["machine_project"])
    step_artifacts = [row for row in project.artifacts if row.kind == "step_model"]

    assert len(step_artifacts) == 2
    assert {row.artifact_id for row in step_artifacts} == {
        "step-model-left",
        "step-model-right",
    }
    assert all(row.metadata["content_hash"].startswith("sha256:") for row in step_artifacts)
    assert updated["mechanical_geometry"]["status"] == "candidate"
    assert updated["engineering_readiness"]["mechanical_geometry_blocker_count"] == 0
    assert updated["engineering_readiness"]["full_brep_validation"] is False
    assert updated["engineering_readiness"]["collision_analysis"] is False
    assert updated["engineering_readiness"]["fabrication_authorized"] is False
    assert updated["scenario"]["mechanical_geometry_acceptance"]["fabrication_authorized"] is False


def test_mechanical_fit_failure_enters_unified_manufacturing_queue() -> None:
    updated = apply_mechanical_geometry_to_plan(_plan(), _report(STEP_R1, spacing=43.0))
    status = updated["engineering_status"]

    assert updated["mechanical_geometry"]["status"] == "blocked"
    assert status["overall_status"] == "blocked"
    assert status["current_phase"] == "manufacturing"
    mechanical = [
        row for row in status["blockers"]
        if row["blocker_id"].startswith("mechanical-mount-pair-")
    ]
    assert len(mechanical) == 1
    assert "spacing_x_mm" in mechanical[0]["message"]
    assert mechanical[0]["blocker_id"] in status["blocker_groups"]["manufacturing"]


def test_reapplying_same_report_is_idempotent() -> None:
    once = apply_mechanical_geometry_to_plan(_plan(), _report(STEP_R1))
    twice = apply_mechanical_geometry_to_plan(once, _report(STEP_R1))
    project = MachineProject.model_validate(twice["machine_project"])

    step_artifacts = [row for row in project.artifacts if row.kind == "step_model"]
    assert len(step_artifacts) == 2
    assert len({row.artifact_id for row in step_artifacts}) == 2
    assert twice["engineering_status"]["summary"]["mechanical_geometry_blocker_count"] == 0


def test_changed_step_hash_is_visible_in_canonical_revision_diff() -> None:
    base = apply_mechanical_geometry_to_plan(_plan(), _report(STEP_R1))
    candidate = apply_mechanical_geometry_to_plan(_plan(), _report(STEP_R2))

    report = diff_engineering_revisions(
        base,
        candidate,
        base_revision="r1",
        candidate_revision="r2",
    )

    step_changes = [
        row for row in report.artifact_changes
        if row["artifact_id"] in {"step-model-left", "step-model-right"}
    ]
    assert len(step_changes) == 2
    assert all(row["change"] == "changed" for row in step_changes)
    assert all(row["base"]["content_hash"] != row["candidate"]["content_hash"] for row in step_changes)
