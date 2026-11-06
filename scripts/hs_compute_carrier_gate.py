#!/usr/bin/env python3
"""Read-only audit of reusable HS compute carrier evidence and authorizations."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"src"))
from hardware_splicer.compute_carrier_reference_gate import assess

DEFAULT="examples/cyberdeck/compute_carrier/evidence/source_contract_20261107.json"
OUT="examples/cyberdeck/compute_carrier/evidence/assessment.json"

def inside(relative: str) -> Path:
    p=Path(relative)
    resolved=(REPO/p).resolve()
    if p.is_absolute() or not resolved.is_relative_to(REPO):
        raise ValueError("path must remain inside HS repository")
    return resolved

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",default=DEFAULT)
    parser.add_argument("--out",default=OUT)
    parser.add_argument("--check-only",action="store_true")
    args=parser.parse_args()
    result=assess(inside(args.source).read_bytes())
    if not args.check_only:
        dest=inside(args.out)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Official carrier CAD and KiCad reference located:",result["source_designs_available"])
    print("Upstream agentic pinout data trusted:",result["upstream_db_trusted_for_pinout"])
    print("Unresolved HS carrier gates:",result["blocker_count"])
    print("Safe to fabricate:",result["safe_to_fabricate"])
    print("Direct CM4<->CM5 insertion approved:",result["safe_to_power_any_cross_module_swap"])
    return 0

if __name__=="__main__":
    raise SystemExit(main())
