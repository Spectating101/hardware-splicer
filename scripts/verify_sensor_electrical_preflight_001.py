#!/usr/bin/env python3
"""Generate the fail-closed symbolic electrical and BOM audit for HS sensor 001."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.sensor_electrical_preflight import write

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",required=True,type=Path)
    a=p.parse_args()
    try:
        electrical,bom=write(a.project)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f"ELECTRICAL PREFLIGHT REFUSED: {exc}",file=sys.stderr)
        return 1
    print("Verified catalog wiring and compiled-source pin contracts; "
          f"{len(bom['parts'])} catalog modules UNQUALIFIED. "
          "No physical, supplier or native KiCad authorization.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
