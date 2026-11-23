#!/usr/bin/env python3
"""Produce a real upstream-Teardown machine entrypoint from verified HS CAD evidence."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hardware_splicer.teardown_product import export

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--multicad",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:
        result=export(a.multicad,a.out)
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("HS Teardown generation REFUSED: "+str(e),file=sys.stderr)
        return 1
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
