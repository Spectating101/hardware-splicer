from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.machine_project import AuthorityState
from hardware_splicer.machine_project_compile_adapter import machine_project_from_compile_spec


REPO_ROOT = Path(__file__).resolve().parents[1]


def rover_spec() -> dict:
    return json.loads(
        (REPO_ROOT / "examples" / "hardware_splicer_robotics_platform_rover_demo.json").read_text(
            encoding="utf-8"
        )
    )


def test_existing_rover_compile_spec_projects_into_one_machine_model() -> None:
    project = machine_project_from_compile_spec(rover_spec())

    assert project.project_id == "robotics_platform_rover_demo"
    assert project.purpose == "indoor inspection rover prototype"
    assert {row.subsystem_id for row in project.subsystems} >= {
        "system",
        "electrical-system",
        "mechanical-system",
        "robotics-system",
        "firmware-control",
        "verification-system",
    }
    component_ids = {row.component_id for row in project.components}
    assert "board-main_ctrl" in component_ids
    assert "actuator-left_drive_motor" in component_ids
    assert "actuator-right_drive_motor" in component_ids
    assert "sensor-front_range" in component_ids
    assert "firmware-main_ctrl" in component_ids
    assert project.interfaces == []
    assert project.metadata["interfaces_inferred"] is False
    assert project.discipline_payloads["hardware_compile_spec"]["robotics_project"]["platform"]
    assert not [issue for issue in project.traceability_issues() if issue.code == "invalid_ref"]


def test_existing_capture_packets_become_evidence_and_verification() -> None:
    project = machine_project_from_compile_spec(rover_spec())

    evidence_ids = {row.evidence_id for row in project.evidence}
    verification_ids = {row.verification_id for row in project.verifications}
    assert evidence_ids >= {
        "evidence-mechanical_measurement_capture",
        "evidence-mechanical_bench_capture",
        "evidence-robotics_bench_capture",
        "evidence-integrated_bench_capture",
        "evidence-field_validation",
    }
    assert verification_ids >= {
        "verify-mechanical_measurement_capture",
        "verify-integrated_bench_capture",
        "verify-field_validation",
    }
    assert all(row.status.value == "passed" for row in project.verifications)
    assert all(row.simulated is False for row in project.evidence)
    assert any(row.authority == AuthorityState.MEASURED for row in project.evidence)


def test_reviewed_release_documents_do_not_auto_authorize_the_machine() -> None:
    project = machine_project_from_compile_spec(rover_spec())

    release_artifacts = [row for row in project.artifacts if row.kind.endswith("_release")]
    assert release_artifacts
    assert all(row.authority == AuthorityState.VERIFIED for row in release_artifacts)
    assert all(row.authority != AuthorityState.AUTHORIZED for row in project.artifacts)

    assessment = project.assess_release()
    assert assessment.allowed is False
    assert {row.code for row in assessment.blockers} >= {
        "unverified_requirement",
        "safety_not_closed",
    }


def test_compile_spec_adapter_preserves_board_sources_as_declared_artifacts() -> None:
    project = machine_project_from_compile_spec(rover_spec())

    board_artifact = next(row for row in project.artifacts if row.artifact_id == "artifact-board-source-main_ctrl")
    assert board_artifact.ref == "main_ctrl_esp32_servo.net"
    assert board_artifact.authority == AuthorityState.DECLARED
