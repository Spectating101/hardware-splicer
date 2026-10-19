"""Run old and canonical HS planning separately; audit source-bound candidates.

Preserves historical baseline; never rewrites benchmark acceptance to force
green. A conditional design is not a physically viable machine.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from hardware_splicer.source_agnostic_benchmark import (
    evaluate_source_agnostic_suite,load_source_agnostic_scenario,
)
from hardware_splicer.source_bound_candidate_trial import build_source_bound_candidate
from hardware_splicer.source_bound_candidate_oracle import independently_audit_source_bound_candidate

ROOT=Path(__file__).resolve().parents[1]
CASES=ROOT/"examples/source_agnostic"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--cases",type=Path,default=CASES)
    parser.add_argument(
        "--holdout",type=Path,
        default=ROOT/"examples/source_bound_holdout/unfamiliar_tabletop_label_feeder_20261020.json",
    )
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    scenarios=[load_source_agnostic_scenario(p) for p in sorted(args.cases.glob("*.json"))]
    baseline=evaluate_source_agnostic_suite(scenarios)
    results=[]
    for case in scenarios:
        candidate=build_source_bound_candidate(case)
        # Independent audit reruns canonical plan only when needed: recorded
        # source trace is reconstructed from a second plan with no shared
        # authority from the candidate's own success fields.
        from hardware_splicer.engineering_planner import plan_engineering_project
        fresh=plan_engineering_project(
            case["intake"],engineering_sources=case.get("engineering_sources"),
            declared_conflicts=case.get("declared_conflicts"),skip_vision=True,
        )
        audit=independently_audit_source_bound_candidate(case,fresh,candidate)
        results.append({"scenario_id":case["scenario_id"],"candidate":candidate,"independent_audit":audit})
        if not audit["passes_independent_evidence_integrity"]:
            raise RuntimeError(f"source integrity failed for {case['scenario_id']}: {audit['failures']}")
    holdout_scenario=load_source_agnostic_scenario(args.holdout)
    holdout_plan=plan_engineering_project(
        holdout_scenario["intake"],
        engineering_sources=holdout_scenario.get("engineering_sources"),
        declared_conflicts=holdout_scenario.get("declared_conflicts"),skip_vision=True,
    )
    holdout_candidate=build_source_bound_candidate(holdout_scenario,plan=holdout_plan)
    holdout_audit=independently_audit_source_bound_candidate(
        holdout_scenario,holdout_plan,holdout_candidate,
    )
    if not holdout_audit["passes_independent_evidence_integrity"]:
        raise RuntimeError("independent holdout had corrupted source or claim provenance")
    if holdout_audit["conditional_candidate_accepted"]:
        raise RuntimeError("false positive: mobile topology accepted for a stationary holdout")
    result={
        "schema_version":"hardware_splicer.source_bound_design_suite.v1",
        "unseen_public_source_holdout":{
            "scenario_id":holdout_scenario["scenario_id"],
            "candidate":holdout_candidate,
            "independent_audit":holdout_audit,
        },
        "baseline_source_agnostic":baseline,
        "conditional_design_count":len(results),
        "integrity_audited_design_count":sum(r["independent_audit"]["passes_independent_evidence_integrity"] for r in results),
        "physically_verified_design_count":0,
        "validated_repair_count":0,
        "fabrication_authorized_count":0,
        "cases":results,
        "note":"Canonical source graph and topology produce conditional decisions. Earlier fixture claims are input data and have NOT been independently instrument-authenticated.",
    }
    target=args.out/"SOURCE_BOUND_DESIGN_TRIAL.json"
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps({
      "baseline_bounded_design_count":baseline["bounded_engineering_candidate_count"],
      "conditional_design_count":result["conditional_design_count"],
      "independently_integrity_audited_count":result["integrity_audited_design_count"],
      "physically_verified_design_count":0,
      "holdout_source_binding_integrity":holdout_audit["passes_independent_evidence_integrity"],
      "holdout_architecture_relevance":holdout_audit["passes_independent_architecture_relevance"],
      "holdout_rejected_invalid_rover_topology":holdout_audit["explicit_topology_rejection_was_honestly_recorded"],
      "output":str(target),
      "case_results":[{
        "scenario":r["scenario_id"],
        "decisions":len(r["candidate"]["decisions"]),
        "sources":len(r["candidate"]["source_integrity"]),
        "conflicts":r["candidate"]["unresolved_blocking_source_conflicts"],
        "evidence_integrity":r["independent_audit"]["passes_independent_evidence_integrity"],
        "hardware_release":r["candidate"]["physical_fabrication_or_power_authorized"],
      } for r in results],
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
