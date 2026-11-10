"""Independent real STEP/STL reimport and finer 1-degree hinge sweep."""
from __future__ import annotations
import json
from pathlib import Path
from hardware_splicer.functional_hinge_audit import audit,fine_selected
HERE=Path(__file__).resolve().parent

def main():
    folder=HERE/"generated"
    spec=json.loads((HERE/"reference_spec.json").read_text())
    audited=audit(spec,folder)
    print("Native audit",json.dumps(audited),flush=True)
    precise=fine_selected(spec,folder)
    outfile=folder/"ONE_DEGREE_SWEEP.json"
    if outfile.exists():
        raise SystemExit("Cannot overwrite frozen finer-sweep evidence")
    outfile.write_text(json.dumps(precise,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "selected":precise["selected"],"angles_checked":precise["angle_count"],
        "all_declared_gates_passed":precise["all_nominal_gates_pass"],
        "minimum_screen_gap_mm":precise["minimum_mock_screen_gap_mm"],
        "smallest_printed_part_gap_mm":precise["minimum_printed_clearance_mm"],
        "physical_fit_verified":precise["physical_hinge_fabrication_verified"]
    },indent=2))
if __name__=="__main__":main()
