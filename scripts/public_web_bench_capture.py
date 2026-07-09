#!/usr/bin/env python3
"""Public-web DMM photo → bench capture (cold-run provenance).

  PYTHONPATH=src python3 scripts/public_web_bench_capture.py --build-dir OUT
  PYTHONPATH=src python3 scripts/public_web_bench_capture.py --build-dir OUT --live
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.public_web_bench import run_public_web_bench_on_build


def main() -> int:
    parser = argparse.ArgumentParser(description="Public-web DMM bench capture")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="Call Qwen VL (needs key + budget env)")
    parser.add_argument("--no-submit", action="store_true")
    parser.add_argument("--max-photos", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_public_web_bench_on_build(
        args.build_dir,
        live=bool(args.live),
        submit=not args.no_submit,
        max_photos=args.max_photos,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Public-web bench: {'PASS' if report.get('passed') else 'FAIL'}")
        print(f"  live={report.get('live')} matched={report.get('matched_gate_count')}")
        print(f"  power_on={report.get('bench_after', {}).get('power_on_authorized')}")
        print(f"  report={report.get('report_path')}")
        print("  note: public photos ≠ this-board café measurement")
    return 0 if report.get("passed") or args.no_submit else 1


if __name__ == "__main__":
    raise SystemExit(main())
