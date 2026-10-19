"""Run source recheck then independent virtual software/controller feasibility.

   PYTHONPATH=src python -m scripts.run_autonomous_splice_feasibility --out /tmp/hs-splice-feasibility

No hardware, no purchases, no power-on. All physical claims stay blocked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.sdk import investigate_public_donor_sources
from hardware_splicer.autonomous_splice_feasibility import evaluate_splice_feasibility


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--source-snapshot",type=Path,
                        help="Previously recorded (not live) controller JSON, useful for deterministic offline replay")
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    source=(json.loads(args.source_snapshot.read_text()) if args.source_snapshot
            else investigate_public_donor_sources())
    report=evaluate_splice_feasibility(source)
    p=args.out/"AUTONOMOUS_SPLICE_FEASIBILITY.json"
    p.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    snap=args.out/"SOURCE_EVIDENCE_SNAPSHOT.json"
    snap.write_text(json.dumps(source,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps({
        "virtual_cases_passed":report["virtual_control_software"]["passed"],
        "virtual_cases_total":report["virtual_control_software"]["total"],
        "motor_driver_candidate":report["conditional_motor_driver_plan"]["planner_result"],
        "electrical_blockers":report["conditional_motor_driver_plan"]["missing_evidence"],
        "physical_gates_open":report["physical_gate_count_open"],
        "physical_product_proven":report["novel_product_functionally_proven"],
        "report":str(p),
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
