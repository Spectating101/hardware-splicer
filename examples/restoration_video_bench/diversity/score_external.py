"""Post-review scorer for the SEALED GPT-6 text-control baseline.

Never invoked in the pre-outcome CI. The reviewer-supplied case outcomes must
be an external file created after the prediction commit/digest; the algorithm
cannot independently adjudicate repair evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PRED=HERE / "evidence/gpt6_text_control_preoutcome.json"
CASES=HERE / "cases.json"

def score(control_path:Path, outcome_path:Path, expected_sha256:str)->dict:
    raw=control_path.read_bytes()
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=expected_sha256:
        raise ValueError("control file does not match frozen prediction SHA-256")
    control=json.loads(raw)
    cases=json.loads(CASES.read_text())
    inputs={c["id"]:c for c in cases["cases"]}
    predictions={p["case_id"]:p for p in control["predictions"]}
    if set(inputs)!=set(predictions):raise ValueError("prediction coverage changed")
    outcomes=json.loads(outcome_path.read_text())
    if outcomes.get("schema")!="hs.restoration.external_outcome_review.v1":
        raise ValueError("wrong post-review schema")
    labels=outcomes.get("outcomes",[])
    if set(r.get("case_id") for r in labels)!=set(inputs):
        raise ValueError("external outcome review must address every case, including unknowns")
    results=[]
    for row in labels:
        case=inputs[row["case_id"]]
        p=predictions[row["case_id"]]
        if row.get("video_url")!=case["source_url"]:
            raise ValueError("outcome/video source mismatch")
        if not row.get("reviewer") or not row.get("review_provenance"):
            raise ValueError("reviewer and timestamped evidence required")
        status=row.get("status")
        if status not in ("resolved","partially_resolved","unresolved","inconclusive"):
            raise ValueError("unknown outcome adjudication status")
        accepted=set(row.get("supported_hypotheses",[]))
        valid={h["mechanism"] for h in p["hypotheses"]}
        if not accepted<=valid:
            raise ValueError("outcome labels cannot invent predicted mechanisms")
        if status!="resolved" and accepted:
            raise ValueError("don't score ambiguous/unresolved repairs as correct")
        order=[h["mechanism"] for h in p["hypotheses"]]
        top1=(order[0] in accepted) if status=="resolved" else None
        top3=(bool(accepted)) if status=="resolved" else None
        results.append({
            "case_id":row["case_id"],
            "adjudication_status":status,
            "prediction_top1":order[0],
            "supported_predictions":sorted(accepted),
            "top1_hit":top1,
            "top3_hit":top3,
            "review_provenance":row["review_provenance"],
            "outcome_claim":row.get("creator_reported_result",""),
            "uncertainty":row.get("uncertainty",""),
        })
    determinate=[r for r in results if r["adjudication_status"]=="resolved"]
    return {
        "schema":"hs.restoration.external_control_review_score.v1",
        "sha256_frozen_prediction":actual,
        "review_quality":outcomes.get("quality_note","human adjudication, creator narration not independent electrical proof"),
        "case_count":len(results),
        "resolved_denominator":len(determinate),
        "top1_count":sum(r["top1_hit"] is True for r in determinate),
        "top3_count":sum(r["top3_hit"] is True for r in determinate),
        "unscorable_count":len(results)-len(determinate),
        "not_HS_runtime_or_video_vision":True,
        "not_physical_validation":True,
        "results":results
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--outcomes",type=Path,required=True)
    p.add_argument("--control",type=Path,default=PRED)
    p.add_argument("--expected-sha256",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    x=score(a.control,a.outcomes,a.expected_sha256)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(x,indent=2)+"\n")
    print(json.dumps({
        "resolved":x["resolved_denominator"],
        "top1":x["top1_count"],
        "top3":x["top3_count"],
        "unscorable":x["unscorable_count"]
    },indent=2))

if __name__=="__main__":main()
