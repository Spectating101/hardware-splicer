#!/usr/bin/env python3
"""Salvage bring-up demo — junk-drawer parts → wired PCB + evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.salvage_bringup import run_salvage_bringup

DEFAULT_INTAKE = ROOT / "examples" / "intakes" / "salvage_wifi_logger_brief.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Salvage bring-up demo with evidence bundle")
    parser.add_argument("--intake", type=Path, default=DEFAULT_INTAKE)
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_salvage_bringup"))
    parser.add_argument("--export-gerber", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print report JSON to stdout")
    args = parser.parse_args()

    intake = json.loads(args.intake.resolve().read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    report = run_salvage_bringup(intake, out_dir=args.out.resolve(), export_gerber=args.export_gerber)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        qs = report["quality_summary"]
        print(f"Salvage bring-up: ok={report['ok']} build_id={report.get('build_id')}")
        print(f"  KiCad DRC errors={qs.get('kicad_drc_errors')} warnings={qs.get('kicad_drc_warnings')}")
        print(f"  copper_tier={qs.get('copper_tier')} fab={qs.get('fab_recommendation')}")
        print(f"  drc_fix: resolved={qs.get('drc_fix_resolved')} attempts={qs.get('drc_fix_attempts')}")
        print(f"  report: {report.get('report_path')}")

    return 0 if report.get("ok") and (report.get("quality_summary") or {}).get("kicad_drc_errors", 1) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
