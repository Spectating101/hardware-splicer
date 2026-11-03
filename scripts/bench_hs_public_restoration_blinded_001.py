#!/usr/bin/env python3
"""Run outcome-BLINDED public repair checkpoints through original Circuit-AI.

The user-facing product is a sourced diagnostic benchmark, not a physical
repair. Each scene only supplies observations available before its source
outcome; full solution steps and outcomes stay in withheld oracle material.
No transcript, video frame, measured voltage or hardware actuation invented.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA="hardware_splicer.public_restoration_replay_cases.v1"
RESULT_SCHEMA="hardware_splicer.public_restoration_blinded_replay_results.v1"

def require(ok,reason):
    if not ok:raise ValueError("HS public source benchmark: "+reason)

def digest(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()

def generate(root:Path,casefile:Path,out:Path)->dict:
    sys.path.insert(0,str((root/"apps/circuit-ai").resolve()))
    from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
    from src.intelligence.board_session_store import BoardSessionStore

    corpus=json.loads(casefile.read_text())
    require(corpus["schema_version"]==SCHEMA and corpus["case_count"]==len(corpus["cases"])>=4,
            "invalid public case corpus")
    require(corpus["all_actual_operator_measurements_unknown"] is True and
            corpus["HS_actual_physical_repairs_performed"]==0,
            "physical repair outcome fabricated")
    out.mkdir(parents=True,exist_ok=True)
    engine=RepairCaseEvaluator(session_store=BoardSessionStore(out/"internal_ephemeral_sessions.json"))
    predictions=[]
    adjudications=[]
    for case in corpus["cases"]:
        source_url=case["source"]["url"]
        require(source_url.startswith("https://") and case["oracle"]["physical_repair_by_hs"] is False,
                "unverified source or falsely attributed HS repair")
        checkpoint_rows=[]
        for checkpoint in case["checkpoints"]:
            # Outcome/repair solution, future events and oracle vocabulary are
            # NOT copied into input. Input source reference is a mere URL.
            ident=case["id"]+"__"+checkpoint["id"]
            blinded={
                "case_id":ident,
                "title":checkpoint["title"],
                "device_hint":checkpoint["device_hint"],
                "symptoms":list(checkpoint["symptoms"]),
                "notes":checkpoint["notes"],
                "source_url":source_url,
                "source_kind":"public_pre_solution_observations_only",
                "observed_actions":[],
                "expected_lane":"",
            }
            require(all(key not in blinded for key in
                        ("oracle","full_breakdown","expected_subsystems","source_reported_result")),
                    "source gold outcome leaked")
            actual=engine.evaluate_case(blinded,commit_session=False)
            diagnostics=engine.encyclopedia.generate(
                analysis={},symptoms=blinded["symptoms"],device_hint=blinded["device_hint"])
            technique={
                "engine_diagnostic_flow":diagnostics.get("diagnostic_flow") or [],
                "engine_requested_evidence":diagnostics.get("evidence_to_collect_next") or [],
                "engine_candidate_faults":(diagnostics.get("fault_candidates") or [])[:5],
                "engine_first_board_session_tasks":actual["board_session"]["first_tasks"],
            }
            generated=json.dumps(technique,ensure_ascii=False,default=str).lower()
            keyword_matches=[]
            for expected in checkpoint["expected_subsystems"]:
                hits=[token for token in expected["any_of"] if token.lower() in generated]
                keyword_matches.append({
                    "engineering_subsystem":expected["id"],
                    "expected_terms":expected["any_of"],
                    "terms_mentioned_in_actual_generated_diagnostic_text":hits,
                    "keyword_presence_not_ground_truth_correctness":True})
            checkpoint_rows.append({
                "checkpoint_id":ident,
                "public_case_id":case["id"],
                "source_reference":source_url,
                "blinded_input_hash":hashlib.sha256(
                    json.dumps(blinded,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
                "blinded_engine_input":blinded,
                "observed_source_steps_allowed":checkpoint["evidence_available_steps"],
                "engine_was_given_case_oracle_or_future_repair":False,
                "real_original_CircuitAI_case_evaluator_executed":True,
                "original_engine_output":actual,
                "original_engine_generated_diagnostics":technique,
                "expected_subsystem_lexical_presence":keyword_matches,
                "workflow_verdict_is_not_physical_device_repair":True,
                "physical_device_tested_by_HS":False,
                "physical_robot_or_device_power_authorized":False,
            })
        predictions.extend(checkpoint_rows)
        # Adjudicate only after evaluation of *every* checkpoint of the case.
        truth=case["oracle"]
        adjudications.append({
            "case_id":case["id"],
            "source":source_url,
            "source_type":case["source"]["kind"],
            "checkpoints_completed_before_oracle_read":len(checkpoint_rows),
            "reported_intervention":truth["source_reported_hardware_intervention"],
            "reported_outcome":truth["source_reported_result"],
            "source_reported_product_state":truth["product_state"],
            "source_reported_residual_faults":truth["known_remaining_defects"],
            "root_cause_evidence_limit":truth["underlying_cause_certainty"],
            "public_author_only_not_independent_lab_evidence":True,
            "public_owner_claimed_fully_fixed":truth["source_owner_confirmed_full_repair"],
            "HS_completed_real_hardware_restoration":False,
            "missing_for_certification":truth["missing_technical_evidence"],
            "engineering_lesson":case["engineering_lesson"],
        })
    result={
        "schema_version":RESULT_SCHEMA,
        "original_corpus_sha256":digest(casefile),
        "source_case_count":len(corpus["cases"]),
        "blinded_engine_checkpoint_count":len(predictions),
        "actual_original_CircuitAI_case_evaluator_exercised":True,
        "source_video_frames_or_transcripts_reviewed":False,
        "original_public_claims_independently_lab_verified":False,
        "HS_actual_physical_repair_count":0,
        "original_operator_hardware_measurements_ingested":0,
        "physical_power_authorized":False,
        "flight_authorized":False,
        "customer_data_access_authorized":False,
        "recovered_resale_value_verified":False,
        "blinded_engine_predictions":predictions,
        "withheld_oracle_revealed_after_engine_predictions":adjudications,
    }
    (out/"PUBLIC_RESTORATION_BLINDED_REPLAY.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    return result

def summary(report:dict)->str:
    lines=["# Hardware Splicer: blinded replay of public restoration records","",
           "This is a source-backed SOFTWARE diagnostic benchmark, not physical repair evidence.","",
           "| Public case | Earlier checkpoint | Item category | Device family | Top fault | Software workflow verdict |",
           "| --- | --- | --- | --- | --- | --- |"]
    for row in report["blinded_engine_predictions"]:
        x=row["original_engine_output"]
        lines.append("| "+row["public_case_id"]+" | "+row["checkpoint_id"].split("__")[-1]+
                     " | "+str(x["coverage"]["top_item"])+" | "+
                     str(x["repair_guide"]["family"])+" | "+
                     str(x["repair_guide"]["top_fault"])+" | "+str(x["verdict"])+" |")
    lines+=["","## Source-reported outcomes revealed after prediction",""]
    for v in report["withheld_oracle_revealed_after_engine_predictions"]:
        lines+=["### "+v["case_id"],
                "Source: "+v["source"],
                "Original repair actions: "+v["reported_intervention"],
                "Reported outcome: "+v["reported_outcome"],
                "Outcome classification: "+v["source_reported_product_state"],
                "Residual faults: "+("; ".join(v["source_reported_residual_faults"]) or
                                      "none reported; not full physical certification"),
                "Missing evidence: "+("; ".join(v["missing_for_certification"])),
                "Engineering lesson: "+v["engineering_lesson"],""]
    lines+=["## Interpretation boundary","",
            "The original Circuit-AI evaluator labels workflow feasibility, not factual physical success. A generated fault candidate is not independently confirmed by a meter or board view. The YouTube case was curated only from its public chapter-description timestamps; no full video or transcript was ingested, and no real device was repaired by HS.",""]
    return "\n".join(lines)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",default=".",type=Path)
    ap.add_argument("--cases",default="examples/public_restoration_replays/cases_2026_11_03.json",type=Path)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    results=generate(a.root,a.cases,a.out)
    (a.out/"PUBLIC_RESTORATION_BLINDED_SUMMARY.md").write_text(summary(results))
    print(json.dumps({"real_original_engine_replay_checkpoints":results["blinded_engine_checkpoint_count"],
                      "source_cases":results["source_case_count"],
                      "HS_actual_physical_repairs":results["HS_actual_physical_repair_count"],
                      "engine_outputs":[
                           {"id":row["checkpoint_id"],
                            "category":row["original_engine_output"]["coverage"]["top_item"],
                            "family":row["original_engine_output"]["repair_guide"]["family"],
                            "fault":row["original_engine_output"]["repair_guide"]["top_fault"],
                            "software_workflow_verdict":row["original_engine_output"]["verdict"]}
                           for row in results["blinded_engine_predictions"]]},indent=2))
