#!/usr/bin/env python3
"""Audit third-party Circuit JSON visual identity against official KiCad export.

The geometry is NEVER merged or treated as PCB/repair authority. Only exact
unique library+value+complete pin number correspondences are proposed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from hardware_splicer.integrations.kicad_geometry_identity_audit import audit_converter_geometry_identity


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schematic",type=Path,required=True)
    parser.add_argument("--converter-json",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if not args.schematic.is_file() or args.schematic.suffix!=".kicad_sch":
        parser.error("must supply an existing .kicad_sch")
    cli=shutil.which("kicad-cli")
    if not cli:
        parser.error("official KiCad CLI is required for this audit")
    converter_docs=json.loads(args.converter_json.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="hs-geometry-identity-") as directory:
        exported=Path(directory)/"official.net"
        result=subprocess.run(
            [cli,"sch","export","netlist","--format","kicadsexpr",
             "--output",str(exported),str(args.schematic.resolve())],
            capture_output=True,text=True,timeout=120,
        )
        if result.returncode or not exported.is_file():
            raise RuntimeError("KiCad source export failed: "+(result.stderr or result.stdout)[-600:])
        report=audit_converter_geometry_identity(
            exported.read_text(encoding="utf-8"),
            converter_docs,
            schematic_sha256=hashlib.sha256(args.schematic.read_bytes()).hexdigest(),
        )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "source_components":report["source_component_count"],
        "upstream_visual_components":report["converter_source_component_count"],
        "candidate_matches":report["unique_candidate_matches"],
        "candidate_matched_pins":report["matched_source_pin_numbers"],
        "ambiguous_source_components":len(report["unmatched_kicad_references"]),
        "geometry_merged":False,
        "source_uuid_confirmed":False,
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
