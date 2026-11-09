"""Audit sealed Gemini vs HS source-graph A/B after external creator review.

A human-style adjudicator explicitly labels per-fault mechanism matches.
The scorer verifies all references and recomputes counts; it DOES NOT
invent a correctness label from matching model text to creator prose.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

VALID={"exact_family","partial_domain","miss"}
ARMS=("plain","hs_graph")

def sha_file(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def score(pred:Path, review:Path, creator:Path)->dict:
    a=json.loads(review.read_text())
    if a.get("schema")!="hs.restoration.graph_ab_human_postreview.v1":
        raise ValueError("wrong grading protocol")
    if sha_file(pred)!=a["frozen_prediction_sha256"]:
        raise ValueError("predictions changed after human outcome review")
    if sha_file(creator)!=a["creator_outcomes_sha256"]:
        raise ValueError("external creator outcome source changed")
    p=json.loads(pred.read_text())
    c=json.loads(creator.read_text())
    if not p["complete"] or c["schema"]!="hs.restoration.creator_narrative_postreview.v1":
        raise ValueError("incomplete trial or unknown outcome source")
    if set(x["case_id"] for x in a["cases"])!=set(x["case_id"] for x in p["cases"]):
        raise ValueError("review did not cover all and only the A/B cases")
    p_by={r["case_id"]:r for r in p["cases"]}
    c_by={r["case_id"]:r for r in c["outcomes"]}
    counts={arm:Counter() for arm in ARMS}
    first_exact={arm:0 for arm in ARMS}
    device_complete={arm:0 for arm in ARMS}
    flags={arm:0 for arm in ARMS}
    details=[]
    for r in a["cases"]:
        case_id=r["case_id"]
        actual=c_by[case_id]
        if actual["status"]!="resolved":
            raise ValueError("cannot count uncertain or unresolved creator outcomes")
        outcome_faults=[f["fault"] for f in actual["faults"]]
        if [f["fault"] for f in r["faults"]]!=outcome_faults:
            raise ValueError("review fault labels differ from source review")
        row={"case_id":case_id,"faults":[],"faults_count":len(outcome_faults)}
        for f in r["faults"]:
            graded={"fault":f["fault"]}
            for arm in ARMS:
                v=f[arm]
                grade=v.get("grade")
                if grade not in VALID:
                    raise ValueError("unknown score grade")
                rank=v.get("hypothesis_rank")
                model_plan=p_by[case_id]["arms"][arm]["receipt"]["plan"]
                if grade=="miss":
                    if rank is not None:
                        raise ValueError("miss cannot cite an allegedly matched hypothesis")
                elif not isinstance(rank,int) or not 1<=rank<=len(model_plan["hypotheses"]):
                    raise ValueError("supported mechanism rank outside real model output")
                if not v.get("rationale"):
                    raise ValueError("human judgment rationale missing")
                counts[arm][grade]+=1
                graded[arm]={"grade":grade,"rank":rank,"rationale":v["rationale"]}
            row["faults"].append(graded)
        for arm in ARMS:
            if any(f[arm]["grade"]=="exact_family" and f[arm]["hypothesis_rank"]==1 for f in r["faults"]):
                first_exact[arm]+=1
            if all(f[arm]["grade"]=="exact_family" for f in r["faults"]):
                device_complete[arm]+=1
        if r.get("hs_added_unverified_threshold"):
            flags["hs_graph"]+=1
        row["test_notes"]=r["test_notes"]
        row["hs_added_unverified_threshold"]=r.get("hs_added_unverified_threshold",False)
        details.append(row)
    return {
        "schema":"hs.restoration.graph_ab_postreview_score.v1",
        "source_human_review":a["reviewer"],
        "source_creator_caveat":a["creator_outcome_caveat"],
        "frozen_prediction_sha256":a["frozen_prediction_sha256"],
        "creator_review_sha256":a["creator_outcomes_sha256"],
        "case_count":len(details),
        "reviewed_distinct_faults":sum(x["faults_count"] for x in details),
        "grade_counts":{arm:{g:counts[arm][g] for g in ("exact_family","partial_domain","miss")} for arm in ARMS},
        "cases_with_top_ranked_exact_family":first_exact,
        "cases_with_all_distinct_faults_exact_family":device_complete,
        "HS_cases_with_unsourced_numeric_thresholds":flags["hs_graph"],
        "runtime_results": {
            arm:{
                "valid":sum(
                    p_by[c]["arms"][arm]["receipt"]["status"]=="proposed_unverified_differential"
                    for c in p_by
                ),
                "seconds":round(sum(p_by[c]["arms"][arm]["receipt"]["elapsed_seconds"] for c in p_by),2),
            } for arm in ARMS
        },
        "no_independent_blinded_reviewer":True,
        "not_a_reliability_or_statistical_significance_claim":True,
        "analysis_not_accessible_to_initial_model_prompts":True,
        "details":details
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--predictions",type=Path,required=True)
    p.add_argument("--review",type=Path,required=True)
    p.add_argument("--creator-outcomes",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=score(a.predictions,a.review,a.creator_outcomes)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:result[k] for k in (
        "case_count","reviewed_distinct_faults","grade_counts",
        "cases_with_top_ranked_exact_family","cases_with_all_distinct_faults_exact_family",
        "HS_cases_with_unsourced_numeric_thresholds","runtime_results"
    )},indent=2))
if __name__=="__main__":
    main()
