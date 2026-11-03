#!/usr/bin/env python3
"""Independent verifier for frozen 17-case external evidence holdout.

No imports from benchmark or Circuit-AI scorer. Recomputes inputs and
denominators; never treats public owner comments as verified bench evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

BLOB="c4473c96309cd95d043e12dcaf4c9f308e66960d"
ENGINE="c296b7fb06df581b929f2bfff08664c3ca420aef"
EXCLUDED_URLS = {
    "https://www.ifixit.com/Answers/View/937739/Why+will+my+Game+Boy+not+turn+on?",
    "https://www.ifixit.com/Answers/View/769879/MacBook+not+turning+on?",
    "https://www.ifixit.com/Answers/View/517971/Phone+not+charging+after+charging+port+replacement?",
    "https://www.ifixit.com/Answers/View/701499/iPhone+won't+turn+on+with+charging+port+connected",
    "https://www.ifixit.com/Answers/View/731169/Not+turning+on+or+charging",
    "https://www.ifixit.com/Answers/View/503051/Fixing+the+Nintendo+Switch+Dock+(no+signal-LED+blinking)",
    "https://www.ifixit.com/Answers/View/282696/Printer+cartridges+stuck,+wont+move+back+to+print+location",
    "https://www.ifixit.com/Answers/View/676743/Cannot+get+sound+from+the+main+speaker",
    "https://www.ifixit.com/Answers/View/273962/How+do+I+fix+my+Drone+that+won't+lift+off",
}

def need(condition, reason):
    if not condition:
        raise ValueError("Independent post-#269 repair holdout validation: "+reason)

def blob_sha(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def canonical(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()

def validate(corpus_path:Path,report_path:Path):
    b=corpus_path.read_bytes()
    need(blob_sha(b)==BLOB,"original frozen source case blob was modified")
    corpus=json.loads(b)
    report=json.loads(report_path.read_text())
    need(corpus["schema_version"]=="hardware_splicer.measurement_grade_public_repair_holdout.v1", "wrong source schema")
    need(report["schema_version"]=="hardware_splicer.measurement_grade_public_repair_eval.v1", "wrong report schema")
    need(corpus["case_count"]==report["source_owner_cases"]==17 and
         corpus["checkpoint_count"]==report["source_only_checkpoint_count"]==34,
         "changed source population")
    need(corpus["model_target_commit"]==report["original_engine_pinned_commit"]==ENGINE,
         "engine revision changed after freeze")
    need(report["original_frozen_blob_sha1"]==BLOB and
         report["corpus_sha256"]==hashlib.sha256(b).hexdigest(),
         "wrong source corpus hash")
    cases=corpus["cases"]
    ids=[c["id"] for c in cases]
    urls=[c["source"]["url"] for c in cases]
    need(len(cases)==len(set(ids))==len(set(urls))==17,"duplicate story, author or source ID")
    need(not set(urls)&EXCLUDED_URLS,"source reused from original four/seven known development studies")
    need(sum(c["predeclared_eval"]["measurement_claimed"] for c in cases)==9,
         "original number of claimed owner measurements rewritten")
    need(sum(c["predeclared_eval"]["out_of_market_catalog"] for c in cases)==5,
         "original OOD denominator altered")
    need(sum(not c["outcome_oracle"]["owner_claimed_full_fix"] for c in cases)==10,
         "future source outcomes altered")
    need(all(c["source"]["url"].startswith("https://") for c in cases),
         "unlinked source case")
    preds=report["raw_blinded_engine_responses"]
    rows=report["after_predictions_source_outcome_adjudication"]
    need(len(preds)==34 and len(rows)==17, "dropped predictions or source outcomes")
    need(len({p["checkpoint_id"] for p in preds})==34, "duplicated checkpoint identities")
    indexed={p["checkpoint_id"]:p for p in preds}
    truth_index={r["case_id"]:r for r in rows}
    all_scores=[]
    for case in cases:
        source=case["source"]
        truth=case["outcome_oracle"]
        spec=case["predeclared_eval"]
        need(len(case["checkpoints"])==2 and len(case["events"])==2,
             "source pre-outcome checkpoint order missing")
        need(spec["measurement_claimed"]==bool(spec["reported_readings"]),
             "invented source measurement status")
        for cp in case["checkpoints"]:
            need(cp["event_index"] in (0,1),"future source state submitted")
            ident=case["id"]+"__"+cp["id"]
            row=indexed.get(ident)
            need(row is not None,"checkpoint omitted "+ident)
            pre={
                "case_id":ident,
                "title":case["device"]+" public repair history",
                "device_hint":cp["device_hint"],
                "symptoms":cp["symptoms"],
                "notes":cp["notes"],
                "source_url":source["url"],
                "source_kind":"public_owner_observations_with_future_outcomes_masked",
                "observed_actions":[],
                "expected_lane":"",
            }
            need(cp["symptoms"]==case["events"][0]["observations"] if cp["event_index"]==0
                 else cp["symptoms"]==(case["events"][0]["observations"]+
                                       case["events"][1]["observations"]),
                 "frozen input chronology was changed")
            need(row["blinded_input"]==pre and
                 row["input_sha256"]==hashlib.sha256(canonical(pre)).hexdigest(),
                 "owner outcome or oracle may be leaked into model input")
            need(row["oracle_was_not_passed_to_engine"] is True and
                 row["engine_is_unmodified_pinned_revision"] is True and
                 row["physical_repairs_by_HS"]==0,"false model independence/physical authority")
            engine=row["engine_output"]
            need(engine["case_id"]==ident and
                 engine["source_url"]==source["url"] and
                 engine["verdict"] in ("solvable_now","assistive_only","not_ready") and
                 engine["verdict_scope"]=="software_workflow_only_not_repaired_product" and
                 engine["physical_repair_ready"] is False,
                 "software workflow promoted into physical repair authority")
            need(engine["repair_guide"]["family"] is not None,
                 "engine did not actually return a family")
            need(engine["coverage"]["top_item"] is not None or
                 engine["coverage"]["matched"] is False,
                 "unsupported item silently given matched classification")
        adjud=truth_index.get(case["id"])
        need(adjud and adjud["source_url"]==source["url"] and
             adjud["source_owner_reported_status"]==truth["reported_status"] and
             adjud["source_owner_claimed_full_fix"] is truth["owner_claimed_full_fix"] and
             adjud["source_limitations"]==truth["limitations"] and
             adjud["owner_reported_readings"]==spec["reported_readings"],
             "oracle or outcome rewritten after engine execution")
        need(adjud["measurements_independently_verified"] is False and
             adjud["root_cause_independently_verified"] is False and
             adjud["HS_physical_repair"] is False,"false lab validation")
        for score,cp in zip(adjud["checkpoints"],case["checkpoints"]):
            original=indexed[case["id"]+"__"+cp["id"]]["engine_output"]
            need(score["checkpoint_id"]==original["case_id"] and
                 score["actual_item"]==original["coverage"]["top_item"] and
                 score["actual_family"]==original["repair_guide"]["family"] and
                 score["leading_fault"]==original["repair_guide"]["top_fault"] and
                 score["software_workflow_score"]==original["workflow_score"] and
                 score["software_workflow_verdict"]==original["verdict"],
                 "raw prediction changed in scorecard")
            expected_item=spec["expected_item"]
            expected_family=spec["expected_family"]
            need(score["expected_item"]==expected_item and
                 score["expected_family"]==expected_family and
                 score["item_exact_match"]==(score["actual_item"]==expected_item if expected_item is not None else None) and
                 score["family_exact_match"]==(score["actual_family"]==expected_family if expected_family is not None else None) and
                 score["ood_product_abstained"]==(score["actual_item"] is None if expected_item is None else None),
                 "original scored product/family/abstention oracle manipulated")
            need(score["root_cause_exact_match"] is None and
                 score["source_root_cause_proven"] is False and
                 score["physical_repair_ready"] is False,
                 "source anecdote converted to diagnosed component or physical repair")
            all_scores.append(score)
    item=[p for p in all_scores if p["item_exact_match"] is not None]
    family=[p for p in all_scores if p["family_exact_match"] is not None]
    ood=[p for p in all_scores if p["ood_product_abstained"] is not None]
    need(report["known_item_scored"]==len(item) and
         report["known_item_matches"]==sum(p["item_exact_match"] for p in item),
         "category score numerator or denominator inflated")
    need(report["known_family_scored"]==len(family) and
         report["known_family_matches"]==sum(p["family_exact_match"] for p in family),
         "family score inflated")
    need(report["out_of_catalog_checkpoint_count"]==len(ood) and
         report["out_of_catalog_abstentions"]==sum(p["ood_product_abstained"] for p in ood),
         "OOD abstention inflated")
    need(report["reported_numeric_measurement_cases"]==9 and
         report["owner_without_complete_confirmed_fix_cases"]==10,
         "source integrity count incorrect")
    need(report["software_solvable_now_for_unresolved_source_checkpoints"]==
         sum(p["software_workflow_verdict"]=="solvable_now"
             for c in rows if not c["source_owner_claimed_full_fix"]
             for p in c["checkpoints"]),"unresolved risky software verdict hidden")
    need(report["physical_repair_claims"]==report["independently_validated_component_root_causes"]==0 and
         report["any_autonomous_power_or_flight_authorized"] is False and
         report["only_owner_reports_and_sourced_advice_not_lab_truth"] is True,
         "fake completed physical work or component diagnosis")
    return {"independent_verification":"PASS",
            "cases":17,"prior_only_checkpoints":34,
            "known_market_matches":[report["known_item_matches"],len(item)],
            "known_family_matches":[report["known_family_matches"],len(family)],
            "OOD_abstained":[report["out_of_catalog_abstentions"],len(ood)],
            "source_claimed_numeric_cases":9,"owner_not_full_fix_cases":10,
            "owner_values_verified_by_lab":0,
            "genuine_HS_physical_repairs":0,"autonomous_flight_and_power_authorized":False}

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--corpus",type=Path,required=True)
    a.add_argument("--report",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    args=a.parse_args()
    result=validate(args.corpus,args.report)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
