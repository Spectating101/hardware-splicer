"""Execute a reproducible real multi-part cyberdeck hinge source study."""
from __future__ import annotations
import json
import argparse
from pathlib import Path
from hardware_splicer.functional_hinge_assembly import execute,validate

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,default=HERE/"reference_spec.json")
    p.add_argument("--out",type=Path,required=True)
    opts=p.parse_args()
    req=validate(json.loads(opts.spec.read_text()))
    report=execute(req,opts.out)
    print(json.dumps({
        "status":"concept_assembly_no_physical_authority",
        "selected":report["selected"],"feasible_order":report["feasible_order"],
        "positions_per_candidate":37,
        "candidates":[{
            "id":x["id"],"pass":x["nominal_mechanism_feasible"],
            "thickness_mm":x["geometry"]["folded_solid_height_mm"],
            "min_screen_gap_mm":x["geometry"]["min_modelled_screen_gap_mm"],
            "min_screen_vs_other_leaf_mm":x["geometry"]["min_screen_to_other_leaf_gap_mm"],
            "failed_gates":[k for k,v in x["checks"].items() if not v],
        } for x in report["candidates"]],
    },indent=2))
if __name__=="__main__":
    main()
