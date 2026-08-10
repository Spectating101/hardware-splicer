from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from hardware_splicer.robot_arm_design import parse_robot_arm_design
from hardware_splicer.robot_arm_experiment import robot_arm_inventory
from hardware_splicer.robot_arm_kinematics import generate_robot_arm_urdf, run_pybullet_kinematics_oracle
from hardware_splicer.robot_arm_reference_benchmark import reference_source_ids


_BUNDLE = Path("experiments/robot_arm/reference_benchmark_gpt56_sol_proposals.json")


def _bundle() -> dict:
    return json.loads(_BUNDLE.read_text(encoding="utf-8"))


def _proposal(name: str, *, allow_sources: bool):
    return parse_robot_arm_design(
        _bundle()[name],
        inventory=robot_arm_inventory(),
        known_source_ids=reference_source_ids() if allow_sources else [],
    )


def test_generated_urdf_is_kinematics_only_and_preserves_joint_structure() -> None:
    proposal = _proposal("blind_reconstruction", allow_sources=False)
    artifact = generate_robot_arm_urdf(proposal)
    root = ET.fromstring(artifact.text)

    joints = root.findall("joint")
    moving = [row for row in joints if row.attrib["type"] != "fixed"]
    assert artifact.joint_count == 4
    assert [row.attrib["name"] for row in moving] == [row.joint_id for row in proposal.joints]
    assert abs(artifact.chain_length_m - 0.4) < 1e-9
    assert root.find(".//inertial") is None
    assert artifact.collision_geometry_authority == "proxy_only"
    assert artifact.physical_authority == "none"


def test_pybullet_blind_lane_runs_fk_ik_and_unreachable_probe(tmp_path: Path) -> None:
    # The general Core Diagnostics lane intentionally installs only the base/dev package.
    # The dedicated Robot Arm Kinematics workflow owns the positive PyBullet execution bar.
    pytest.importorskip("pybullet")

    proposal = _proposal("blind_reconstruction", allow_sources=False)
    artifact = generate_robot_arm_urdf(proposal)
    urdf = tmp_path / "blind.urdf"
    urdf.write_text(artifact.text, encoding="utf-8")

    result = run_pybullet_kinematics_oracle(
        proposal,
        urdf_path=str(urdf),
        workspace_samples=64,
        collision_samples=32,
    )

    assert result["status"] == "pass"
    assert result["urdf_load_pass"] is True
    assert result["loaded_movable_joint_count"] == 4
    assert result["zero_pose_chain_error_mm"] <= 0.05
    assert result["ik_within_5mm"] is True
    assert result["ik_joint_limits_respected"] is True
    assert result["unreachable_target_not_falsely_closed"] is True
    assert result["proxy_collision_sample_count"] == 32
    assert result["collision_geometry_authority"] == "proxy_only"
    assert result["motion_authorized"] is False


def test_mutation_can_be_kinematically_valid_while_actuator_identity_stays_unresolved(tmp_path: Path) -> None:
    pytest.importorskip("pybullet")

    proposal = _proposal("mutated_requirement", allow_sources=True)
    shoulder = next(row for row in proposal.joints if row.joint_id == "shoulder-pitch")
    assert shoulder.actuator_part_id is None

    artifact = generate_robot_arm_urdf(proposal)
    urdf = tmp_path / "mutation.urdf"
    urdf.write_text(artifact.text, encoding="utf-8")
    result = run_pybullet_kinematics_oracle(
        proposal,
        urdf_path=str(urdf),
        workspace_samples=64,
        collision_samples=32,
    )

    assert result["ik_within_5mm"] is True
    assert shoulder.actuator_part_id is None
    assert result["motion_authorized"] is False
    assert result["physical_authority"] == "none"
