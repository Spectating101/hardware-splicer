#!/usr/bin/env python3
"""Verify all netlist fixtures compile KiCad-clean (general engine bar)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.build_compiler import compile_from_netlist
from hardware_splicer.integrations.circuit_json_import import circuit_json_to_netlist
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist
from hardware_splicer.netlist.ir import CircuitNetlist

FIXTURE_ROOT = ROOT / "examples" / "netlist_fixtures"
MANIFEST = FIXTURE_ROOT / "manifest.json"


def _load_netlist(fixture: dict) -> CircuitNetlist:
    path = FIXTURE_ROOT / fixture["path"]
    if fixture.get("type") == "kicad_netlist":
        return parse_kicad_netlist(path.read_text(encoding="utf-8"))
    return CircuitNetlist.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _kicad_drc_errors(row: dict) -> int:
    val = row.get("kicad_drc_errors")
    if val is None:
        return 1
    return int(val)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_verify_netlist"))
    args = parser.parse_args()

    os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    os.environ["HARDWARE_SPLICER_JLC_ENRICH"] = "0"

    fixtures = json.loads(MANIFEST.read_text(encoding="utf-8")).get("fixtures") or []
    rows = []
    for fixture in fixtures:
        fid = fixture["id"]
        out = args.out / fid
        t0 = time.time()
        try:
            netlist = _load_netlist(fixture)
            result = compile_from_netlist(
                netlist,
                out,
                build_id="generic_low_voltage_build",
                export_gerber=False,
            )
            q = result.design_quality or {}
            rows.append(
                {
                    "fixture_id": fid,
                    "ok": result.ok,
                    "kicad_drc_errors": int(q.get("kicad_drc_errors") or 0),
                    "kicad_truth_pass": q.get("kicad_truth_pass"),
                    "copper_tier": q.get("copper_tier"),
                    "compile_engine": q.get("compile_engine"),
                    "seconds": round(time.time() - t0, 2),
                    "error": result.error,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "fixture_id": fid,
                    "ok": False,
                    "error": str(exc),
                    "seconds": round(time.time() - t0, 2),
                }
            )

    clean = [r for r in rows if r.get("ok") and _kicad_drc_errors(r) == 0]
    report = {
        "fixture_count": len(rows),
        "compile_ok": len([r for r in rows if r.get("ok")]),
        "kicad_drc_clean": len(clean),
        "autoroute": False,
        "failures": [r for r in rows if not r.get("ok") or _kicad_drc_errors(r) > 0],
        "fixtures": rows,
    }
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"fixtures={report['fixture_count']} drc_clean={report['kicad_drc_clean']}")
    if report["failures"]:
        for row in report["failures"]:
            print(f"FAIL {row['fixture_id']}: {row.get('error') or row.get('kicad_drc_errors')}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
