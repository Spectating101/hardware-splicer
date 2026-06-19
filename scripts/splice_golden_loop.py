#!/usr/bin/env python3
"""CLI entry for splice golden loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.golden_loop import run_splice_golden_loop
from hardware_splicer.project_intake import load_project_intake


def main() -> int:
    parser = argparse.ArgumentParser(description="Run splice golden loop (build + bench closure)")
    parser.add_argument(
        "--intake",
        type=Path,
        default=ROOT / "examples" / "intakes" / "splice_robot_drive_vision_brief.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_splice_golden_loop"))
    parser.add_argument("--export-gerber", action="store_true")
    parser.add_argument("--no-simulate-bench", action="store_true", help="Stop after template (real bench required)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    intake = load_project_intake(args.intake)
    report = run_splice_golden_loop(
        intake,
        out_dir=args.out,
        export_gerber=bool(args.export_gerber),
        simulate_bench=not args.no_simulate_bench,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Golden loop: {'PASS' if report.get('passed') else 'FAIL'}")
        print(f"  build_id={report.get('build_id')} drc_pass={report.get('drc_pass')}")
        print(f"  bench {report['bench_before']['readiness']} -> {report['bench_after']['readiness']}")
        print(f"  power_on_authorized={report['bench_after'].get('power_on_authorized')}")
        print(f"  report: {report.get('report_path')}")
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
