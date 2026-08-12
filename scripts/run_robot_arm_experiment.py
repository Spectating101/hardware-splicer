#!/usr/bin/env python3
"""Run the typed robot-arm engineering experiment and persist its evidence report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running a file from scripts/ otherwise places scripts/ before the installed package and
# shadows ``hardware_splicer`` with scripts/hardware_splicer.py.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if sys.path and str(Path(sys.path[0]).resolve()) == _SCRIPT_DIR:
    sys.path.pop(0)

from hardware_splicer.robot_arm_experiment import run_robot_arm_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="artifacts/robot-arm")
    args = parser.parse_args()

    result = run_robot_arm_experiment()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "ROBOT_ARM_EXPERIMENT.json"
    summary_path = out_dir / "ROBOT_ARM_SUMMARY.txt"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    checks = dict(result.get("checks") or {})
    lines = [
        "experiment=tabletop_robot_arm",
        f"diagnostic_pass={bool(result.get('diagnostic_pass'))}",
        f"design_ready={bool(result.get('design_ready'))}",
        f"motion_ready={bool(result.get('motion_ready'))}",
    ]
    for key, value in checks.items():
        lines.append(f"{key}={bool(value)}")
    probe = dict(result.get("historical_canonical_builder_probe") or {})
    lines.extend(
        [
            f"historical_hidden_default={bool(probe.get('implicit_default_detected'))}",
            f"historical_joint_count_without_declared_dof={int(probe.get('joint_count_without_declared_dof') or 0)}",
            f"historical_diagnosis={probe.get('diagnosis')}",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_path.read_text(encoding="utf-8"), end="")
    return 0 if result.get("diagnostic_pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
