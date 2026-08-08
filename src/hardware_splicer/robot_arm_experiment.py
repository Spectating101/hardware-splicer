"""Robot-arm engineering experiment for the model-first Hardware Splicer path.

This experiment does not assert one golden arm architecture. It proves that a typed model
proposal can be converted into canonical topology and checked against explicit reach and
actuator evidence while known-bad proposal classes are rejected or blocked.

It also probes the historical canonical arm topology builder for implicit architecture
that the user/model never declared. That probe is diagnostic: detecting the hidden default
is success for the evaluator, not evidence that the old builder is acceptable.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Mapping

from .robot_arm_design import (
    RobotArmDesignError,
    evaluate_robot_arm_design,
    propose_robot_arm_design,
)
from .robot_topology import build_robot_topology


SCHEMA_VERSION = "hardware_splicer.robot_arm_experiment.v1"


def robot_arm_requirements() -> Dict[str, Any]:
    return {
        "required_reach_mm": 450.0,
        "payload_mass_kg": 0.25,
        "minimum_static_torque_safety_factor": 1.5,
        "max_joint_count": 6,
        "maximum_base_width_mm": 300.0,
        "target_repeatability_mm": 5.0,
        "power_on_authorized": False,
        "motion_authorized": False,
    }


def robot_arm_inventory() -> list[Dict[str, Any]]:
    return [
        {
            "component_id": "actuator-base-heavy",
            "type": "actuator",
            "continuous_torque_nm": 4.0,
            "nominal_voltage_v": 24.0,
            "feedback": "encoder",
        },
        {
            "component_id": "actuator-shoulder-heavy",
            "type": "actuator",
            "continuous_torque_nm": 4.0,
            "nominal_voltage_v": 24.0,
            "feedback": "encoder",
        },
        {
            "component_id": "actuator-elbow-medium",
            "type": "actuator",
            "continuous_torque_nm": 2.5,
            "nominal_voltage_v": 24.0,
            "feedback": "encoder",
        },
        {
            "component_id": "actuator-wrist-light",
            "type": "actuator",
            "continuous_torque_nm": 1.0,
            "nominal_voltage_v": 24.0,
            "feedback": "encoder",
        },
        {
            "component_id": "actuator-weak",
            "type": "actuator",
            "continuous_torque_nm": 0.4,
            "nominal_voltage_v": 12.0,
            "feedback": "unknown",
        },
    ]


def robot_arm_source_ids() -> list[str]:
    return ["src-arm-requirements", "src-actuator-candidates"]


def _envelope(payload: Mapping[str, Any], model: str) -> Dict[str, Any]:
    return {
        "ok": True,
        "provider": "robot-arm-experiment",
        "model": model,
        "content": json.dumps(dict(payload), ensure_ascii=False),
        "usage": {},
    }


def _balanced_payload() -> Dict[str, Any]:
    return {
        "reasoning": (
            "Use a four-joint serial candidate whose proposed link-length sum exceeds the "
            "declared reach target while keeping all physical closure explicitly unresolved."
        ),
        "joints": [
            {
                "joint_id": "base-yaw",
                "joint_type": "revolute",
                "axis": [0, 0, 1],
                "link_length_mm": 100,
                "actuator_part_id": "actuator-base-heavy",
                "lower_limit_deg": -160,
                "upper_limit_deg": 160,
            },
            {
                "joint_id": "shoulder-pitch",
                "joint_type": "revolute",
                "axis": [0, 1, 0],
                "link_length_mm": 150,
                "actuator_part_id": "actuator-shoulder-heavy",
                "lower_limit_deg": -90,
                "upper_limit_deg": 120,
            },
            {
                "joint_id": "elbow-pitch",
                "joint_type": "revolute",
                "axis": [0, 1, 0],
                "link_length_mm": 140,
                "actuator_part_id": "actuator-elbow-medium",
                "lower_limit_deg": -135,
                "upper_limit_deg": 135,
            },
            {
                "joint_id": "wrist-pitch",
                "joint_type": "revolute",
                "axis": [0, 1, 0],
                "link_length_mm": 80,
                "actuator_part_id": "actuator-wrist-light",
                "lower_limit_deg": -90,
                "upper_limit_deg": 90,
            },
        ],
        "end_effector": "parallel_gripper_candidate",
        "source_ids": robot_arm_source_ids(),
        "unresolved_questions": [
            "What are the measured link masses and centers of mass?",
            "What collision geometry and cable routing constraints apply?",
            "What feedback resolution and backlash are measured at each output joint?",
        ],
        "authority_effect": "none",
        "automatic_execution": False,
    }


def _balanced_model(prompt: str, **_: object) -> Dict[str, Any]:
    del prompt
    return _envelope(_balanced_payload(), "balanced-arm-operator")


def _underpowered_model(prompt: str, **_: object) -> Dict[str, Any]:
    del prompt
    payload = _balanced_payload()
    payload["joints"] = [
        {**dict(row), "actuator_part_id": "actuator-weak"}
        for row in list(payload["joints"])
    ]
    payload["reasoning"] = "Synthetic underpowered design used to prove deterministic torque rejection."
    return _envelope(payload, "underpowered-arm-operator")


def _unresolved_model(prompt: str, **_: object) -> Dict[str, Any]:
    del prompt
    payload = _balanced_payload()
    payload["joints"] = [
        {**dict(row), "actuator_part_id": None}
        for row in list(payload["joints"])
    ]
    payload["reasoning"] = "Keep actuator identity unresolved rather than substituting a familiar hobby part."
    payload["unresolved_questions"] = [
        "Which exact actuators are available with defensible continuous-torque ratings?"
    ]
    return _envelope(payload, "unresolved-arm-operator")


def _hallucinating_model(prompt: str, **_: object) -> Dict[str, Any]:
    del prompt
    payload = _balanced_payload()
    joints = [dict(row) for row in list(payload["joints"])]
    joints[0]["actuator_part_id"] = "sg90-not-visible"
    payload["joints"] = joints
    payload["reasoning"] = "Synthetic identity hallucination probe."
    return _envelope(payload, "hallucinating-arm-operator")


PERSONAS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "balanced": _balanced_model,
    "underpowered": _underpowered_model,
    "unresolved": _unresolved_model,
    "hallucinating": _hallucinating_model,
}


def _run_persona(name: str, model: Callable[..., Dict[str, Any]]) -> Dict[str, Any]:
    try:
        proposal = propose_robot_arm_design(
            "Design a tabletop robot arm for the declared reach and payload requirements.",
            requirements=robot_arm_requirements(),
            inventory=robot_arm_inventory(),
            source_ids=robot_arm_source_ids(),
            llm_callable=model,
        )
    except RobotArmDesignError as exc:
        return {
            "persona": name,
            "proposal_accepted": False,
            "error": str(exc),
            "failure_class": (
                "EVIDENCE_MODEL"
                if "absent from visible inventory" in str(exc) or "absent from visible evidence" in str(exc)
                else "TOOL_CONTRACT"
            ),
        }

    evaluation = evaluate_robot_arm_design(
        proposal,
        requirements=robot_arm_requirements(),
        inventory=robot_arm_inventory(),
    )
    return {
        "persona": name,
        "proposal_accepted": True,
        "proposal": proposal.model_dump(mode="json"),
        "evaluation": evaluation.model_dump(mode="json"),
    }


def _legacy_arm_default_probe() -> Dict[str, Any]:
    """Detect whether the historical topology builder invents an unspecified arm chain."""

    topology = build_robot_topology(
        {
            "project_name": "robot-arm-default-probe",
            "goal": "Build a tabletop robot arm; joint count and kinematic chain are intentionally unspecified.",
            "constraints": {},
            "available_parts": [],
        },
        hinted_genre="robotic_arm",
    )
    joint_ids = [row.joint_id for row in topology.joints]
    canned_tokens = {"shoulder-pan-joint", "shoulder-lift-joint", "elbow-joint", "wrist-pitch-joint", "wrist-roll-joint"}
    detected = bool(len(joint_ids) == 5 and canned_tokens.issubset(set(joint_ids)))
    return {
        "implicit_default_detected": detected,
        "joint_count_without_declared_dof": len(joint_ids),
        "joint_ids": joint_ids,
        "diagnosis": "SCRIPT_BRAIN" if detected else None,
        "reason": (
            "Historical arm builder synthesized a five-joint named chain without declared/model-proposed kinematic structure."
            if detected
            else "No implicit five-joint arm scaffold was detected."
        ),
        "motion_authorized": bool(topology.metadata.get("motion_authorized")),
    }


def run_robot_arm_experiment() -> Dict[str, Any]:
    reports = {name: _run_persona(name, model) for name, model in PERSONAS.items()}
    legacy_probe = _legacy_arm_default_probe()

    balanced = reports["balanced"]
    balanced_eval = dict(balanced.get("evaluation") or {})
    balanced_findings = list(balanced_eval.get("findings") or [])
    balanced_codes = {str(row.get("code")) for row in balanced_findings if isinstance(row, Mapping)}
    torque_rows = [
        row for row in balanced_findings
        if isinstance(row, Mapping) and row.get("code") == "PAYLOAD_ONLY_TORQUE_BOUND"
    ]

    underpowered_eval = dict(reports["underpowered"].get("evaluation") or {})
    unresolved_eval = dict(reports["unresolved"].get("evaluation") or {})
    hallucinating = reports["hallucinating"]

    checks = {
        "typed_balanced_proposal_accepted": bool(balanced.get("proposal_accepted")),
        "balanced_reach_upper_bound_passes": any(
            isinstance(row, Mapping)
            and row.get("code") == "GEOMETRIC_REACH_UPPER_BOUND"
            and row.get("status") == "pass"
            for row in balanced_findings
        ),
        "balanced_payload_only_torque_bounds_pass": bool(torque_rows)
        and all(row.get("status") == "pass" for row in torque_rows),
        "balanced_still_blocks_physical_motion": balanced_eval.get("status") == "blocked"
        and balanced_eval.get("motion_authorized") is False
        and "PHYSICAL_VALIDATION_REQUIRED" in balanced_codes,
        "underpowered_design_rejected_by_engineering_check": underpowered_eval.get("status") == "failed",
        "unresolved_identity_stays_blocked_not_substituted": unresolved_eval.get("status") == "blocked"
        and any(
            isinstance(row, Mapping) and row.get("code") == "ACTUATOR_IDENTITY_UNRESOLVED"
            for row in list(unresolved_eval.get("findings") or [])
        ),
        "invented_actuator_identity_rejected": hallucinating.get("proposal_accepted") is False
        and hallucinating.get("failure_class") == "EVIDENCE_MODEL",
        "historical_hidden_arm_default_detected": bool(legacy_probe.get("implicit_default_detected")),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "tabletop_robot_arm",
        "requirements": robot_arm_requirements(),
        "visible_inventory": robot_arm_inventory(),
        "source_ids": robot_arm_source_ids(),
        "checks": checks,
        "diagnostic_pass": all(checks.values()),
        "design_ready": False,
        "motion_ready": False,
        "reports": reports,
        "historical_canonical_builder_probe": legacy_probe,
        "conclusion": (
            "Typed model-to-topology-to-engineering evaluation is operational, but the historical canonical arm builder still contains an implicit five-DOF script-brain scaffold and full robotic-arm physical closure is not yet implemented."
        ),
    }
