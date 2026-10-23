"""Source-backed HS repair corpus v2: frozen engine versus naive triage baseline.

Reference outcomes are NEVER loaded before all predictions are generated.
This is NOT a blind model eval in research sense: dataset author saw references
when encoding paths. Baseline is explicitly a simple heuristic, NOT Flux/LLM.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from hardware_splicer.repair_intake import apply_repair_intake_context


def naive_frequency_baseline(case: dict) -> dict:
    """Non-AI comparison: most common ID on failed paths, tie alphabetical."""
    evidence = case["repair_intake"]["path_evidence"]
    fails = Counter(
        component for test in evidence["path_tests"] if test["outcome"] == "fail"
        for component in set(test["path"])
    )
    if not fails:
        return {"top_candidate": None, "method": "most_frequent_failed_path"}
    maximum = max(fails.values())
    best = sorted(cid for cid, count in fails.items() if count == maximum)
    return {"top_candidate": best[0], "method": "most_frequent_failed_path"}


def assess_input_discrimination(case: dict) -> dict:
    tests = case["repair_intake"]["path_evidence"]["path_tests"]
    signatures = {(t["outcome"], tuple(sorted(set(t["path"])))) for t in tests}
    failed = {tuple(sorted(set(t["path"]))) for t in tests if t["outcome"] == "fail"}
    passed = {tuple(sorted(set(t["path"]))) for t in tests if t["outcome"] == "pass"}
    distinct_memberships = {x[1] for x in signatures}
    admissible = bool(failed) and len(distinct_memberships) >= 2
    return {
        "distinct_route_count": len(distinct_memberships),
        "observed_test_count": len(tests),
        "enough_distinct_topology": admissible,
        "same_route_both_passed_and_failed": bool(failed & passed),
        "interpretation": (
            "Functional path observations support distinguishing routes; "
            "not independent electrical measurements or physical diagnosis"
            if admissible else
            "Insufficient route distinction: do not score top-ranked part as a validated diagnosis"
        ),
    }


def run(root: Path) -> dict:
    raw = (root / "blind_observations.json").read_bytes()
    cases = json.loads(raw)["cases"]
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ID")
    # Seal: open outcomes ONLY after both competitors finish ALL cases.
    hs_outputs = {}
    baseline_outputs = {}
    input_quality = {}
    for case in cases:
        cid = case["case_id"]
        hs_outputs[cid] = apply_repair_intake_context(case).get("repair_path_diagnostic")
        if not hs_outputs[cid]:
            raise AssertionError(f"{cid}: missing HS repair diagnostics")
        baseline_outputs[cid] = naive_frequency_baseline(case)
        input_quality[cid] = assess_input_discrimination(case)
    outcomes = json.loads((root / "sealed_outcomes.json").read_text(encoding="utf-8"))["labels"]
    gold_by_id = {x["case_id"]: x for x in outcomes}
    if set(gold_by_id) != set(ids):
        raise ValueError("outcome coverage and input ids mismatch")
    per_case = {}
    for cid in ids:
        gold = gold_by_id[cid]
        hs = hs_outputs[cid]
        hs_top = (hs.get("candidates") or [{}])[0].get("component_id")
        base_top = baseline_outputs[cid]["top_candidate"]
        eligible = input_quality[cid]["enough_distinct_topology"]
        owner = gold["score_as_original_owner_confirmed"]
        label = gold["reported_resolution_component"]
        per_case[cid] = {
            "outcome_grade": gold["outcome_grade"],
            "score_as_original_owner_confirmed": owner,
            "admissible_route_evidence": eligible,
            "hs_verdict": hs["verdict"],
            "hs_first": hs_top,
            "naive_baseline_first": base_top,
            "hs_top1_owner_confirmed_match": (bool(eligible and owner and hs_top == label)),
            "naive_top1_owner_confirmed_match": (bool(eligible and owner and base_top == label)),
            "hs_rank_tie_count": hs.get("highest_evidence_score_tie_count"),
            "quality": input_quality[cid],
            "source_url": gold["source_url"],
        }
    confirmed = [v for v in per_case.values() if v["score_as_original_owner_confirmed"]]
    eligible_confirmed = [v for v in confirmed if v["admissible_route_evidence"]]
    unresolved = [v for v in per_case.values() if not v["score_as_original_owner_confirmed"]]
    counts = {
        "all_cases": len(per_case),
        "owner_confirmed_reference_cases": len(confirmed),
        "owner_confirmed_with_at_least_two_distinct_routes": len(eligible_confirmed),
        "owner_confirmed_inadmissible_route_cases": len(confirmed)-len(eligible_confirmed),
        "hs_confirmed_top1_matches_admissible": sum(v["hs_top1_owner_confirmed_match"] for v in eligible_confirmed),
        "naive_confirmed_top1_matches_admissible": sum(v["naive_top1_owner_confirmed_match"] for v in eligible_confirmed),
        "hs_total_owner_confirmed_matches_counting_missing_evidence_as_fail": sum(v["hs_top1_owner_confirmed_match"] for v in confirmed),
        "naive_total_owner_confirmed_matches_counting_missing_evidence_as_fail": sum(v["naive_top1_owner_confirmed_match"] for v in confirmed),
        "no_confirmed_outcome_cases": len(unresolved),
        "hs_abstentions": sum(v["hs_verdict"]=="insufficient_discriminating_evidence" for v in per_case.values()),
        "non_discriminating_inputs": sum(not v["admissible_route_evidence"] for v in per_case.values()),
    }
    return {
        "schema_version": "hardware_splicer.repair_corpus_evaluation.v2",
        "frozen_engine_commit": "be06210bf06db8bc6a2068cfda71b52c47749565",
        "frozen_engine_file": "src/hardware_splicer/repair_path_diagnostics.py",
        "blind_observations_sha256": hashlib.sha256(raw).hexdigest(),
        "observations_read_before_gold": True,
        "benchmark_author_was_aware_of_public_outcomes": True,
        "is_prospective_or_fully_held_out": False,
        "comparison": "naive top-frequency failed-route baseline, NOT a commercial AI competitor",
        "totals": counts,
        "cases": per_case,
        "physical_repairs_performed": 0,
        "competitor_llm_queries_executed": 0,
        "notes": [
            "Top-1 accuracy is only reported for owner-confirmed outcomes and distinct functional paths.",
            "Missing evidence counts as no demonstrated correct diagnosis in overall denominator.",
            "No claim about genuinely unseen real cases or superiority to a real-world repair service.",
        ],
    }


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    report = run(base)
    destination = Path(sys.argv[1]) if len(sys.argv)>1 else base/"evaluation_report.json"
    destination.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"report":str(destination),"totals":report["totals"],"comparison":report["comparison"]},indent=2))
