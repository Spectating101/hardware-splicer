#!/usr/bin/env python3
"""Run typed robot-arm proposals through generated URDF + PyBullet FK/IK/collision checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.robot_arm_design import parse_robot_arm_design
from hardware_splicer.robot_arm_experiment import robot_arm_inventory
from hardware_splicer.robot_arm_kinematics import generate_robot_arm_urdf, run_pybullet_kinematics_oracle
from hardware_splicer.robot_arm_reference_benchmark import reference_source_ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proposal-bundle",
        default="experiments/robot_arm/reference_benchmark_gpt56_sol_proposals.json",
    )
    parser.add_argument("--out-dir", default="artifacts/robot-arm-kinematics")
    args = parser.parse_args()

    bundle = json.loads(Path(args.proposal_bundle).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory = robot_arm_inventory()

    lane_specs = {
        "blind_reconstruction": {"allow_sources": False, "expected_joints": 4},
        "source_assisted_reconstruction": {"allow_sources": True, "expected_joints": 5},
        "mutated_requirement": {"allow_sources": True, "expected_joints": 5},
    }
    lanes = {}
    checks = {}

    for lane_name, spec in lane_specs.items():
        proposal = parse_robot_arm_design(
            bundle[lane_name],
            inventory=inventory,
            known_source_ids=reference_source_ids() if spec["allow_sources"] else [],
        )
        if not spec["allow_sources"] and proposal.source_ids:
            raise RuntimeError("blind kinematics lane contains reference source IDs")

        artifact = generate_robot_arm_urdf(proposal, robot_name=f"hs_{lane_name}")
        urdf_path = out_dir / f"{lane_name}.urdf"
        urdf_path.write_text(artifact.text, encoding="utf-8")
        oracle = run_pybullet_kinematics_oracle(proposal, urdf_path=str(urdf_path))
        lanes[lane_name] = {
            "proposal": proposal.model_dump(mode="json"),
            "urdf": {
                "path": urdf_path.name,
                "joint_count": artifact.joint_count,
                "chain_length_m": artifact.chain_length_m,
                "collision_geometry_authority": artifact.collision_geometry_authority,
                "physical_authority": artifact.physical_authority,
            },
            "oracle": oracle,
        }
        checks[f"{lane_name}.urdf_loads"] = bool(oracle.get("urdf_load_pass"))
        checks[f"{lane_name}.joint_count_matches"] = (
            int(oracle.get("loaded_movable_joint_count") or -1) == int(spec["expected_joints"])
        )
        checks[f"{lane_name}.zero_pose_fk_matches_chain"] = (
            float(oracle.get("zero_pose_chain_error_mm") or 1e9) <= 0.05
        )
        checks[f"{lane_name}.ik_reaches_interior_target"] = bool(oracle.get("ik_within_5mm"))
        checks[f"{lane_name}.ik_respects_joint_limits"] = bool(oracle.get("ik_joint_limits_respected"))
        checks[f"{lane_name}.unreachable_target_not_falsely_closed"] = bool(
            oracle.get("unreachable_target_not_falsely_closed")
        )
        checks[f"{lane_name}.proxy_collision_probe_executed"] = (
            int(oracle.get("proxy_collision_sample_count") or 0) > 0
        )
        checks[f"{lane_name}.physical_authority_closed"] = (
            oracle.get("physical_authority") == "none"
            and oracle.get("motion_authorized") is False
        )

    mutated = lanes["mutated_requirement"]
    mutation_proposal = mutated["proposal"]
    shoulder = next(row for row in mutation_proposal["joints"] if row["joint_id"] == "shoulder-pitch")
    checks["mutation.kinematics_can_pass_without_fabricating_actuator_identity"] = (
        bool(mutated["oracle"].get("ik_within_5mm"))
        and shoulder.get("actuator_part_id") is None
        and mutated["oracle"].get("motion_authorized") is False
    )

    diagnostic_pass = all(checks.values())
    report = {
        "schema_version": "hardware_splicer.robot_arm_kinematics_benchmark.v1",
        "benchmark": "typed_arm_urdf_pybullet",
        "engine": "pybullet",
        "diagnostic_pass": diagnostic_pass,
        "design_ready": False,
        "motion_ready": False,
        "checks": checks,
        "lanes": lanes,
        "interpretation": {
            "urdf_authority": "proposal_only",
            "collision_geometry_authority": "proxy_only",
            "kinematics_result_authority": "deterministic_tool_result_for_generated_proxy_model",
            "physical_authority": "none",
            "next_missing_layers": [
                "CAD-derived transforms and collision meshes",
                "link mass/center-of-mass/inertia",
                "full gravity and inverse dynamics",
                "actuator/transmission electrical and thermal models",
                "MoveIt planning-scene integration",
                "bench calibration and repeatability evidence",
            ],
        },
    }
    report_path = out_dir / "ROBOT_ARM_KINEMATICS_BENCHMARK.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "benchmark=typed_arm_urdf_pybullet",
        f"diagnostic_pass={diagnostic_pass}",
        "design_ready=False",
        "motion_ready=False",
    ]
    for lane_name in lane_specs:
        oracle = lanes[lane_name]["oracle"]
        lines.extend(
            [
                f"{lane_name}.joint_count={oracle.get('loaded_movable_joint_count')}",
                f"{lane_name}.chain_m={oracle.get('chain_length_m')}",
                f"{lane_name}.zero_fk_error_mm={oracle.get('zero_pose_chain_error_mm')}",
                f"{lane_name}.ik_error_mm={oracle.get('ik_position_error_mm')}",
                f"{lane_name}.unreachable_error_mm={oracle.get('unreachable_target_error_mm')}",
                f"{lane_name}.workspace_max_m={oracle.get('workspace_max_radius_m')}",
                f"{lane_name}.proxy_collision_free_fraction={oracle.get('proxy_collision_free_fraction')}",
            ]
        )
    for key, value in checks.items():
        lines.append(f"check.{key}={bool(value)}")
    summary_path = out_dir / "ROBOT_ARM_KINEMATICS_SUMMARY.txt"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_path.read_text(encoding="utf-8"), end="")
    return 0 if diagnostic_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
