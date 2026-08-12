"""Reference-backed robot-arm benchmark for the dual-agent engineering method.

The benchmark deliberately distinguishes three capabilities:

1. blind reconstruction: solve requirements without reference leakage;
2. source-assisted reconstruction: use known public robots as evidence, not templates;
3. transfer/mutation: change requirements enough that copying a reference is unsafe.

The public references are benchmark truth for specific published facts only. They are not
physical authority for a new design. In particular, SO-101 publishes stall-torque guidance;
that value is intentionally not converted into continuous actuator torque.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .robot_arm_design import (
    RobotArmDesignProposal,
    evaluate_robot_arm_design,
    parse_robot_arm_design,
)
from .robot_arm_experiment import robot_arm_inventory


SCHEMA_VERSION = "hardware_splicer.robot_arm_reference_benchmark.v1"
_G = 9.80665


REFERENCE_SOURCES: Dict[str, Dict[str, Any]] = {
    "ref-openmanipulator-x-spec": {
        "kind": "manufacturer_specification",
        "authority": "published_reference_robot_fact",
        "url": "https://emanual.robotis.com/docs/en/platform/openmanipulator_x/specification/",
        "facts": {
            "arm_dof": 4,
            "gripper_dof": 1,
            "reach_mm": 380.0,
            "payload_kg": 0.5,
            "repeatability_mm_lt": 0.2,
            "input_voltage_v": 12.0,
            "actuator_identity": "DYNAMIXEL XM430-W350-T",
            "published_weight_kg": 0.70,
            "published_inertia_total_mass_kg": 0.71137,
        },
    },
    "ref-so101-urdf": {
        "kind": "reference_urdf",
        "authority": "published_reference_robot_model",
        "url": "https://github.com/TheRobotStudio/SO-ARM100/blob/main/Simulation/SO101/so101_new_calib.urdf",
        "facts": {
            "arm_joint_names": [
                "shoulder_pan",
                "shoulder_lift",
                "elbow_flex",
                "wrist_flex",
                "wrist_roll",
            ],
            "gripper_joint_name": "gripper",
            "arm_dof": 5,
            "gripper_dof": 1,
            "link_masses_kg": {
                "base_link": 0.147,
                "shoulder_link": 0.100006,
                "upper_arm_link": 0.103,
                "lower_arm_link": 0.104,
                "wrist_link": 0.079,
                "gripper_link": 0.087,
                "moving_jaw_link": 0.012,
            },
            "modeled_mass_kg": 0.632006,
            "joint_limits_present": True,
            "collision_meshes_present": True,
            "inertial_properties_present": True,
        },
        "quality_notes": [
            "Reference geometry applies to SO-101, not automatically to a derived arm.",
            "Collision meshes in a URDF are evidence/model inputs, not proof of collision-free motion.",
        ],
    },
    "ref-so101-project": {
        "kind": "open_hardware_project_documentation",
        "authority": "published_reference_robot_fact",
        "url": "https://github.com/TheRobotStudio/SO-ARM100",
        "facts": {
            "printable_structure": True,
            "follower_motor_family": "STS3215",
            "follower_7_4v_stall_torque_kg_cm_at_6v": 16.5,
            "follower_12v_stall_torque_kg_cm": 30.0,
            "torque_semantics": "stall_only_not_continuous",
        },
        "authority_ceiling": {
            "continuous_torque_nm": "unresolved",
            "reason": "Published project guidance gives stall torque; stall torque must not be promoted to continuous design torque.",
        },
    },
}


def blind_requirements() -> Dict[str, Any]:
    return {
        "required_reach_mm": 380.0,
        "payload_mass_kg": 0.5,
        "minimum_static_torque_safety_factor": 1.5,
        "max_joint_count": 6,
        "target_repeatability_mm": 0.2,
        "motion_authorized": False,
    }


def assisted_requirements() -> Dict[str, Any]:
    return {
        "required_reach_mm": 400.0,
        "payload_mass_kg": 0.25,
        "minimum_static_torque_safety_factor": 1.5,
        "max_joint_count": 6,
        "printable_structure_preferred": True,
        "motion_authorized": False,
    }


def mutation_requirements() -> Dict[str, Any]:
    return {
        "required_reach_mm": 550.0,
        "payload_mass_kg": 0.75,
        "minimum_static_torque_safety_factor": 1.5,
        "max_joint_count": 6,
        "printable_structure_preferred": True,
        "motion_authorized": False,
    }


def reference_source_ids() -> list[str]:
    return list(REFERENCE_SOURCES)


def load_external_proposals(path: str | Path) -> Dict[str, Any]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(body, Mapping):
        raise ValueError("reference benchmark proposal bundle must be one JSON object")
    return dict(body)


def _inventory_index(inventory: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for row in inventory:
        identity = str(row.get("component_id") or "").strip()
        if identity:
            result[identity] = dict(row)
    return result


def _axis_aware_payload_oracle(
    proposal: RobotArmDesignProposal,
    *,
    requirements: Mapping[str, Any],
    inventory: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Conservative payload-only torque oracle with explicit orientation limits.

    The current typed arm schema does not contain full joint transforms. Therefore only the
    root joint axis can be compared directly with world gravity. If that root axis is
    parallel to gravity, static payload gravity torque about it is zero. For every downstream
    revolute joint, world-axis orientation is unresolved, so the oracle uses the worst-case
    m*g*r bound instead of pretending local-axis coordinates are world coordinates.
    """

    payload_mass_kg = float(requirements["payload_mass_kg"])
    safety_factor = float(requirements["minimum_static_torque_safety_factor"])
    inventory_by_id = _inventory_index(inventory)
    remaining_mm = sum(row.link_length_mm for row in proposal.joints)
    rows: list[Dict[str, Any]] = []
    failures = 0
    unresolved = 0

    for index, joint in enumerate(proposal.joints):
        if joint.joint_type != "revolute":
            rows.append(
                {
                    "joint_id": joint.joint_id,
                    "status": "unresolved",
                    "reason": "prismatic_force_model_not_implemented",
                }
            )
            unresolved += 1
            remaining_mm -= joint.link_length_mm
            continue

        axis_factor = 1.0
        axis_basis = "downstream_world_axis_unresolved_worst_case"
        if index == 0:
            vertical_alignment = abs(float(joint.axis[2]))
            if vertical_alignment >= 1.0 - 1e-9:
                axis_factor = 0.0
                axis_basis = "root_axis_parallel_to_gravity"

        required_nm = (
            payload_mass_kg
            * _G
            * (remaining_mm / 1000.0)
            * safety_factor
            * axis_factor
        )
        part = inventory_by_id.get(str(joint.actuator_part_id or ""))
        available_nm = None
        if part is not None and part.get("continuous_torque_nm") is not None:
            available_nm = float(part["continuous_torque_nm"])

        if not joint.actuator_part_id:
            status = "unresolved"
            unresolved += 1
            margin_nm = None
        elif available_nm is None:
            status = "unresolved"
            unresolved += 1
            margin_nm = None
        else:
            margin_nm = available_nm - required_nm
            status = "pass" if margin_nm >= 0 else "fail"
            if status == "fail":
                failures += 1

        rows.append(
            {
                "joint_id": joint.joint_id,
                "actuator_part_id": joint.actuator_part_id,
                "axis": list(joint.axis),
                "axis_factor": round(axis_factor, 6),
                "axis_basis": axis_basis,
                "remaining_chain_length_mm": round(remaining_mm, 3),
                "required_payload_only_torque_nm": round(required_nm, 4),
                "available_continuous_torque_nm": available_nm,
                "margin_nm": None if margin_nm is None else round(margin_nm, 4),
                "status": status,
            }
        )
        remaining_mm -= joint.link_length_mm

    return {
        "status": "failed" if failures else ("blocked" if unresolved else "bounded_pass"),
        "hard_failure_count": failures,
        "unresolved_count": unresolved,
        "rows": rows,
        "authority_effect": "none",
        "motion_authorized": False,
        "limitations": [
            "Only root-axis alignment with gravity is resolved without full joint transforms.",
            "Downstream joints use a worst-case payload-only gravity bound.",
            "Link self-weight, inertia, acceleration, transmissions, friction, stiffness, and collision are not closed.",
        ],
    }


def _proposal(
    payload: Mapping[str, Any],
    *,
    allow_sources: bool,
) -> RobotArmDesignProposal:
    return parse_robot_arm_design(
        dict(payload),
        inventory=robot_arm_inventory(),
        known_source_ids=reference_source_ids() if allow_sources else [],
    )


def _finding(evaluation: Any, code: str, joint_id: str | None = None) -> Any | None:
    for row in evaluation.findings:
        if row.code == code and (joint_id is None or row.joint_id == joint_id):
            return row
    return None


def _scaled_copy_trap(source_payload: Mapping[str, Any]) -> Dict[str, Any]:
    body = copy.deepcopy(dict(source_payload))
    joints = list(body.get("joints") or [])
    current = sum(float(row.get("link_length_mm") or 0.0) for row in joints)
    scale = 550.0 / current
    for row in joints:
        row["link_length_mm"] = round(float(row["link_length_mm"]) * scale, 6)
    body["reasoning"] = "Naive comparator: scale the source-assisted geometry to the mutated reach while retaining all actuator bindings."
    body["unresolved_questions"] = []
    return body


def run_reference_robot_arm_benchmark(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    inventory = robot_arm_inventory()
    blind = _proposal(bundle["blind_reconstruction"], allow_sources=False)
    assisted = _proposal(bundle["source_assisted_reconstruction"], allow_sources=True)
    mutated = _proposal(bundle["mutated_requirement"], allow_sources=True)
    naive_copy = _proposal(_scaled_copy_trap(bundle["source_assisted_reconstruction"]), allow_sources=True)

    blind_legacy = evaluate_robot_arm_design(blind, requirements=blind_requirements(), inventory=inventory)
    assisted_legacy = evaluate_robot_arm_design(assisted, requirements=assisted_requirements(), inventory=inventory)
    mutation_legacy = evaluate_robot_arm_design(mutated, requirements=mutation_requirements(), inventory=inventory)
    naive_copy_legacy = evaluate_robot_arm_design(naive_copy, requirements=mutation_requirements(), inventory=inventory)

    blind_oracle = _axis_aware_payload_oracle(blind, requirements=blind_requirements(), inventory=inventory)
    assisted_oracle = _axis_aware_payload_oracle(assisted, requirements=assisted_requirements(), inventory=inventory)
    mutation_oracle = _axis_aware_payload_oracle(mutated, requirements=mutation_requirements(), inventory=inventory)
    naive_copy_oracle = _axis_aware_payload_oracle(naive_copy, requirements=mutation_requirements(), inventory=inventory)

    legacy_base = _finding(blind_legacy, "PAYLOAD_ONLY_TORQUE_BOUND", "base-yaw")
    oracle_base = next(row for row in blind_oracle["rows"] if row["joint_id"] == "base-yaw")

    openmanipulator = REFERENCE_SOURCES["ref-openmanipulator-x-spec"]["facts"]
    so101 = REFERENCE_SOURCES["ref-so101-urdf"]["facts"]
    assisted_chain = sum(row.link_length_mm for row in assisted.joints)
    blind_chain = sum(row.link_length_mm for row in blind.joints)

    mutation_shoulder = next(row for row in mutation_oracle["rows"] if row["joint_id"] == "shoulder-pitch")
    naive_copy_failures = [row for row in naive_copy_oracle["rows"] if row["status"] == "fail"]

    checks = {
        "blind_has_no_reference_leakage": blind.source_ids == [],
        "blind_matches_reference_problem_class_without_exact_copy": (
            len(blind.joints) == int(openmanipulator["arm_dof"])
            and blind_chain != float(openmanipulator["reach_mm"])
            and blind_chain >= float(openmanipulator["reach_mm"])
        ),
        "blind_axis_aware_payload_bounds_have_no_hard_failure": blind_oracle["hard_failure_count"] == 0,
        "assisted_uses_visible_reference_evidence": set(assisted.source_ids) == set(reference_source_ids()),
        "assisted_uses_reference_structure_without_copying_reference_geometry": (
            len(assisted.joints) == int(so101["arm_dof"])
            and assisted_chain == 420.0
        ),
        "so101_stall_torque_not_promoted_to_continuous_truth": (
            REFERENCE_SOURCES["ref-so101-project"]["authority_ceiling"]["continuous_torque_nm"] == "unresolved"
            and all(not str(row.actuator_part_id or "").startswith("sts3215") for row in assisted.joints)
        ),
        "mutation_refuses_unsafe_reference_copy": mutation_shoulder["status"] == "unresolved",
        "mutation_keeps_motion_authority_closed": mutation_oracle["motion_authorized"] is False,
        "naive_scaled_reference_copy_is_caught": bool(naive_copy_failures),
        "legacy_base_yaw_gravity_referee_defect_detected": (
            legacy_base is not None
            and float(legacy_base.outputs.get("payload_only_required_torque_nm") or 0.0) > 0.0
            and float(oracle_base["required_payload_only_torque_nm"]) == 0.0
        ),
    }

    diagnostic_pass = all(checks.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "reference_backed_robot_arm_engineering",
        "diagnostic_pass": diagnostic_pass,
        "design_ready": False,
        "motion_ready": False,
        "checks": checks,
        "reference_sources": REFERENCE_SOURCES,
        "lanes": {
            "blind_reconstruction": {
                "requirements": blind_requirements(),
                "proposal": blind.model_dump(mode="json"),
                "reference_comparison": {
                    "openmanipulator_arm_dof": openmanipulator["arm_dof"],
                    "openmanipulator_reach_mm": openmanipulator["reach_mm"],
                    "proposed_joint_count": len(blind.joints),
                    "proposed_chain_length_mm": blind_chain,
                },
                "legacy_evaluator": blind_legacy.model_dump(mode="json"),
                "axis_aware_oracle": blind_oracle,
            },
            "source_assisted_reconstruction": {
                "requirements": assisted_requirements(),
                "proposal": assisted.model_dump(mode="json"),
                "reference_comparison": {
                    "so101_arm_dof": so101["arm_dof"],
                    "proposed_joint_count": len(assisted.joints),
                    "proposed_chain_length_mm": assisted_chain,
                    "source_ids_used": assisted.source_ids,
                },
                "legacy_evaluator": assisted_legacy.model_dump(mode="json"),
                "axis_aware_oracle": assisted_oracle,
            },
            "mutated_requirement": {
                "requirements": mutation_requirements(),
                "proposal": mutated.model_dump(mode="json"),
                "legacy_evaluator": mutation_legacy.model_dump(mode="json"),
                "axis_aware_oracle": mutation_oracle,
            },
            "naive_scaled_copy_trap": {
                "requirements": mutation_requirements(),
                "proposal": naive_copy.model_dump(mode="json"),
                "legacy_evaluator": naive_copy_legacy.model_dump(mode="json"),
                "axis_aware_oracle": naive_copy_oracle,
            },
        },
        "evaluator_diagnostics": {
            "legacy_base_yaw_required_nm": None if legacy_base is None else legacy_base.outputs.get("payload_only_required_torque_nm"),
            "axis_aware_root_yaw_required_nm": oracle_base["required_payload_only_torque_nm"],
            "diagnosis": "TOOL_IMPLEMENTATION" if checks["legacy_base_yaw_gravity_referee_defect_detected"] else None,
            "note": "The existing evaluator applies m*g*r to a vertical root yaw axis. The benchmark oracle resolves root-axis gravity alignment but remains conservative for downstream joints until full transforms/FK exist.",
        },
        "authority": {
            "fabrication_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    }
