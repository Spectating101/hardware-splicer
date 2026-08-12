from __future__ import annotations

import json

import pytest

from hardware_splicer.robot_arm_design import (
    RobotArmDesignError,
    evaluate_robot_arm_design,
    parse_robot_arm_design,
    propose_robot_arm_design,
)
from hardware_splicer.robot_arm_experiment import (
    robot_arm_inventory,
    robot_arm_requirements,
    robot_arm_source_ids,
    run_robot_arm_experiment,
)


def _candidate(actuator_ids: list[str | None]) -> dict:
    return {
        "reasoning": "typed test candidate",
        "joints": [
            {
                "joint_id": "base-yaw",
                "joint_type": "revolute",
                "axis": [0, 0, 1],
                "link_length_mm": 100,
                "actuator_part_id": actuator_ids[0],
                "lower_limit_deg": -160,
                "upper_limit_deg": 160,
            },
            {
                "joint_id": "shoulder-pitch",
                "joint_type": "revolute",
                "axis": [0, 1, 0],
                "link_length_mm": 150,
                "actuator_part_id": actuator_ids[1],
                "lower_limit_deg": -90,
                "upper_limit_deg": 120,
            },
            {
                "joint_id": "elbow-pitch",
                "joint_type": "revolute",
                "axis": [0, 1, 0],
                "link_length_mm": 140,
                "actuator_part_id": actuator_ids[2],
                "lower_limit_deg": -135,
                "upper_limit_deg": 135,
            },
            {
                "joint_id": "wrist-pitch",
                "joint_type": "revolute",
                "axis": [0, 1, 0],
                "link_length_mm": 80,
                "actuator_part_id": actuator_ids[3],
                "lower_limit_deg": -90,
                "upper_limit_deg": 90,
            },
        ],
        "end_effector": "parallel_gripper_candidate",
        "source_ids": robot_arm_source_ids(),
        "unresolved_questions": [],
        "authority_effect": "none",
        "automatic_execution": False,
    }


def test_robot_arm_parser_rejects_invented_actuator_identity() -> None:
    body = _candidate(
        [
            "invented-servo",
            "actuator-shoulder-heavy",
            "actuator-elbow-medium",
            "actuator-wrist-light",
        ]
    )

    with pytest.raises(RobotArmDesignError, match="absent from visible inventory"):
        parse_robot_arm_design(
            body,
            inventory=robot_arm_inventory(),
            known_source_ids=robot_arm_source_ids(),
        )


def test_robot_arm_parser_rejects_invented_source_identity() -> None:
    body = _candidate(
        [
            "actuator-base-heavy",
            "actuator-shoulder-heavy",
            "actuator-elbow-medium",
            "actuator-wrist-light",
        ]
    )
    body["source_ids"] = ["src-arm-requirements", "invented-source"]

    with pytest.raises(RobotArmDesignError, match="absent from visible evidence"):
        parse_robot_arm_design(
            body,
            inventory=robot_arm_inventory(),
            known_source_ids=robot_arm_source_ids(),
        )


def test_balanced_arm_clears_bounded_checks_but_stays_motion_blocked() -> None:
    proposal = parse_robot_arm_design(
        _candidate(
            [
                "actuator-base-heavy",
                "actuator-shoulder-heavy",
                "actuator-elbow-medium",
                "actuator-wrist-light",
            ]
        ),
        inventory=robot_arm_inventory(),
        known_source_ids=robot_arm_source_ids(),
    )
    evaluation = evaluate_robot_arm_design(
        proposal,
        requirements=robot_arm_requirements(),
        inventory=robot_arm_inventory(),
    )

    assert evaluation.status == "blocked"
    assert evaluation.motion_authorized is False
    assert evaluation.fabrication_authorized is False
    reach = next(row for row in evaluation.findings if row.code == "GEOMETRIC_REACH_UPPER_BOUND")
    assert reach.status == "pass"
    torque = [row for row in evaluation.findings if row.code == "PAYLOAD_ONLY_TORQUE_BOUND"]
    assert len(torque) == 4
    assert all(row.status == "pass" for row in torque)
    assert any(row.code == "LINK_SELF_WEIGHT_TORQUE_UNRESOLVED" for row in evaluation.findings)
    assert any(row.code == "PHYSICAL_VALIDATION_REQUIRED" for row in evaluation.findings)
    assert evaluation.summary["full_kinematics_verified"] is False
    assert evaluation.summary["full_dynamics_verified"] is False


def test_underpowered_arm_fails_payload_only_torque_bound() -> None:
    proposal = parse_robot_arm_design(
        _candidate(["actuator-weak"] * 4),
        inventory=robot_arm_inventory(),
        known_source_ids=robot_arm_source_ids(),
    )
    evaluation = evaluate_robot_arm_design(
        proposal,
        requirements=robot_arm_requirements(),
        inventory=robot_arm_inventory(),
    )

    assert evaluation.status == "failed"
    failed = [
        row
        for row in evaluation.findings
        if row.code == "PAYLOAD_ONLY_TORQUE_BOUND" and row.status == "fail"
    ]
    assert failed
    assert evaluation.motion_authorized is False


def test_unresolved_actuator_identity_is_not_substituted() -> None:
    proposal = parse_robot_arm_design(
        _candidate([None, None, None, None]),
        inventory=robot_arm_inventory(),
        known_source_ids=robot_arm_source_ids(),
    )
    evaluation = evaluate_robot_arm_design(
        proposal,
        requirements=robot_arm_requirements(),
        inventory=robot_arm_inventory(),
    )

    assert evaluation.status == "blocked"
    assert sum(row.code == "ACTUATOR_IDENTITY_UNRESOLVED" for row in evaluation.findings) == 4
    topology = evaluation.topology
    assert all(row["source_part_id"] is None for row in topology["actuators"])


def test_model_proposal_is_typed_and_cannot_auto_execute() -> None:
    body = _candidate(
        [
            "actuator-base-heavy",
            "actuator-shoulder-heavy",
            "actuator-elbow-medium",
            "actuator-wrist-light",
        ]
    )

    def fake_llm(prompt: str, **kwargs: object) -> dict:
        assert "required_reach_mm" in prompt
        assert "actuator-base-heavy" in prompt
        return {
            "ok": True,
            "provider": "test",
            "model": "typed-arm",
            "content": json.dumps(body),
            "usage": {},
        }

    proposal = propose_robot_arm_design(
        "Design the declared tabletop arm.",
        requirements=robot_arm_requirements(),
        inventory=robot_arm_inventory(),
        source_ids=robot_arm_source_ids(),
        llm_callable=fake_llm,
    )

    assert len(proposal.joints) == 4
    assert proposal.authority_effect == "none"
    assert proposal.automatic_execution is False


def test_robot_arm_experiment_detects_old_hidden_default_and_new_typed_loop() -> None:
    report = run_robot_arm_experiment()

    assert report["diagnostic_pass"] is True
    assert report["design_ready"] is False
    assert report["motion_ready"] is False
    assert report["checks"]["typed_balanced_proposal_accepted"] is True
    assert report["checks"]["balanced_reach_upper_bound_passes"] is True
    assert report["checks"]["balanced_payload_only_torque_bounds_pass"] is True
    assert report["checks"]["underpowered_design_rejected_by_engineering_check"] is True
    assert report["checks"]["invented_actuator_identity_rejected"] is True
    assert report["checks"]["historical_hidden_arm_default_detected"] is True
    probe = report["historical_canonical_builder_probe"]
    assert probe["diagnosis"] == "SCRIPT_BRAIN"
    assert probe["joint_count_without_declared_dof"] == 5
    assert probe["motion_authorized"] is False
