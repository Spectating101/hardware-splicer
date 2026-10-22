#!/usr/bin/env python3
"""Screen exact source Samtec headers and provisional 3D insertion corridors."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.connector_mating_volume import inspect_mating_volume

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pcb",type=Path,default=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb")
    p.add_argument("--bom",type=Path,default=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/BOM.csv")
    p.add_argument("--mount-manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--allowance-mm",type=float,default=2.0)
    args=p.parse_args()
    r=inspect_mating_volume(
        pcb_path=args.pcb,bom_path=args.bom,mounting_manifest_path=args.mount_manifest,
        output_path=args.out,radial_allowance_mm=args.allowance_mm)
    print(json.dumps({"status":r["status"],"connectors":r["examined_connector_count"],
                      "geometry_blockers":r["nominal_geometry_blocked_references"],
                      "mating_hardware_qualified":False},indent=2))
    if r["status"]=="blocked_nominal_3d_insertion_geometry":
        raise SystemExit(1)

if __name__=="__main__":
    main()
