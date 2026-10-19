"""Autonomous bounded Taiwan donor source checks; no human spot-check needed.

PYTHONPATH=src python -m scripts.run_autonomous_donor_evidence --out /tmp/hs-donor-evidence
Runs exact-source HTTP checks, two mission-specific diagnosis revisions,
emits receipts and stops without buying or accessing physical hardware.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.autonomous_evidence_controller import run_public_evidence_investigation

ROOT=Path(__file__).resolve().parents[1]


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repair",type=Path,default=ROOT/"examples/dual_track/repair_ls2208_unverified.json")
    parser.add_argument("--splice",type=Path,default=ROOT/"examples/dual_track/splice_four_marketplace_donors_unverified.json")
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    repair=json.loads(args.repair.read_text(encoding="utf-8"))
    splice=json.loads(args.splice.read_text(encoding="utf-8"))
    report=run_public_evidence_investigation(repair,splice)
    args.out.mkdir(parents=True,exist_ok=True)
    path=args.out/"AUTONOMOUS_SOURCE_INVESTIGATION.json"
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    short={
        "source_fetches":report["bounded_source_fetches"],
        "marketplace_seller_records_reobserved":sum(
            x["status"]=="MARKET_LISTING_METADATA_REOBSERVED"
            for x in report["source_receipts"]
        ),
        "manufacturer_family_specs_reobserved":sum(
            x["status"]=="MANUFACTURER_FAMILY_SPEC_REOBSERVED"
            for x in report["source_receipts"]
        ),
        "repair_first_hypothesis":report["repair"]["analysis"]["first_hypothesis_id"],
        "splicing_unverified_interfaces":len([
            x for x in report["splicing"]["interconnection_gaps"]
            if x["type"]=="interface_unknown"
        ]),
        "mission_successes":0,
        "stop_reason":report["stop_reason"],
        "output":str(path),
    }
    (args.out/"AUTONOMOUS_EVIDENCE_SUMMARY.json").write_text(json.dumps(short,indent=2)+"\n")
    print(json.dumps(short,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
