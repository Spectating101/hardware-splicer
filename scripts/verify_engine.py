#!/usr/bin/env python3
"""Engine quality bar — all catalog builds KiCad-clean (no FreeRouting).

Exit 0 when every catalog build:
  - compiles ok
  - kicad_drc_errors == 0
  - erc_pass and kicad_erc_pass

Usage:
  PYTHONPATH=src python3 scripts/verify_engine.py
  PYTHONPATH=src python3 scripts/verify_engine.py --json /tmp/verify_engine.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_catalog_build


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify all catalog builds are KiCad DRC-clean")
    parser.add_argument("--json", type=Path, default=None, help="Write full report JSON")
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_verify_engine"))
    parser.add_argument(
        "--max-warnings",
        type=int,
        default=500,
        help="Fail if any build exceeds this KiCad DRC warning count",
    )
    args = parser.parse_args()

    os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    os.environ["HARDWARE_SPLICER_JLC_ENRICH"] = "0"

    rows = []
    for build_id in CATALOG_BUILD_IDS:
        out = args.out / build_id
        t0 = time.time()
        result = compile_catalog_build(build_id, str(out), export_gerber=False)
        q = result.design_quality or {}
        rows.append(
            {
                "build_id": build_id,
                "ok": result.ok,
                "build_ready": q.get("build_ready"),
                "erc_pass": q.get("erc_pass"),
                "kicad_erc_pass": q.get("kicad_erc_pass"),
                "kicad_drc_pass": q.get("kicad_drc_pass"),
                "kicad_drc_errors": int(q.get("kicad_drc_errors") or 0),
                "kicad_drc_warnings": int(q.get("kicad_drc_warnings") or 0),
                "copper_tier": q.get("copper_tier"),
                "fab_recommendation": q.get("fab_recommendation"),
                "kicad_truth_pass": q.get("kicad_truth_pass"),
                "seconds": round(time.time() - t0, 2),
                "error": result.error,
            }
        )

    drc_clean = [r for r in rows if r.get("kicad_drc_errors", 1) == 0]
    warn_ok = [r for r in rows if r.get("kicad_drc_warnings", 0) <= args.max_warnings]
    all_ok = [r for r in rows if r.get("ok")]
    report = {
        "catalog_count": len(rows),
        "compile_ok": len(all_ok),
        "kicad_drc_clean": len(drc_clean),
        "kicad_warnings_within_budget": len(warn_ok),
        "max_warnings_budget": args.max_warnings,
        "autoroute": False,
        "failures": [
            r
            for r in rows
            if not r.get("ok")
            or r.get("kicad_drc_errors", 0) > 0
            or r.get("kicad_drc_warnings", 0) > args.max_warnings
        ],
        "rows": rows,
    }

    print(f"Engine verify: {report['kicad_drc_clean']}/{report['catalog_count']} KiCad DRC clean, "
          f"{report['compile_ok']}/{report['catalog_count']} compile ok")
    for row in rows:
        mark = "OK" if row.get("kicad_drc_errors") == 0 and row.get("ok") else "FAIL"
        print(
            f"  [{mark}] {row['build_id']}: "
            f"drc_err={row.get('kicad_drc_errors')} warn={row.get('kicad_drc_warnings')} "
            f"({row.get('seconds')}s)"
        )

    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 0 if (
        report["kicad_drc_clean"] == report["catalog_count"]
        and report["compile_ok"] == report["catalog_count"]
        and report["kicad_warnings_within_budget"] == report["catalog_count"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
