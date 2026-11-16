#!/usr/bin/env python3
"""Compile a functional device brief into HS MachineProject and evidence gates."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.function_intent_bridge import package_intent

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    try:
        if args.brief.stat().st_size > 128*1024:
            raise ValueError("Functional brief above allowed 128KiB")
        receipt=package_intent(json.loads(args.brief.read_text()),args.out)
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(f"Function-first compilation REFUSED: {e}",file=sys.stderr)
        return 1
    print(json.dumps(receipt,indent=2,sort_keys=True))
    print("FUNCTIONAL CONCEPT ONLY: no component qualification, fabrication, drinking-water or physical authority.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
