#!/usr/bin/env python3
"""Validate a converter-captured UUID companion and emit a read-only source overlay.

1. Run: npm run convert:provenance -- schematic.kicad_sch out.json uuid.json
2. Run: python verify_uuid_overlay.py --schematic schematic.kicad_sch
       --circuit-json out.json --provenance uuid.json --out overlay.json

Requires genuine KiCad CLI. Does not infer schematic traces or build hardware.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from hardware_splicer.integrations.kicad_runtime_uuid_provenance import (
    build_uuid_linked_source_overlay,
)


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schematic",type=Path,required=True)
    p.add_argument("--circuit-json",type=Path,required=True)
    p.add_argument("--provenance",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    cli=shutil.which("kicad-cli")
    if not cli:
        p.error("kicad-cli is required for independently verified source export")
    if not x.schematic.is_file() or x.schematic.suffix!=".kicad_sch":
        p.error("--schematic must be an existing KiCad .kicad_sch source")
    with tempfile.TemporaryDirectory(prefix="hs-uuid-overlay-") as work:
        export=Path(work)/"independent.net"
        result=subprocess.run([
            cli,"sch","export","netlist","--format","kicadsexpr",
            "--output",str(export),str(x.schematic.resolve()),
        ],capture_output=True,text=True,timeout=120)
        if result.returncode or not export.exists():
            raise RuntimeError("Independent KiCad source export failed: "+(result.stderr or result.stdout)[-750:])
        output=build_uuid_linked_source_overlay(
            x.schematic.read_bytes(),export.read_text(encoding="utf-8"),
            x.circuit_json.read_bytes(),x.provenance.read_bytes(),
        )
    x.out.parent.mkdir(parents=True,exist_ok=True)
    x.out.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "native_uuid_links_verified":output["verification"]["native_uuid_entries_verified"],
        "visual_components":output["total_visual_components"],
        "visual_ports":output["total_visual_pins"],
        "physical_parts":output["physical_components"],
        "physical_pins_with_independent_net":output["physical_pins_with_source_net"],
        "authenticated_wire_geometry":False,
        "visual_electrical_merge_authorized":False,
        "fabrication_authorized":False,
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
