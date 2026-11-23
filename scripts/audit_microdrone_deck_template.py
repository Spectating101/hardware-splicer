#!/usr/bin/env python3
"""Audit Bitcraze's actual KiCad deck connector template against HS design.

This reads the historic template .net to establish real P1/P2 connector pin
names. It does NOT convert the legacy schematic, add sensor components, route
a board, run modern KiCad ERC/DRC or grant fabrication authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

REQUIRED={("P1",1):"VCC",("P1",4):"SDA",("P1",5):"SCL",("P1",10):"GND",("P2",8):"OW"}
VENDOR_REPO="bitcraze/crazyflie2-exp-template-electronics"


def audit(vendor:Path,commit:str,design_file:Path,out_dir:Path)->dict:
    vendor=vendor.resolve()
    actual=subprocess.run(["git","-C",str(vendor),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
    if actual!=commit or len(actual)!=40:
        raise ValueError("Vendor template revision mismatch")
    source=vendor/"ecad/template.net"
    data=source.read_bytes()
    text=data.decode("utf-8")
    if "eeschema (2014-" not in text:
        raise ValueError("Expected original legacy Bitcraze template, not migrated netlist")
    left=text.split("(libpart (lib connectors) (part CF_EXP_LEFT)",1)[1].split("(libpart",1)[0]
    right=text.split("(libpart (lib connectors) (part CF_EXP_RIGHT)",1)[1].split("(libpart",1)[0]
    extracted={}
    for ref,chunk in (("P1",left),("P2",right)):
        pins=re.findall(r"\(pin\s+\(num\s+(\d+)\)\s+\(name\s+([^\)]+)\)",chunk)
        if len(pins)!=10:
            raise ValueError(f"Missing 10 {ref} connector pins")
        for n,name in pins:
            extracted[(ref,int(n))]=name.strip()
    for key,label in REQUIRED.items():
        if extracted.get(key)!=label:
            raise ValueError(f"Changed deck connector pin {key}: {extracted.get(key)} != {label}")
    design=json.loads(design_file.read_text())
    if design["candidate"]["electrical"]["connector_pin_mapping_verified"]:
        raise ValueError("Cannot accept a complete pin mapping from a legacy reference template alone")
    if design["baseline"]["model"]!="Crazyflie 2.1+":
        raise ValueError("Wrong Crazyflie reference variant")
    receipt={
      "schema_version":"hardware_splicer.microdrone_deck_template_audit.v1",
      "upstream_repo":VENDOR_REPO,
      "commit":actual,
      "upstream_netlist_file":"ecad/template.net",
      "upstream_netlist_sha256":hashlib.sha256(data).hexdigest(),
      "design_input_sha256":hashlib.sha256(design_file.read_bytes()).hexdigest(),
      "verified_source_pin_names":{f"{p}.{n}":label for (p,n),label in REQUIRED.items()},
      "source_connector_count":2,
      "source_pin_count":20,
      "origin_era":"2014 KiCad legacy",
      "legacy_template_audit_pass":True,
      "new_sensor_circuit_authored":False,
      "modern_kicad_native_schematic_validated":False,
      "board_routed_or_drc_validated":False,
      "electrical_pin_evidence_complete":False,
      "manufacturing_authorized":False,
      "notes":[
        "Template's pin names are from legacy CF2.0, not independently measured on purchased CF2.1+",
        "2014 schematic and library require compatible migration and revised symbols",
        "BME688 and DS28E05 power and communications pins have NOT been wired",
        "Do not use 3V expansion power until the exact die/board power characteristics are checked",
      ],
    }
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError("Refuse overwrite of existing ECAD audit")
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"DECK_ECAD_UPSTREAM_AUDIT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return receipt


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vendor",type=Path,required=True)
    p.add_argument("--commit",required=True)
    p.add_argument("--design",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(audit(a.vendor,a.commit,a.design,a.out),indent=2))
