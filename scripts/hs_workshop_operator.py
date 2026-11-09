#!/usr/bin/env python3
"""One HS work-order: registered tool selection -> real checks -> honest outcome."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.workshop_operator import list_cases,run_workshop_operator


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list",action="store_true",help="Show the bounded capability routes")
    p.add_argument("--case",help="Registered case ID (never an arbitrary shell command)")
    p.add_argument("--out",type=Path,help="Fresh output directory")
    p.add_argument("--execute",action="store_true",
                   help="Run software-only existing engineering tools, never hardware")
    args=p.parse_args()
    if args.list:
        print(json.dumps({"cases":list_cases()},indent=2))
        return 0
    if not args.case or not args.out:
        p.error("--case and --out are required unless --list is set")
    try:
        result=run_workshop_operator(args.case,out_dir=args.out,execute=args.execute)
    except (ValueError,OSError) as exc:
        print(json.dumps({"ok":False,"error":str(exc)},indent=2),file=sys.stderr)
        return 2
    print(json.dumps({
        "case_id":result["case_id"],"status":result["status"],
        "engineering_acceptance":result["engineering_acceptance"],
        "physical_validation":result["physical_validation"],
        "fabrication_authorized":result["fabrication_authorized"],
        "result_file":str(args.out/"HS_OPERATOR_RESULT.json"),
    },indent=2))
    return 0 if result["engineering_acceptance"] or not args.execute else 2


if __name__=="__main__":
    raise SystemExit(main())
