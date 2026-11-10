"""Run and independently audit one function-to-printable-CAD candidate search."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from hardware_splicer.function_print_geometry import run_design,audit_bundle

ROOT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,default=ROOT/"design_request.json")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    req=json.loads(args.spec.read_text())
    result=run_design(req,args.out)
    audit=audit_bundle(req,args.out)
    (args.out/"NATIVE_AUDIT.json").write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps({
      "selected":result["selected"],
      "feasible":result["ranked_feasible"],
      "solid_volume_reduction_vs_plate_percent":result["vs_plate_solid_volume_reduction_pct"],
      "native_shapes_reimported":audit["native_shape_count"],
      "print_approved":result["authority"]["fabrication_release_authorized"],
    },indent=2))
if __name__=="__main__":
    main()
