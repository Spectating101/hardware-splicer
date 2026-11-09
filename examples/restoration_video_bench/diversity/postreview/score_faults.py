"""Strict, post-freeze multi-fault score of creator-narrative repair outcomes.

This is a reviewer-adjudicated evaluation: NOT independent instrument data.
It explicitly distinguishes exact fault-family identification from a broad
component-category guess. The original frozen predictions are read-only.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PRED=HERE.parent/"evidence/gpt6_text_control_preoutcome.json"
REVIEW=HERE/"creator_narrative_outcomes.json"
OUTPUT=HERE/"score.json"
ALLOWED={"exact_family","partial_domain","miss"}

def assess(prediction_file:Path=PRED, review_file:Path=REVIEW)->dict:
    raw=prediction_file.read_bytes()
    pred=json.loads(raw)
    review=json.loads(review_file.read_text())
    if review.get("schema")!="hs.restoration.creator_narrative_postreview.v1":
        raise ValueError("invalid postreview schema")
    digest=hashlib.sha256(raw).hexdigest()
    if review["frozen_prediction_sha256"]!=digest:
        raise ValueError("prediction file changed after sealed commit")
    if pred.get("no_creator_outcomes_opened_for_scoring") is not True:
        raise ValueError("not a sealed pre-outcome control")
    c={p["case_id"]:p for p in pred["predictions"]}
    outcomes=review.get("outcomes",[])
    if len(outcomes)!=len(c) or {v["case_id"] for v in outcomes}!=set(c):
        raise ValueError("reviews must include every case exactly once")
    results=[]
    for row in outcomes:
        p=c[row["case_id"]]
        if not row.get("review_provenance") or not row.get("reviewer"):
            raise ValueError("source+reviewer required")
        if row["status"] not in {"resolved","partially_resolved","inconclusive"}:
            raise ValueError("unrecognized adjudication")
        if row["status"]=="resolved" and not row["faults"]:
            raise ValueError("resolved case requires traceable root fault")
        if row["status"]!="resolved" and row["faults"]:
            raise ValueError("ambiguous/partial cases must remain unscored")
        hypotheses={h["mechanism"]:h["rank"] for h in p["hypotheses"]}
        fault_rows=[]
        for fault in row["faults"]:
            q=fault["match_quality"]
            h=fault["matched_hypothesis"]
            if q not in ALLOWED:
                raise ValueError("match specificity must be explicit")
            if (q=="miss") != (h is None):
                raise ValueError("unmatched root must have no proposed hypothesis")
            if h is not None and h not in hypotheses:
                raise ValueError("cannot credit a mechanism absent from sealed prediction")
            if not fault.get("timestamp") or not fault.get("rationale"):
                raise ValueError("timestamped proof and adjudication required")
            fault_rows.append({
                "reported_fault":fault["fault"],
                "source_window":fault["timestamp"],
                "match_quality":q,
                "matched_prediction_rank":hypotheses[h] if h else None,
                "judgement":fault["rationale"],
            })
        results.append({
            "case_id":row["case_id"],
            "status":row["status"],
            "creator_reported_result":row["creator_reported_result"],
            "review_provenance":row["review_provenance"],
            "faults":fault_rows,
        })
    resolved=[r for r in results if r["status"]=="resolved"]
    faults=[f for r in resolved for f in r["faults"]]
    count=lambda quality:sum(f["match_quality"]==quality for f in faults)
    exact=count("exact_family")
    partial=count("partial_domain")
    miss=count("miss")
    return {
        "schema":"hs.restoration.postfreeze_multifault_score.v1",
        "frozen_prediction_commit":review["frozen_prediction_commit"],
        "frozen_prediction_sha256":digest,
        "n_cases":len(results),
        "n_resolved_cases":len(resolved),
        "n_unscored_cases":len(results)-len(resolved),
        "n_creator_reported_faults_scored":len(faults),
        "exact_fault_family":exact,
        "broad_domain_only":partial,
        "missed_faults":miss,
        "exact_fault_family_top1":sum(
            f["match_quality"]=="exact_family" and f["matched_prediction_rank"]==1
            for f in faults
        ),
        "cases_all_reported_faults_exact":sum(
            all(f["match_quality"]=="exact_family" for f in r["faults"])
            for r in resolved
        ),
        "quality_note":review["quality_note"],
        "NOT_native_HS_diagnostic_result":True,
        "NOT_independent_ground_truth":True,
        "NOT_video_frame_evaluation":True,
        "NOT_a_proof_of_generalization":True,
        "case_results":results,
    }

if __name__=="__main__":
    scored=assess()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(scored,indent=2)+"\n")
    print(json.dumps({k:scored[k] for k in (
        "n_cases","n_resolved_cases","n_unscored_cases",
        "n_creator_reported_faults_scored","exact_fault_family",
        "broad_domain_only","missed_faults","exact_fault_family_top1",
        "cases_all_reported_faults_exact")},indent=2))
