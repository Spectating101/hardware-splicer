"""Actually slice every geometry with pinned PrusaSlicer CLI and preserve receipts.

Generic slicer output is NOT approved for printer execution. Raw machine-
specific G-code stays in local scratch; source-linked audit receipts
can be committed to Git without claiming certified toolpaths.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from hardware_splicer.function_print_slicer import run_slicer_comparison, audit_slicer_report

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,default=HERE/"design_request.json")
    p.add_argument("--profile",type=Path,default=HERE/"slicer_profile.json")
    p.add_argument("--cad-dir",type=Path,default=HERE/"generated")
    p.add_argument("--slicer",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    req=json.loads(args.spec.read_text())
    profile=json.loads(args.profile.read_text())
    result=run_slicer_comparison(req,profile,
                                 cad_dir=args.cad_dir,bin_path=args.slicer,out=args.out)
    if not result["all_calls_successful"]:
        print("One or more native slices failed; original records retained, no rerolls")
        raise SystemExit(1)
    audit=audit_slicer_report(req,profile,cad_dir=args.cad_dir,
                              out=args.out,require_gcode=True)
    (args.out/"NATIVE_SLICER_AUDIT.json").write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps({
        "actual_slicer_runs":result["attempt_count"],
        "successful":result["all_calls_successful"],
        "native_slicer":result["PrusaSlicer_version_text"],
        "ranking":result["profile_rankings"],
        "physical_printer_execution_authorized":False,
    },indent=2))
if __name__=="__main__":
    main()
