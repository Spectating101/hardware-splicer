#!/usr/bin/env python3
"""Verify actual HTML, Playwright browser interactions and source-bound evidence."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.teardown_product import validate_native_browser
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product",type=Path,required=True)
    a=p.parse_args()
    try:
        report=validate_native_browser(a.product)
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("HS Teardown native acceptance REFUSED: "+str(e),file=sys.stderr)
        return 1
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
