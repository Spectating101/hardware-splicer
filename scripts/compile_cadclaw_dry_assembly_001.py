#!/usr/bin/env python3
"""Generate source-bound dry stand STEP parts and CADCLAW assembly spec."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.cadclaw_dry_product import author
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product-package",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:print(json.dumps(author(a.product_package,a.out),sort_keys=True,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("CADCLAW SOURCE AUTHORING REFUSED:",e,file=sys.stderr)
        raise SystemExit(1)
