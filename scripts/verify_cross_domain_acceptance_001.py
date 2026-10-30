#!/usr/bin/env python3
"""Reconcile native CAD and firmware evidence from two independent CI jobs."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.engineering_acceptance_sensor import produce

def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry",required=True,type=Path)
    parser.add_argument("--firmware",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    try:
        produce(args.geometry,args.firmware,args.out)
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(f"Cross-domain acceptance REFUSED: {error}",file=sys.stderr)
        return 1
    print("CROSS-DOMAIN SOURCE/HASH/TOOLCHAIN CONSISTENCY: PASS. PHYSICAL BUILD: BLOCKED.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
