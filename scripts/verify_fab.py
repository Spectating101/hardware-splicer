#!/usr/bin/env python3
"""Verify Gerber export + fabrication inspection for catalog builds (gate 2.6)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_catalog_build  # noqa: E402
from hardware_splicer.fabrication_inspection import inspect_fabrication_package  # noqa: E402
from hardware_splicer.runtime import scratch_path  # noqa: E402

# Representative subset for fast local runs; CI uses --all.
FAST_BUILD_IDS = [
    "automatic_plant_watering",
    "usb_fume_extractor",
    "small_audio_amp_box",
    "plotter_motion_stage",
    "bench_power_adapter",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerber + inspect-fab bar for catalog builds")
    parser.add_argument("--all", action="store_true", help="Verify all catalog builds (CI default)")
    parser.add_argument("--json", type=Path, help="Write FAB_VERIFY_REPORT.json")
    args = parser.parse_args()

    if not shutil.which("kicad-cli"):
        print("skip: kicad-cli not installed")
        return 0

    os.environ.setdefault("HARDWARE_SPLICER_AUTOROUTE", "0")
    os.environ.setdefault("HARDWARE_SPLICER_JLC_ENRICH", "0")

    build_ids = list(CATALOG_BUILD_IDS) if args.all or os.getenv("CI") else FAST_BUILD_IDS
    out_root = scratch_path("fab_verify")
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    failures = 0
    for build_id in build_ids:
        target = out_root / build_id
        result = compile_catalog_build(build_id, target, export_gerber=True)
        quality = result.design_quality or {}
        inspection = inspect_fabrication_package(build_compilation=result.to_dict())
        gerber_dir = result.gerber_package_dir
        gerber_ok = bool(gerber_dir and Path(gerber_dir).is_dir())
        drc_clean = int(quality.get("kicad_drc_errors") or 0) == 0
        row = {
            "build_id": build_id,
            "compile_ok": bool(result.ok),
            "gerber_ready": bool(quality.get("gerber_ready")),
            "gerber_dir_present": gerber_ok,
            "honest_fabrication_ready": bool(inspection.get("honest_fabrication_ready")),
            "inspection_score": inspection.get("inspection_score"),
            "blockers": inspection.get("blockers") or [],
            "kicad_drc_errors": int(quality.get("kicad_drc_errors") or 0),
        }
        gate_pass = bool(result.ok and gerber_ok and drc_clean)
        row["fab_gate_pass"] = gate_pass
        if not gate_pass:
            failures += 1
            row["error"] = result.error or "gerber_or_drc_failed"
        rows.append(row)

    report = {
        "schema_version": "hardware_splicer.fab_verify.v1",
        "builds": len(rows),
        "failures": failures,
        "rows": rows,
    }
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"fab_verify builds={len(rows)} failures={failures}")
    if failures:
        for row in rows:
            if row.get("error"):
                print(f"  FAIL {row['build_id']}: {row['error']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
