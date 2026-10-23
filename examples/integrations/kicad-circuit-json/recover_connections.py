#!/usr/bin/env python3
"""KiCad source-authoritative Circuit JSON recovery (does not merge geometry).

Example, with an actual user-owned schematic:
  python recover_connections.py \
    --schematic device.kicad_sch \
    --converter-json upstream_converter.json \
    --out /tmp/verified_connected_source.json \
    --receipt /tmp/verification.json

Source topology uses official KiCad CLI. If --netlist-export is provided
instead, the caller is responsible for the supplied netlist's authenticity.
The upstream converter's geometry remains a *separate* unverified artifact.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from hardware_splicer.integrations.kicad_circuit_json_recovery import write_recovery


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--schematic",type=Path,help="User-owned KiCad schematic; invokes real kicad-cli")
    selection.add_argument("--netlist-export",type=Path,help="Existing verified/exported KiCad S-expression netlist")
    parser.add_argument("--converter-json",type=Path,help="Optional upstream geometry-only converter output")
    parser.add_argument("--out",required=True,type=Path,help="Authoritative recovered Circuit JSON array")
    parser.add_argument("--receipt",type=Path,help="Optional sidecar strict parity/provenance report")
    args=parser.parse_args()
    converted=None
    if args.converter_json:
        converted=json.loads(args.converter_json.read_text(encoding="utf-8"))
        if not isinstance(converted,list) or not all(isinstance(doc,dict) for doc in converted):
            parser.error("--converter-json must be a Circuit JSON document array")
    if args.schematic:
        command=shutil.which("kicad-cli")
        if command is None:
            parser.error("kicad-cli not installed; use actual KiCad or explicit --netlist-export")
        if not args.schematic.is_file() or args.schematic.suffix != ".kicad_sch":
            parser.error("--schematic must be a local .kicad_sch file")
        with tempfile.TemporaryDirectory(prefix="hs-kicad-topology-") as directory:
            export=Path(directory)/"official.net"
            process=subprocess.run(
                [command,"sch","export","netlist","--format","kicadsexpr",
                 "--output",str(export),str(args.schematic.resolve())],
                capture_output=True,text=True,timeout=120,check=False,
            )
            if process.returncode != 0 or not export.exists():
                raise RuntimeError("KiCad CLI source export failed: " + (process.stderr or process.stdout)[-1200:])
            text=export.read_text(encoding="utf-8")
    else:
        text=args.netlist_export.read_text(encoding="utf-8")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
    result=write_recovery(
        text,str(args.out),
        external_converter_docs=converted,
        receipt_json=str(args.receipt) if args.receipt else None,
    )
    print(json.dumps({
        "authoritative_component_count": result["components"],
        "connected_nets": result["connected_multi_pin_nets"],
        "connected_pin_memberships": result["imported_multi_pin_memberships"],
        "exact_source_round_trip": result["topology_exact_multi_pin_match"],
        "converter_geometry_merged": False,
        "fabrication_authorized": False,
    }, indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
