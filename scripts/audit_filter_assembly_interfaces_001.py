#!/usr/bin/env python3
"""Audit documentary Slim Line assembly interfaces against actual native CAD receipts."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.filter_assembly_gate import package_assembly


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--component-package",required=True,type=Path)
    p.add_argument("--assembly-interfaces",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    try:
        if args.assembly_interfaces.stat().st_size>128*1024:
            raise ValueError("Assembly interface source too large")
        receipt=package_assembly(args.component_package,args.assembly_interfaces,args.out)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print("ASSEMBLY INTERFACE STUDY REFUSED:",e,file=sys.stderr)
        return 1
    print(json.dumps(receipt,indent=2,sort_keys=True))
    print("DOCUMENTARY ASSEMBLY GATE: exact bracket/seat fit, hydraulics and water quality remain UNVERIFIED.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
