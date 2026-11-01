#!/usr/bin/env python3
"""Build real STEP glTF showroom inputs from verified HS native multi-CAD+CADCLAW."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.teardown_cad_showcase import create
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--multicad",type=Path,required=True)
    p.add_argument("--cadclaw",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:
        print(json.dumps(create(a.multicad,a.cadclaw,a.out),indent=2))
    except (ValueError,TypeError,KeyError, OSError) as exc:
        print("Native STEP SHOWROOM REFUSED: "+str(exc),file=sys.stderr)
        return 1
    return 0
if __name__=="__main__":
    raise SystemExit(main())
