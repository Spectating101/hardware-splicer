#!/usr/bin/env python3
"""Author independent native build123d parts and PartCAD package from verified HS STEP."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.multicad_toolchain import prepare_from_cadclaw,author_with_build123d,check_native_outputs

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product",type=Path,required=True)
    p.add_argument("--cadclaw",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:
        prepare_from_cadclaw(a.product,a.cadclaw,a.out)
        evidence=author_with_build123d(a.out)
        check_native_outputs(a.out)
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("Multi-CAD native integration refused: "+str(e),file=sys.stderr)
        return 1
    print(json.dumps(evidence,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
