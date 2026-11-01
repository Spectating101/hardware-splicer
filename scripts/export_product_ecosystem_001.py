#!/usr/bin/env python3
"""Export one source-bound HS product to external backend native data contracts."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.product_ecosystem_bridge import export

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-package",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    try: print(json.dumps(export(args.product_package,args.out),indent=2,sort_keys=True))
    except (ValueError,OSError,TypeError,KeyError) as exc:
        print("EXTERNAL TOOL ADAPTER REFUSED:",str(exc),file=sys.stderr)
        raise SystemExit(1)
