#!/usr/bin/env python3
"""Audit functional build delivery (artifacts on disk), not authority theater."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_catalog_build  # noqa: E402
from hardware_splicer.functional_delivery import build_functional_delivery_score  # noqa: E402
from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake  # noqa: E402


def _export_gerber_enabled() -> bool:
    if os.getenv("HARDWARE_SPLICER_AUDIT_SKIP_GERBER", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return shutil.which("kicad-cli") is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit catalog + plant splice functional delivery.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when any build is below 70%% or honest_fabrication_ready is false.",
    )
    args = parser.parse_args()
    strict = args.strict or os.getenv("HARDWARE_SPLICER_AUDIT_STRICT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    export_gerber = _export_gerber_enabled()

    out_root = Path("/tmp/hardware_splicer_functional_audit")
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []

    for build_id in CATALOG_BUILD_IDS:
        target = out_root / "catalog" / build_id
        result = compile_catalog_build(build_id, target, export_gerber=export_gerber)
        scorecard = build_functional_delivery_score(build_compilation=result.to_dict())
        rows.append(
            {
                "kind": "catalog",
                "build_id": build_id,
                "functional_delivery_score": scorecard["functional_delivery_score"],
                "fabrication_inspection_score": scorecard.get("fabrication_inspection_score"),
                "honest_fabrication_ready": scorecard.get("honest_fabrication_ready"),
                "prototype_breakout_only": scorecard.get("prototype_breakout_only"),
                "grade": scorecard["grade"],
                "checks_passed": scorecard["checks_passed"],
                "checks_total": scorecard["checks_total"],
                "blockers": scorecard["blockers"],
            }
        )

    plant_brief = ROOT / "examples" / "intakes" / "plant_watering_brief.json"
    if plant_brief.is_file():
        intake = load_project_intake(plant_brief)
        splice = splice_and_build_from_intake(intake, out_dir=out_root / "plant_splice", export_gerber=export_gerber)
        fd = splice["functional_delivery"]
        rows.append(
            {
                "kind": "intake_splice",
                "build_id": splice.get("build_id"),
                "functional_delivery_score": fd["functional_delivery_score"],
                "fabrication_inspection_score": fd.get("fabrication_inspection_score"),
                "honest_fabrication_ready": fd.get("honest_fabrication_ready"),
                "grade": fd["grade"],
                "checks_passed": fd["checks_passed"],
                "checks_total": fd["checks_total"],
                "blockers": fd["blockers"],
            }
        )

    below_70 = [row for row in rows if float(row["functional_delivery_score"]) < 70.0]
    not_honest = [row for row in rows if row.get("honest_fabrication_ready") is False]
    report = {
        "schema_version": "hardware_splicer.functional_delivery_audit.v1",
        "export_gerber": export_gerber,
        "strict": strict,
        "row_count": len(rows),
        "average_score": round(sum(float(r["functional_delivery_score"]) for r in rows) / max(len(rows), 1), 1),
        "below_70_count": len(below_70),
        "below_70": below_70,
        "not_honest_fabrication_ready_count": len(not_honest),
        "not_honest_fabrication_ready": not_honest,
        "rows": rows,
    }
    report_path = out_root / "FUNCTIONAL_DELIVERY_AUDIT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "average": report["average_score"],
                "below_70": len(below_70),
                "not_honest": len(not_honest),
                "export_gerber": export_gerber,
                "strict": strict,
                "report": str(report_path),
            },
            indent=2,
        )
    )
    if below_70:
        return 1
    if strict and not_honest:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
