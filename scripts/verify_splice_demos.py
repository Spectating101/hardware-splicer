#!/usr/bin/env python3
"""Verify canonical splice demos from examples/splice/manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.splice_manifest import load_splice_manifest, run_and_evaluate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify splice demo manifest cases")
    parser.add_argument("--manifest", type=Path, default=ROOT / "examples" / "splice" / "manifest.json")
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_splice_verify"))
    parser.add_argument("--case", action="append", default=[], help="Run only these case_id values (repeatable)")
    parser.add_argument("--export-gerber", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = load_splice_manifest(args.manifest)
    report = run_and_evaluate_manifest(
        manifest,
        out_root=args.out.resolve(),
        case_ids=args.case or None,
        export_gerber=bool(args.export_gerber),
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Splice verify: {report['passed_count']}/{report['case_count']} passed")
        print(f"report: {report['report_path']}")
        for row in report["cases"]:
            evaluation = row["evaluation"]
            status = "PASS" if evaluation["passed"] else "FAIL"
            print(f"  [{status}] {evaluation['case_id']}")
            for failure in evaluation.get("failures") or []:
                print(f"         - {failure}")

    return 0 if report.get("all_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
