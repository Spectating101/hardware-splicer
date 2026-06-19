#!/usr/bin/env python3
"""Golden real S3: build + submit committed manual bench capture (not simulator)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.golden_real_bench import run_splice_golden_real
from hardware_splicer.project_intake import load_project_intake


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden real S3 bench path")
    parser.add_argument(
        "--intake",
        type=Path,
        default=ROOT / "examples" / "intakes" / "splice_robot_drive_golden_real_brief.json",
    )
    parser.add_argument(
        "--capture",
        type=Path,
        default=ROOT / "tests" / "data" / "golden" / "rc_motor_manual_bench_capture.v1.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_splice_golden_real"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    intake = load_project_intake(args.intake)
    report = run_splice_golden_real(
        intake,
        out_dir=args.out,
        capture_path=args.capture,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Golden real S3: {'PASS' if report.get('passed') else 'FAIL'}")
        print(f"  simulated={report.get('simulated')} matched={report.get('matched_measurement_count')}")
        print(f"  power_on={report.get('bench_after', {}).get('power_on_authorized')}")
        print(f"  report: {report.get('report_path')}")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
