#!/usr/bin/env python3
"""Produce fail-closed mounted-device review after native CAD mount tests."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.mounted_device_acceptance import assess_native_mounted_reference

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engines",required=True,type=Path)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--cad-recipe",required=True,type=Path)
    args=p.parse_args()
    result=assess_native_mounted_reference(
        pcb_path=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb",
        seed_path=ROOT/"examples/external_engines/cad/spi_adapter_shell.json",
        mounted_recipe_path=args.cad_recipe,
        mounting_manifest_path=args.manifest,
        native_engine_dir=args.engines,output_dir=args.out)
    print(json.dumps({"status":result["status"],
                      "mount_count":result["mount_count"],
                      "native_material_samples":result["native_3d_material_void_checks"],
                      "source_pcb_envelope_blockers":result["source_pcb_envelope_blockers"],
                      "fabrication_authorized":False},indent=2))
if __name__=="__main__":
    main()
