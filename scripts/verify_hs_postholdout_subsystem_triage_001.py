#!/usr/bin/env python3
"""Post-#271 hand-built *development* diagnostic checks, never a new holdout."""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"apps/circuit-ai"))
from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
from src.intelligence.board_session_store import BoardSessionStore

CASES=[
    ("lcd_bias_not_battery","Nintendo Game Boy DMG-01",
     ["Device powers up but LCD/boot behavior is abnormal",
      "Technician reports negative LCD-bias DC-DC converter rail measured -30 V instead of nominal -19 V"],
     "retro_handheld_console","retro_lcd_bias_or_dc_dc_regulation_unverified",True),
    ("audio_without_headphone_note","Nintendo Game Boy Color",
     ["Game Boy starts games but built-in speaker audio is very quiet",
      "A new speaker and volume wheel cleaning did not restore loudness"],
     "retro_handheld_console","retro_audio_output_or_coupling_unverified",True),
    ("audio_with_working_headphones","Game Boy Color",
     ["No sound from built-in speaker", "Headphones work, display still works and gameplay still works"],
     "retro_handheld_console","speaker_jack_switch_or_audio_path_unverified",True),
    ("thinkpad_identification","Lenovo ThinkPad S430",
     ["Notebook suddenly fails to turn on after phone was powered over USB",
      "The same charger works in another compatible ThinkPad"],
     "laptop_or_macbook",None,False),
    ("adapter_id_sense","Dell Latitude laptop",
     ["Laptop reports charger not detected; battery will not charge",
      "Correct barrel adapter voltage present at jack but type and wattage cannot be determined"],
     "laptop_or_macbook","laptop_adapter_identification_or_sense_unverified",True),
    ("barrel_supply_load_droop","ASUS ROG Zephyrus M15",
     ["Barrel AC charging fluctuates, USB-C charging still works", "External charger measured 19.7 V no load and 13-19 V connected"],
     "laptop_or_macbook","laptop_barrel_dc_in_or_loaded_supply_unverified",True),
    ("iphone_degraded_battery","Apple iPhone 12 Pro",
     ["Battery health 74%, shutdowns at 35%, severe charge cycle count",
      "Charging varies with screen on/off and after cleaning Lightning port"],
     "phone_or_tablet","phone_battery_bms_or_state_dependent_charge_unverified",True),
    ("console_black_boot_not_port","Nintendo Switch HAC-001",
     ["Console black screen/no boot despite charging behavior measured by USB ammeter",
      "Prior M92 replacement did not resolve apparent no-power symptom"],
     "modern_game_console","console_boot_mode_or_power_path_unverified",True),
    ("printer_encoder_registration","HP OfficeJet printer",
     ["Print alignment output badly distorted and blurred",
      "Printhead cleaning has not resolved the page registration problem"],
     None,"printer_encoder_strip_or_registration_unverified",True),
    ("printer_bind_not_controller","Epson L3250 printer",
     ["Printhead carriage catches and makes rubbing noise at one repeatable spot",
      "Encoder strip cleaned, but mechanical motion still catches"],
     None,"printer_carriage_or_service_station_mechanical_unverified",True),
    ("new_build_quad_no_takeoff","Homebuilt FPV quadcopter drone",
     ["Newly built aircraft spins propellers but fails to take off",
      "Operator assumes CW/CCW motor rotation is right without measuring"],
     None,"propeller_orientation_or_thrust_path_unverified",True),
    ("postimpact_quad_regression","Toy quadcopter drone",
     ["After crash all rotors spin but drone doesn't lift", "Gear mesh and shafts not checked yet"],
     None,"postimpact_propulsion_path_unverified",True),
    ("switch_usb_video_original","Nintendo Switch OLED",
     ["Switch USB-C charges but docked HDMI video is missing"],
     "modern_game_console","modern_console_usb_c_port_or_video_filter_fault",False),
]

def check():
    failures=[];rows=[]
    with tempfile.TemporaryDirectory() as temp:
        evaluator=RepairCaseEvaluator(session_store=BoardSessionStore(Path(temp)/"sessions.json"))
        for name,hint,symptoms,item,top_expected,gate_expected in CASES:
            guide=evaluator.encyclopedia.generate(analysis={},symptoms=symptoms,device_hint=hint)
            out=evaluator.evaluate_case({
                "case_id":name, "title":"Synthetic post-holdout negative control",
                "device_hint":hint,"symptoms":symptoms,"notes":"","source_url":"https://example.invalid/synthetic",
                "observed_actions":[]}, commit_session=False)
            fault=out["repair_guide"]["top_fault"]
            triage=out["repair_guide"].get("triage_state") or {}
            if out["coverage"]["top_item"]!=item:
                failures.append(name+": device identity "+str(out["coverage"]["top_item"]))
            if top_expected is not None and fault!=top_expected:
                failures.append(name+": expected "+top_expected+", got "+str(fault))
            if bool(triage.get("requires_measurement"))!=gate_expected:
                failures.append(name+": triage evidence gate missing or overactive")
            if out["physical_repair_ready"] is not False:
                failures.append(name+": physical repair authority incorrectly granted")
            if gate_expected:
                if out["verdict"]=="solvable_now":
                    failures.append(name+": unverified differential incorrectly marked ready")
                if (triage.get("repair_ready") is not False or
                    guide.get("parts_and_tools",{}).get("likely_parts") or
                    guide.get("repair_playbooks",[{}])[0].get("title")!="Diagnostic evidence collection only; no repair approved"):
                    failures.append(name+": stale repair/parts path still present")
            if "drone" in hint.lower() or "printer" in hint.lower():
                if out["coverage"]["top_item"] is not None or out["verdict"]=="solvable_now":
                    failures.append(name+": forced OOD coverage or readiness")
            rows.append({"case":name,"market":out["coverage"]["top_item"],"family":out["repair_guide"]["family"],
                         "fault":fault,"verdict":out["verdict"],"requires_measurement":bool(triage.get("requires_measurement"))})
    report={"benchmark_kind":"post_holdout_synthetic_development_not_unseen_accuracy",
            "count":len(rows),"errors":failures,"rows":rows,
            "actual_HS_hardware_repaired":0,"qualified_power_or_flight":False}
    print(json.dumps(report,indent=2))
    if failures:raise SystemExit("Post-#271 differential synthetic checks FAILED")

if __name__=="__main__":check()
