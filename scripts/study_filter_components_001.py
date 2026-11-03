#!/usr/bin/env python3
"""Bind manufacturer-documented component candidates to a function-first study."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.filter_component_preflight import package_parts

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--functional-package",required=True,type=Path)
    parser.add_argument("--technology-study",required=True,type=Path)
    parser.add_argument("--components",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.components.stat().st_size>128*1024:
            raise ValueError("component file too large")
        result=package_parts(args.functional_package,args.technology_study,args.components,args.out)
    except (ValueError,OSError,KeyError,TypeError) as e:
        print("FILTER COMPONENT FEASIBILITY REFUSED:",e,file=sys.stderr)
        return 1
    print(json.dumps(result,indent=2,sort_keys=True))
    print("MANUFACTURER-DOCUMENTED CANDIDATES, NOT PHYSICALLY QUALIFIED OR WATER-SAFE.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
