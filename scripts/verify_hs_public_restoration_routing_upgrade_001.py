#!/usr/bin/env python3
"""Independent routing regression: sourced repair replay + original 7 HS cases.

Read the actual Circuit-AI output from the AFTER patch, compare it with the
preserved BEFORE source replay (CI run 41635416606), and also execute the
existing seven-case regression sample through the same original evaluator.
This verifies routing and needed evidence, NEVER physical repair success.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from scripts.verify_hs_public_restoration_blinded_001 import verify as verify_blinded

BASELINE_RUN="https://github.com/Spectating101/hardware-splicer/actions/runs/41635416606"
EXPECTATIONS={
 "public_gameboy_dmg_2026_power_and_lcd": {
    "item":"retro_handheld_console",
    "family":"retro_handheld_aa_power",
    "top_fault":"aa_battery_contact_or_power_switch_fault",
    "original_family":["laptop_power_path","battery_charging_gadget"],
    "original_item":"retro_handheld_console",
    "diagnostic_keywords":["aa", "battery", "contact", "lcd"],
 },
 "public_macbook_a1534_port_2023": {
    "item":"laptop_or_macbook",
    "family":"laptop_power_path",
    "top_fault":"laptop_usb_c_port_or_input_path_fault",
    "original_family":["laptop_power_path","laptop_power_path"],
    "original_item":"small_usb_gadget",
    "diagnostic_keywords":["usb-c", "charger", "port"],
 },
 "public_iphone6s_replacement_not_charging_2018": {
    "item":"phone_or_tablet",
    "family":"phone_charging_port_flex",
    "top_fault":"phone_charge_port_or_replacement_flex_fault",
    "original_family":["battery_charging_gadget","small_dc_motor_gadget"],
    "original_item":"battery_charging_gadget",
    "diagnostic_keywords":["flex", "port", "battery", "original"],
 },
 "public_switch_oled_usb_c_noise_filter_video_2024": {
    "item":"modern_game_console",
    "family":"modern_console_usb_c_video",
    "top_fault":"modern_console_usb_c_port_or_video_filter_fault",
    "original_family":["relay_power_box","relay_power_box"],
    "original_item":"retro_handheld_console",
    "diagnostic_keywords":["usb-c", "hdmi", "filter", "charging"],
 },
}

def require(cond,msg):
    if not cond:raise ValueError("HS sourced restoration routing regression: "+msg)

def verify(root:Path,cases:Path,replay:Path)->dict:
    source=json.loads(cases.read_text())
    report=json.loads(replay.read_text())
    source_audit=verify_blinded(cases,replay)
    check={x["id"]:x for x in source["cases"]}
    require(set(check)==set(EXPECTATIONS),"actual public source cases changed")
    evaluated={}
    rows=report["blinded_engine_predictions"]
    require(len(rows)==8,"missing blinded original engine replay")
    for r in rows:
        case_id=r["public_case_id"]
        expected=EXPECTATIONS[case_id]
        model=r["original_engine_output"]
        family=model["repair_guide"]["family"]
        item=model["coverage"]["top_item"]
        fault=model["repair_guide"]["top_fault"]
        require(item==expected["item"],
                case_id+" market routing mismatch: "+str(item))
        require(family==expected["family"],
                case_id+" family routing mismatch: "+str(family))
        require(fault==expected["top_fault"],
                case_id+" top hypothesis incorrectly ranked: "+str(fault))
        if case_id in ("public_iphone6s_replacement_not_charging_2018",
                       "public_switch_oled_usb_c_noise_filter_video_2024"):
            require(model["verdict"]=="assistive_only",
                    case_id+" risks falsely claiming fully independent model-specific repair readiness")
        original_tasks=r["original_engine_generated_diagnostics"]
        generated=json.dumps(original_tasks,ensure_ascii=False).lower()
        for marker in expected["diagnostic_keywords"]:
            require(marker in generated,
                    case_id+" lacks appropriate generated procedure word: "+marker)
        require(r["engine_was_given_case_oracle_or_future_repair"] is False and
                r["physical_device_tested_by_HS"] is False,
                "repair gold or physical authority was leaked")
        evaluated.setdefault(case_id,[]).append({
           "checkpoint":r["checkpoint_id"],"category":item,
           "family":family,"leading_fault_hypothesis":fault,
           "workflow_verdict":model["verdict"],
           "software_workflow_only_not_physical_repair":True
        })
    # Execute seven pre-existing public-guide cases as an independent
    # negative regression set. These are source reference cases, not tests
    # of repaired physical devices.
    sys.path.insert(0,str((root/"apps/circuit-ai").resolve()))
    from src.intelligence.board_session_store import BoardSessionStore
    from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
    original_data=json.loads((root/"apps/circuit-ai/eval/real_repair_cases/cases.json").read_text())
    baseline=json.loads((root/"apps/circuit-ai/eval/real_repair_cases/real_repair_case_eval.json").read_text())
    original_by_id={v["case_id"]:v for v in baseline["cases"]}
    require(len(original_data)==len(original_by_id)==7,"original seven-case engine regression not available")
    evaluator=RepairCaseEvaluator(session_store=BoardSessionStore(
        Path("/tmp/hs-public-restoration-regression-transient-session.json")))
    old_cases=[]
    for original in original_data:
        curr=evaluator.evaluate_case(original,commit_session=False)
        before=original_by_id[original["case_id"]]
        # Existing seven repairs are not to be rewritten to make new
        # hand-picked cases pass; exceptions must be explicit and reviewed.
        require(curr["repair_guide"]["family"]==before["repair_guide"]["family"],
                "existing source repair family regressed: "+original["case_id"])
        require(curr["repair_guide"]["top_fault"]==before["repair_guide"]["top_fault"],
                "existing source repair fault ranking regressed: "+original["case_id"])
        require(curr["verdict"]==before["verdict"],
                "existing seven reference case workflow verdict regressed: "+original["case_id"])
        old_cases.append({"id":original["case_id"],
                          "original_family_preserved":True,
                          "original_top_fault_preserved":True,
                          "original_software_workflow_verdict_preserved":True})
    return {
       "schema_version":"hardware_splicer.restoration_model_specific_route_regression.v1",
       "baseline_original_engine_run":BASELINE_RUN,
       "source_outcome_blinding_independently_verified":source_audit["all_8_input_payloads_confirmed_not_leaking_future_source_steps"],
       "sourced_repair_cases":len(evaluated),
       "blinded_model_predictions_correctly_routed":sum(len(x) for x in evaluated.values()),
       "existing_original_7_case_regression_preserved":len(old_cases),
       "route_comparison":evaluated,
       "original_existing_case_regressions":old_cases,
       "source_reported_fixes_not_independent_bench_truth":True,
       "model_did_not_authorize_any_real_repair_power_solder_or_flight":True,
       "HS_physical_products_restored":0,
       "actual_operator_hardware_measurements_recorded":0,
       "owner_real_world_repair_economics_measured":False,
       "future_unseen_heldout_hardware_case_accuracy_certified":False,
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",default=".",type=Path)
    ap.add_argument("--cases",required=True,type=Path)
    ap.add_argument("--replay",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    a=ap.parse_args()
    report=verify(a.root,a.cases,a.replay)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"blinded_cases_routed":report["sourced_repair_cases"],
                      "blinded_checkpoints_routed":report["blinded_model_predictions_correctly_routed"],
                      "original_seven_cases_not_regressed":report["existing_original_7_case_regression_preserved"],
                      "physical_repaired_products":0},indent=2))
