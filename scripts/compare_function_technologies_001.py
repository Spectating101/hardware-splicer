#!/usr/bin/env python3
"""Compare process technologies against a source-bound HS functional intent."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.function_technology_selection import compile_option_study


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--functional-package",required=True,type=Path)
    parser.add_argument("--options",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.options.stat().st_size > 128*1024:
            raise ValueError("Options catalog size exceeds bounded 128KiB")
        receipt=compile_option_study(args.functional_package,args.options,args.out)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print("TECHNOLOGY STUDY REFUSED: "+str(e),file=sys.stderr)
        return 1
    print(json.dumps(receipt,sort_keys=True,indent=2))
    print("DESIGN STUDY ONLY: selected mechanism is a hypothesis, not tested water treatment.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
