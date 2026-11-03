#!/usr/bin/env python3
"""Evaluate genuinely unseen, predeclared public restoration cases without retraining.

Unlike the earlier four in-sample cases this holdout includes printer and
drone cases and source-reported no-fix / partial-fix outcomes. Submit only
prior observations to the *existing* Circuit-AI RepairCaseEvaluator;
report unknown/unsupported domain honestly. No model changes based on these
cases in this experiment. The original public outcomes are not verified
physical evidence or hardware work done by HS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA="hardware_splicer.public_restoration_unseen_holdout.v1"
REPORT="hardware_splicer.public_restoration_untouched_holdout_evaluation.v1"
FROZEN_GIT_BLOB="b2441fb0fbdeb594e33a4f8f01deda25b3b3096a"

def need(ok,why):
    if not ok:raise ValueError("HS untouched outside-case validation: "+why)

def file_sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_blob_sha(path:Path)->str:
    blob=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(blob)).encode()+b"\0"+blob).hexdigest()

def evaluate(root:Path,cases:Path,out:Path)->dict:
    need(git_blob_sha(cases)==FROZEN_GIT_BLOB,
         "frozen holdout altered after case pre-registration; cannot tune test to known results")
    src=json.loads(cases.read_text())
    need(src["schema_version"]==SCHEMA and src["case_count"]==7 and
         src["checkpoint_count"]==14 and
         src["actual_hardware_physically_tested_by_HS"]==0,
         "public source case selection/authority changed")
    need(len(src["cases"])==src["case_count"],"frozen public case count mismatch")
    out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str((root/"apps/circuit-ai").resolve()))
    from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
    from src.intelligence.board_session_store import BoardSessionStore
    engine=RepairCaseEvaluator(
        session_store=BoardSessionStore(out/"ephemeral_original_engine_case_store.json")
    )

    raw=[]
    truth=[]
    for case in src["cases"]:
        need(len(case["checkpoints"])==2 and case["source"]["url"].startswith("https://"),
             "unmatched source chronology")
        predictions=[]
        for cp in case["checkpoints"]:
            # Absolutely NO source future, expected device classification,
            # outcome, oracle, guide or completed repair goes to the engine.
            inp={
                "case_id":case["id"]+"__"+cp["id"],
                "title":case["title"],
                "device_hint":cp["device_hint"],
                "symptoms":cp["symptoms"],
                "notes":cp["notes"],
                "source_url":case["source"]["url"],
                "source_kind":"earlier_public_case_observations_not_final_repair",
                "observed_actions":[],
                "expected_lane":"",
            }
            assert all(x not in inp for x in (
                "oracle","chronology","predeclared_eval",
                "source_intervention","owner_reported_complete_fix"))
            before=engine.evaluate_case(inp,commit_session=False)
            guide=engine.encyclopedia.generate(
                analysis={},symptoms=inp["symptoms"],device_hint=inp["device_hint"]
            )
            text=json.dumps({
                "fault_candidates":guide.get("fault_candidates",[])[:5],
                "diagnostic_flow":guide.get("diagnostic_flow",[]),
                "evidence_to_collect_next":guide.get("evidence_to_collect_next",[]),
                "board_first_tasks":before["board_session"]["first_tasks"],
            },ensure_ascii=False,default=str).lower()
            need(before["case_id"]==inp["case_id"],"original evaluator result not tied to source")
            predictions.append({
                "checkpoint_id":inp["case_id"],
                "blinded_input":inp,
                "blinded_input_sha256":hashlib.sha256(json.dumps(
                    inp,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                "source_event_steps_known":cp["time_available"],
                "original_CircuitAI_evaluator_returned":before,
                "generated_diagnostics": {
                    "fault_candidates":guide.get("fault_candidates",[])[:5],
                    "diagnostic_flow":guide.get("diagnostic_flow",[]),
                    "evidence_to_collect_next":guide.get("evidence_to_collect_next",[]),
                },
                "current_model_not_modified_to_fit_holdout":True,
                "repair_and_future_truth_not_passed_to_engine":True,
                "physical_product_repaired_by_HS":False,
                "bench_power_or_flight_authorized":False,
            })
        raw.extend(predictions)
        # Only after the two calls: reveal source-owned outcome and prior
        # registration. The declared categories apply strictly as a proxy,
        # never a proof of electrical root-cause correctness.
        expected=case["predeclared_eval"]
        case_score=[]
        for row in predictions:
            before=row["original_CircuitAI_evaluator_returned"]
            text=json.dumps(row["generated_diagnostics"],ensure_ascii=False,default=str).lower()
            signals=[tok for tok in expected["diagnostic_terms_any"] if tok.lower() in text]
            score={
                "checkpoint_id":row["checkpoint_id"],
                "predeclared_device_domain":expected["device_domain"],
                "predeclared_expected_market_item":expected["expected_item"],
                "engine_market_item":before["coverage"]["top_item"],
                "market_item_exact_match":(
                    before["coverage"]["top_item"]==expected["expected_item"]
                    if expected["expected_item"] is not None else None),
                "predeclared_expected_family":expected["expected_family"],
                "engine_family":before["repair_guide"]["family"],
                "engine_leading_fault_hypothesis":before["repair_guide"]["top_fault"],
                "family_exact_match":(
                    before["repair_guide"]["family"]==expected["expected_family"]
                    if expected["expected_family"] is not None else None),
                "diagnostic_terms_predeclared":expected["diagnostic_terms_any"],
                "diagnostic_terms_present_in_actual_engine":signals,
                "weak_keyword_relevance_proxy_any":bool(signals),
                "software_workflow_verdict":before["verdict"],
                "software_workflow_score":before["workflow_score"],
                "software_verdict_is_not_physical_certification":True,
                "actual_root_cause_diagnosis_measured_correctly":None,
                "retrospective_outcome_not_given_to_engine":True,
            }
            case_score.append(score)
        truth.append({
            "id":case["id"],
            "source_url":case["source"]["url"],
            "source_kind":case["source"]["kind"],
            "source_reliability":case["source"]["source_reliability"],
            "owner_reported_full_fix":case["oracle"]["owner_reported_complete_fix"],
            "reported_product_status":case["oracle"]["status"],
            "source_reported_intervention":case["oracle"]["source_intervention"],
            "remaining_source_reported_faults":case["oracle"]["open_faults"],
            "source_reported_outcome_limit":case["oracle"]["uncertainty"],
            "source_reported_actual_measurements":case["oracle"]["source_actual_measurements"],
            "repair_created_by_HS":False,
            "checkpoint_scores_after_predictions":case_score,
        })
    flattened=[row for c in truth for row in c["checkpoint_scores_after_predictions"]]
    market_known=[r for r in flattened if r["market_item_exact_match"] is not None]
    family_known=[r for r in flattened if r["family_exact_match"] is not None]
    public_unresolved=[c for c in truth if not c["owner_reported_full_fix"]]
    assert len(raw)==len(flattened)==14
    result={
        "schema_version":REPORT,
        "holdout_corpus_sha256":file_sha(cases),
        "holdout_corpus_git_blob_sha1":git_blob_sha(cases),
        "precommitted_public_case_count":len(src["cases"]),
        "source_only_pre_solution_checkpoints":len(raw),
        "source_original_CircuitAI_evaluator_used":True,
        "model_code_frozen_at_base_revision_before_holdout_results":True,
        "scored_known_market_class_checkpoints":len(market_known),
        "matched_known_market_class_checkpoints":sum(x["market_item_exact_match"] for x in market_known),
        "scored_known_diagnostic_family_checkpoints":len(family_known),
        "matched_known_diagnostic_family_checkpoints":sum(x["family_exact_match"] for x in family_known),
        "weak_keyword_presence_checkpoints":sum(x["weak_keyword_relevance_proxy_any"] for x in flattened),
        "source_owner_did_not_confirm_final_repair_cases":len(public_unresolved),
        "physical_repairs_performed_or_independently_certified_by_HS":0,
        "source_answers_are_not_independent_laboratory_ground_truth":True,
        "physical_power_or_flight_authorized":False,
        "private_owner_device_data_access_authorized":False,
        "external_repair_profit_measured":False,
        "raw_blinded_engine_outputs":raw,
        "after_prediction_case_by_case_adjudication":truth,
    }
    (out/"UNSEEN_REPAIR_HOLDOUT_ORIGINAL_ENGINE_OUTPUTS.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    return result

def markdown(report:dict)->str:
    lines=["# Untouched seven-case, fourteen-checkpoint public repair holdout","",
           "No repairs, hardware measurements, physical certification, or engine patch was performed in this evaluation.",
           "",
           "## Predeclared classification results (NOT electrical root-cause accuracy)",
           "",
           "| Case | Checkpoint | Item | Item match | Guide family | Family match | Top fault | Workflow |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in report["after_prediction_case_by_case_adjudication"]:
        for x in c["checkpoint_scores_after_predictions"]:
            lines+=["| "+c["id"]+" | "+x["checkpoint_id"].split("__")[-1]+
                " | "+str(x["engine_market_item"])+" | "+str(x["market_item_exact_match"])+
                " | "+str(x["engine_family"])+" | "+str(x["family_exact_match"])+
                " | "+str(x["engine_leading_fault_hypothesis"])+" | "+
                str(x["software_workflow_verdict"])+" |"]
    lines+=["",
        "Known category comparisons: "+str(report["matched_known_market_class_checkpoints"])+
        " / "+str(report["scored_known_market_class_checkpoints"]),
        "Known family comparisons: "+str(report["matched_known_diagnostic_family_checkpoints"])+
        " / "+str(report["scored_known_diagnostic_family_checkpoints"]),
        "Weak any-keyword diagnostic text presence: "+str(report["weak_keyword_presence_checkpoints"])+
        " / "+str(report["source_only_pre_solution_checkpoints"])+
        " (not proof of correct diagnosis).",
        "", "## Documented source outcomes and falsification limits"]
    for c in report["after_prediction_case_by_case_adjudication"]:
        lines+=["", "### "+c["id"],
                "Original source: "+c["source_url"],
                "Reported outcome: "+c["reported_product_status"],
                "Owner's documented intervention: "+c["source_reported_intervention"],
                "Owner confirmed fully fixed: "+str(c["owner_reported_full_fix"]),
                "Remaining defects: "+("; ".join(c["remaining_source_reported_faults"]) or
                                        "none explicitly reported; no independent physical test"),
                "Uncertainty: "+c["source_reported_outcome_limit"]]
    lines+=["","## Interpretation", "",
       "Exact category and family match compare to labels frozen BEFORE HS was run. They are classification checks only.",
       "The diagnostic-keyword test is deliberately a weak relevance sanity check, not correctness.",
       "A video/forum comment is NOT a DMM verified root cause, and a claimed fix on one Syma X5SW is NOT evidence the original X5C aircraft was repaired.",
       "Models should not be re-tuned on these same seven held-out cases; any new changes require another independent corpus and fresh blind evaluation.", ""]
    return "\n".join(lines)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--cases",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    r=evaluate(a.root,a.cases,a.out)
    (a.out/"UNSEEN_REPAIR_HOLDOUT_SCORING.md").write_text(markdown(r))
    print(json.dumps({
        "cases":r["precommitted_public_case_count"],
        "blinded_sourced_checkpoints":r["source_only_pre_solution_checkpoints"],
        "known_market_item_hits":[r["matched_known_market_class_checkpoints"],r["scored_known_market_class_checkpoints"]],
        "known_family_hits":[r["matched_known_diagnostic_family_checkpoints"],r["scored_known_diagnostic_family_checkpoints"]],
        "weak_relevance_keywords":r["weak_keyword_presence_checkpoints"],
        "unresolved_owner_cases":r["source_owner_did_not_confirm_final_repair_cases"],
        "HS_actual_physical_repairs":0,
        "results":[
          {"id":s["checkpoint_id"],
           "item":s["engine_market_item"],
           "family":s["engine_family"],
           "fault":s["engine_leading_fault_hypothesis"],
           "software_workflow":s["software_workflow_verdict"]}
          for c in r["after_prediction_case_by_case_adjudication"]
          for s in c["checkpoint_scores_after_predictions"]
        ]
    },indent=2))
