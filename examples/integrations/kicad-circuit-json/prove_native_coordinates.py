#!/usr/bin/env python3
"""Native KiCad source UUID/position correlation with converter geometry.

Uses official KiCad CLI for electrical export and native .kicad_sch source for
UUIDs/position. Produces evidence sidecar; never merges visual records into
authoritative electrical circuit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from hardware_splicer.integrations.kicad_native_coordinate_proof import prove_native_visual_positions


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schematic",type=Path,required=True)
    parser.add_argument("--converter-json",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    cli=shutil.which("kicad-cli")
    if cli is None:
        parser.error("Official KiCad CLI required to verify exported native component UUIDs")
    if not args.schematic.is_file() or args.schematic.suffix!=".kicad_sch":
        parser.error("--schematic must be an existing .kicad_sch")
    docs=json.loads(args.converter_json.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="hs-native-geometry-") as root:
        net=Path(root)/"official.net"
        task=subprocess.run([
            cli,"sch","export","netlist","--format","kicadsexpr",
            "--output",str(net),str(args.schematic.resolve())
        ],capture_output=True,text=True,timeout=120)
        if task.returncode!=0 or not net.is_file():
            raise RuntimeError("Official KiCad netlist export failed: "+(task.stderr or task.stdout)[-750:])
        result=prove_native_visual_positions(
            args.schematic.read_text(encoding="utf-8"),
            net.read_text(encoding="utf-8"),
            docs,
        )
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "source_components":result["native_component_count"],
        "position_correlated":result["source_position_correlated_instances"],
        "pin_number_correlated":result["source_position_correlated_pins"],
        "metadata_anchors":result["original_unique_metadata_anchors"],
        "additional_duplicate_type_position_matches":result["additional_coordinate_correlations"],
        "native_uuid_in_converter":False,
        "symbol_shape_and_pin_geometry_verified":False,
        "visual_merge_allowed":False,
    },indent=2))


if __name__=="__main__":
    main()
