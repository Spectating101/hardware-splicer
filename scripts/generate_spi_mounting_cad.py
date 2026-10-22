#!/usr/bin/env python3
"""Compile mount/boss CAD operations from the verified KiCad SPI board."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.pcb_mounting_cad import generate_pcb_mounted_shell  # noqa E402

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pcb",type=Path,default=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb")
    p.add_argument("--seed",type=Path,default=ROOT/"examples/external_engines/cad/spi_adapter_shell.json")
    p.add_argument("--out",type=Path,default=ROOT/"examples/external_engines/cad/spi_adapter_with_mounts.json")
    p.add_argument("--manifest",type=Path,required=True)
    args=p.parse_args()
    r=generate_pcb_mounted_shell(pcb_path=args.pcb,seed_recipe_path=args.seed,
        output_recipe_path=args.out,output_manifest_path=args.manifest)
    print(json.dumps({"mounts":r["mount_count"],"source_pcb_sha256":r["input_pcb_sha256"],
      "cad_sha256":r["generated_solidcraft_script_sha256"],
      "mechanical_release_authorized":False},indent=2))
if __name__=="__main__":
    main()
