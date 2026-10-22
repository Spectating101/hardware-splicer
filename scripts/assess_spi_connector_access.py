#!/usr/bin/env python3
"""Assess source KiCad connector accessibility in proposed open-top SPI shell.

Outputs nominal footprint/courtyard projection, pin-net trace, and unresolved
mating connector/cable evidence; does not certify physical assembly.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.connector_access_plan import inspect_connector_access


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pcb",type=Path,default=ROOT/"hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb")
    p.add_argument("--mount-manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--margin-mm",type=float,default=2.0)
    args=p.parse_args()
    result=inspect_connector_access(pcb_path=args.pcb,
        mounting_manifest_path=args.mount_manifest,output_path=args.out,
        side_margin_mm=args.margin_mm)
    print(json.dumps({"status":result["status"],"connectors":result["connector_count"],
                      "pcb_source_sha256":result["pcb_source_sha256"],
                      "physical_mating_verified":False},indent=2))
    if result["status"]!="nominal_open_top_projection_clear_unverified":
        raise SystemExit(1)
if __name__=="__main__":
    main()
