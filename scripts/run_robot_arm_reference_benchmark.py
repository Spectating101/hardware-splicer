#!/usr/bin/env python3
"""Run the reference-backed robot-arm benchmark and persist evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.robot_arm_reference_benchmark import (
    load_external_proposals,
    run_reference_robot_arm_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--proposal-bundle",
        default="experiments/robot_arm/reference_benchmark_gpt56_sol_proposals.json",
    )
    parser.add_argument("--out-dir", default="artifacts/robot-arm-reference-benchmark")
    args = parser.parse_args()

    bundle = load_external_proposals(args.proposal_bundle)
    report = run_reference_robot_arm_benchmark(bundle)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "ROBOT_ARM_REFERENCE_BENCHMARK.json"
    summary_path = out_dir / "ROBOT_ARM_REFERENCE_SUMMARY.txt"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    checks = dict(report.get("checks") or {})
    blind = report["lanes"]["blind_reconstruction"]
    assisted = report["lanes"]["source_assisted_reconstruction"]
    mutated = report["lanes"]["mutated_requirement"]
    diagnostic = report["evaluator_diagnostics"]

    mutation_shoulder = next(
        row
        for row in mutated["axis_aware_oracle"]["rows"]
        if row["joint_id"] == "shoulder-pitch"
    )
    lines = [
        "benchmark=reference_backed_robot_arm_engineering",
        f"diagnostic_pass={bool(report.get('diagnostic_pass'))}",
        f"design_ready={bool(report.get('design_ready'))}",
        f"motion_ready={bool(report.get('motion_ready'))}",
        f"blind_joint_count={blind['reference_comparison']['proposed_joint_count']}",
        f"blind_chain_mm={blind['reference_comparison']['proposed_chain_length_mm']}",
        f"blind_openmanipulator_reference_reach_mm={blind['reference_comparison']['openmanipulator_reach_mm']}",
        f"assisted_joint_count={assisted['reference_comparison']['proposed_joint_count']}",
        f"assisted_chain_mm={assisted['reference_comparison']['proposed_chain_length_mm']}",
        f"mutation_shoulder_status={mutation_shoulder['status']}",
        f"mutation_shoulder_required_payload_only_nm={mutation_shoulder['required_payload_only_torque_nm']}",
        f"legacy_base_yaw_required_nm={diagnostic['legacy_base_yaw_required_nm']}",
        f"axis_aware_root_yaw_required_nm={diagnostic['axis_aware_root_yaw_required_nm']}",
        f"evaluator_diagnosis={diagnostic['diagnosis']}",
    ]
    for key, value in checks.items():
        lines.append(f"check.{key}={bool(value)}")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_path.read_text(encoding="utf-8"), end="")
    return 0 if report.get("diagnostic_pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
