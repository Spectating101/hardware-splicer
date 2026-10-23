#!/usr/bin/env python3
"""Audit converter pin positions using native KiCad symbol-library pins.

No source wire inference, PCB routing check, geometry merge, or physical
manufacturing authority. Requires real kicad-cli and converter output.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from hardware_splicer.integrations.kicad_native_pin_geometry_audit import verify_native_pin_positions


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schematic",required=True,type=Path)
    ap.add_argument("--converter-json",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    cli=shutil.which("kicad-cli")
    if not cli:
        ap.error("genuine KiCad CLI is required for independent source export")
    if not args.schematic.is_file() or args.schematic.suffix!=".kicad_sch":
        ap.error("schematic must be a real .kicad_sch file")
    docs=json.loads(args.converter_json.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="hs-kicad-pin-geometry-") as temp:
        export=Path(temp)/"source.net"
        process=subprocess.run([
            cli,"sch","export","netlist","--format","kicadsexpr",
            "--output",str(export),str(args.schematic.resolve()),
        ],capture_output=True,text=True,timeout=120)
        if process.returncode or not export.exists():
            raise RuntimeError("Official netlist export failed: "+
                               (process.stderr or process.stdout)[-850:])
        receipt=verify_native_pin_positions(
            args.schematic.read_text(encoding="utf-8"),
            export.read_text(encoding="utf-8"),
            docs,
        )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "source_component_count":receipt["source_components"],
        "verified_component_centers":receipt["component_centers_correlated"],
        "official_pin_count":receipt["source_numbered_pins"],
        "verified_pin_centers":receipt["source_library_pin_positions_verified"],
        "failed_checks":receipt["failed_pin_or_component_checks"],
        "all_pin_centers_correlated":receipt["all_pin_centers_correlated"],
        "native_converter_uuid_authenticated":False,
        "visual_merge_allowed":False,
        "fabrication_authorized":False,
    },indent=2))


if __name__=="__main__":
    main()
