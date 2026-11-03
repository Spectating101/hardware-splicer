#!/usr/bin/env python3
"""Independent source and outcome-blind integrity checks for public repair replay.

Never treat public owner messages, YouTube chapter summaries or original
Circuit-AI workflow scores as physical repair, battery or flight authority.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def need(cond,why):
    if not cond:raise ValueError("HS independent public restoration audit: "+why)

def canonical(data):
    return json.dumps(data,sort_keys=True,separators=(",",":")).encode()

def verify(cases:Path,report:Path)->dict:
    source=json.loads(cases.read_text())
    result=json.loads(report.read_text())
    need(source["schema_version"]=="hardware_splicer.public_restoration_replay_cases.v1",
         "source version wrong")
    need(result["schema_version"]=="hardware_splicer.public_restoration_blinded_replay_results.v1",
         "report version wrong")
    need(result["original_corpus_sha256"]==hashlib.sha256(cases.read_bytes()).hexdigest(),
         "source corpus replaced")
    indexed={c["id"]:c for c in source["cases"]}
    need(len(indexed)==4==result["source_case_count"],"source real cases absent")
    predictions=result["blinded_engine_predictions"]
    assessments=result["withheld_oracle_revealed_after_engine_predictions"]
    need(len(predictions)==8==result["blinded_engine_checkpoint_count"] and len(assessments)==4,
         "independent two-stage replay coverage missing")
    allowed_ids={c["id"]+"__"+cp["id"] for c in source["cases"] for cp in c["checkpoints"]}
    need(len(allowed_ids)==8 and
         {p["checkpoint_id"] for p in predictions}==allowed_ids,
         "checkpoint dropped or duplicated")
    for case in source["cases"]:
        need(case["source"]["url"].startswith("https://") and
             len(case["full_breakdown"])>=5 and
             case["oracle"]["physical_repair_by_hs"] is False,
             "source chronology or physical claim wrong")
        need([x["step"] for x in case["full_breakdown"]]==list(
             range(1,len(case["full_breakdown"])+1)),"source timeline stage malformed")
        need(all(x["evidence"] in {
             "owner_initial","expert_advice_not_measurement",
             "expert_advice_not_direct_measurement",
             "owner_intervention","owner_reported_partial_success",
             "owner_reported_residual_fault","owner_diagnostic_observation",
             "owner_intended_action","owner_reported_fix",
             "owner_reported_original_and_intervention",
             "owner_reported_postrepair_fault",
             "owner_reported_diagnostic_reversal",
             "expert_inference_not_verified_final_repair",
             "youtube_description_chapter"} for x in case["full_breakdown"]),
             "source evidence tier misrepresented")
        if case["source"]["kind"]=="youtube_description_timestamp_chapters_only":
            need(case["source"]["transcript_or_frame_review_available"] is False,
                 "video frame analysis not actually conducted")
            need(not case["oracle"]["source_owner_confirmed_full_repair"],
                 "unverified full HDMI restoration claim")
        if case["oracle"]["known_remaining_defects"]:
            need(case["oracle"]["source_owner_confirmed_full_repair"] is False,
                 "device with known residual faults incorrectly fully repaired")
        for cp in case["checkpoints"]:
            need(0<len(cp["evidence_available_steps"])<len(case["full_breakdown"]),
                 "replay step is not pre-outcome observation")
            need(cp["evidence_available_steps"]==sorted(set(cp["evidence_available_steps"])),
                 "nonchronological or duplicate source steps")
            need(cp["gold_visible"] is False,
                 "source gold exposed in pre-solution checkpoint")
            need(cp["symptoms"] and cp["expected_subsystems"],
                 "source observation or scoring target missing")
    for row in predictions:
        case=indexed[row["public_case_id"]]
        cp=next(x for x in case["checkpoints"] if row["checkpoint_id"]==case["id"]+"__"+x["id"])
        expected={
            "case_id":row["checkpoint_id"],
            "title":cp["title"],
            "device_hint":cp["device_hint"],
            "symptoms":cp["symptoms"],
            "notes":cp["notes"],
            "source_url":case["source"]["url"],
            "source_kind":"public_pre_solution_observations_only",
            "observed_actions":[],
            "expected_lane":"",
        }
        need(row["blinded_engine_input"]==expected and
             row["blinded_input_hash"]==hashlib.sha256(canonical(expected)).hexdigest(),
             "future repairs leaked to diagnostic input or source changed")
        need(row["observed_source_steps_allowed"]==cp["evidence_available_steps"],
             "source evidence chronology changed")
        output=row["original_engine_output"]
        need(output["case_id"]==row["checkpoint_id"] and
             output["source_url"]==case["source"]["url"],
             "not real original Circuit-AI evaluator output")
        need(output["verdict"] in {"solvable_now","assistive_only","not_ready"} and
             isinstance(output["workflow_score"],(float,int)) and
             0<=output["workflow_score"]<=1,
             "original engine verdict invalid")
        need(output["repair_guide"]["family"] and
             output["board_session"]["task_count"] is not None,
             "actual source repair engine did not emit hypotheses and tasks")
        actual_diag=json.dumps(row["original_engine_generated_diagnostics"],
                               ensure_ascii=False,default=str).lower()
        need(len(row["expected_subsystem_lexical_presence"])==len(cp["expected_subsystems"]),
             "expected source-scoring subsystem dropped")
        for claim,expected_item in zip(row["expected_subsystem_lexical_presence"],
                                        cp["expected_subsystems"]):
            hits=[token for token in expected_item["any_of"] if token.lower() in actual_diag]
            need(claim["engineering_subsystem"]==expected_item["id"] and
                 claim["terms_mentioned_in_actual_generated_diagnostic_text"]==hits and
                 claim["keyword_presence_not_ground_truth_correctness"] is True,
                 "model-generated diagnostic search term misreported")
        need(row["engine_was_given_case_oracle_or_future_repair"] is False and
             row["physical_device_tested_by_HS"] is False and
             row["physical_robot_or_device_power_authorized"] is False,
             "software output promoted to physical repair")
    for a in assessments:
        c=indexed[a["case_id"]]
        need(a["source"]==c["source"]["url"] and
             a["source_reported_product_state"]==c["oracle"]["product_state"] and
             a["public_owner_claimed_fully_fixed"] is c["oracle"]["source_owner_confirmed_full_repair"] and
             a["source_reported_residual_faults"]==c["oracle"]["known_remaining_defects"] and
             a["checkpoints_completed_before_oracle_read"]==len(c["checkpoints"]),
             "documented source outcome or qualification rewritten")
        need(a["HS_completed_real_hardware_restoration"] is False and
             a["public_author_only_not_independent_lab_evidence"] is True,
             "web story misrepresented as HS actual bench proof")
    for key in ("physical_power_authorized","flight_authorized",
                "customer_data_access_authorized","recovered_resale_value_verified",
                "source_video_frames_or_transcripts_reviewed",
                "original_public_claims_independently_lab_verified"):
        need(result[key] is False,"illegitimate source/physical authority: "+key)
    need(result["HS_actual_physical_repair_count"]==0 and
         result["original_operator_hardware_measurements_ingested"]==0,
         "fictitious physical repair evidence")
    return {
      "schema_version":"hardware_splicer.public_restoration_independent_acceptance.v1",
      "public_source_cases":len(indexed),
      "source_documented_breakdown_events":sum(len(x["full_breakdown"]) for x in indexed.values()),
      "real_original_CircuitAI_evaluator_checkpoints":len(predictions),
      "source_repair_outcomes_preserved_as_separate_blinded_oracles":True,
      "source_reported_owner_complete_repair_claims":sum(x["oracle"]["source_owner_confirmed_full_repair"] for x in indexed.values()),
      "source_fully_repaired_hardware_independently_verified":0,
      "HS_real_hardware_repaired":0,
      "video_frame_and_transcript_material_reviewed":False,
      "physical_power_motion_sale_authority":False,
      "all_8_input_payloads_confirmed_not_leaking_future_source_steps":True,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--cases",required=True,type=Path)
    ap.add_argument("--report",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    receipt=verify(a.cases,a.report)
    a.output.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2))
