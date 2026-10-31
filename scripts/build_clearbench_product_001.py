#!/usr/bin/env python3
"""Generate a complete ClearBench S1 digital product assembly from HS evidence."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.whole_product_sample import build

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assembly-package",required=True,type=Path)
    p.add_argument("--product",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    try: out=build(a.assembly_package,a.product,a.out)
    except (OSError,ValueError,TypeError,KeyError) as e:
        print("WHOLE PRODUCT REFUSED:",e,file=sys.stderr)
        return 1
    print(json.dumps(out,indent=2,sort_keys=True))
    print("Complete DIGITAL product assembly only; not manufactured or wet-tested.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
