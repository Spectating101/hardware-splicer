#!/usr/bin/env python3
"""Headless engine stress report — low resource by default.

Fast mode (default): no FreeRouting, no gerbers, optional catalog sample.
Use --autoroute only with --sample 1 (or 2) unless you want a long, heavy run.

Examples:
  PYTHONPATH=src python3 scripts/engine_stress_report.py
  PYTHONPATH=src python3 scripts/engine_stress_report.py --sample 3 --autoroute
  PYTHONPATH=src python3 scripts/engine_stress_report.py --kicad-netlist examples/main_ctrl_esp32_servo.net
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_catalog_build, compile_from_netlist
from hardware_splicer.netlist.import_kicad import parse_kicad_netlist


def _pcb_stats(pcb_path: Path) -> Dict[str, int]:
    if not pcb_path.is_file():
        return {"footprints": 0, "segments": 0, "tracks": 0}
    text = pcb_path.read_text(encoding="utf-8", errors="replace")
    return {
        "footprints": text.count("(footprint"),
        "segments": text.count("(segment"),
        "tracks": text.count("(track"),
    }


def _row_from_result(build_id: str, r: Any, seconds: float) -> Dict[str, Any]:
    q = r.design_quality or {}
    pcb = Path(r.kicad_pcb_file) if r.kicad_pcb_file else None
    return {
        "build_id": build_id,
        "ok": r.ok,
        "error": r.error,
        "seconds": round(seconds, 2),
        "erc_pass": q.get("erc_pass"),
        "kicad_erc_pass": q.get("kicad_erc_pass"),
        "drc_pass": q.get("drc_pass"),
        "kicad_drc_pass": q.get("kicad_drc_pass"),
        "kicad_drc_errors": q.get("kicad_drc_errors"),
        "kicad_drc_warnings": q.get("kicad_drc_warnings"),
        "freerouting_ok": q.get("freerouting_ok"),
        "freerouting_skipped": q.get("freerouting_skipped"),
        "freerouting_tracks": q.get("freerouting_track_count"),
        "build_ready": q.get("build_ready"),
        "pcb": _pcb_stats(pcb) if pcb else {},
    }


def run_catalog_sample(
    *,
    out_root: Path,
    sample: int,
    autoroute: bool,
) -> List[Dict[str, Any]]:
    ids = CATALOG_BUILD_IDS[: max(1, sample)]
    rows: List[Dict[str, Any]] = []
    for bid in ids:
        if autoroute:
            os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "1"
        else:
            os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
        os.environ["HARDWARE_SPLICER_JLC_ENRICH"] = "0"
        out = out_root / "catalog" / bid
        t0 = time.time()
        r = compile_catalog_build(bid, str(out), export_gerber=False)
        rows.append(_row_from_result(bid, r, time.time() - t0))
    return rows


def run_kicad_netlist(path: Path, out_root: Path, *, autoroute: bool) -> Dict[str, Any]:
    if autoroute:
        os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "1"
    else:
        os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    os.environ["HARDWARE_SPLICER_JLC_ENRICH"] = "0"
    nl = parse_kicad_netlist(path.read_text(encoding="utf-8"))
    out = out_root / "kicad_netlist"
    t0 = time.time()
    r = compile_from_netlist(nl, out, build_id=path.stem, export_gerber=False)
    row = _row_from_result(path.stem, r, time.time() - t0)
    row["source"] = str(path)
    row["components"] = len(nl.components)
    row["nets"] = len(nl.nets)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Low-footprint engine stress report")
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_engine_stress"))
    parser.add_argument("--sample", type=int, default=3, help="Catalog builds to test (default 3)")
    parser.add_argument(
        "--autoroute",
        action="store_true",
        help="Enable FreeRouting (heavy; keep --sample small)",
    )
    parser.add_argument(
        "--kicad-netlist",
        type=Path,
        default=None,
        help="Optional KiCad netlist path to ingest",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Write report JSON here")
    args = parser.parse_args()

    if args.autoroute and args.sample > 2:
        print("warning: --autoroute with sample>2 is CPU-heavy; consider --sample 1", file=sys.stderr)

    args.out.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "mode": {"autoroute": args.autoroute, "catalog_sample": args.sample},
        "catalog": run_catalog_sample(out_root=args.out, sample=args.sample, autoroute=args.autoroute),
    }
    if args.kicad_netlist and args.kicad_netlist.is_file():
        report["kicad_netlist"] = run_kicad_netlist(args.kicad_netlist, args.out, autoroute=args.autoroute)
    elif Path("examples/main_ctrl_esp32_servo.net").is_file():
        report["kicad_netlist"] = run_kicad_netlist(
            Path("examples/main_ctrl_esp32_servo.net"), args.out, autoroute=args.autoroute
        )

    cat = report["catalog"]
    report["summary"] = {
        "catalog_tested": len(cat),
        "catalog_ok": sum(1 for x in cat if x.get("ok")),
        "kicad_drc_pass": sum(1 for x in cat if x.get("kicad_drc_pass")),
        "freerouting_ok": sum(1 for x in cat if x.get("freerouting_ok")),
        "total_seconds": round(sum(x.get("seconds", 0) for x in cat), 2),
    }

    text = json.dumps(report, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")
    return 0 if report["summary"]["catalog_ok"] == report["summary"]["catalog_tested"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
