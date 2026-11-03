#!/usr/bin/env python3
"""Replay a previously failed real repair through the new typed-evidence path.

Development-only demonstration, NOT a new blind performance score. The
source technician's actions and measurements are public reports, not HS work.
The original unstructured 5-step engine trace must stay unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "examples/whole_product_restorations/dell_latitude_e5250_technician_case_2026.json"

# Strict event order, with all data extracted from the source case chronology.
# No T5 functional outcome or post-stage observation enters any early intake.
# Event names are typed engineer interpretations, NOT verified component truth.
SCHEDULE = {
    "T0": [
        ("measurement", "adapter_output_unloaded", 19.9, "V",
         "External adapter output measured with laptop disconnected"),
        ("observation", "adapter_led_trips_when_connected", None, None,
         "Adapter power indicator extinguishes when plugged into this laptop"),
    ],
    "T1": [
        ("measurement", "bench_supply_setpoint_not_board_voltage", 19.0, "V",
         "Nominal supply setting, actual board rail collapsed almost to zero"),
        ("measurement", "input_fault_current_reported", 2.3, "A",
         "Source-reported current into low-voltage-collapsed motherboard"),
        ("observation", "rail_collapses_under_load_reported", None, None,
         "Supply current rises but board input rail is nearly zero"),
        ("observation", "board_short_persists_with_jack_removed", None, None,
         "Source technician isolated the charging port; main-board short remained"),
        ("intervention", "current_injection", None, None,
         "Original technician operation recorded for provenance only, NOT authorized"),
    ],
    "T2": [
        ("measurement", "localization_current_reported", 1.3, "A",
         "Source described first attempt to localize short; not an HS recommended current"),
        ("observation", "sense_resistor_heat_is_false_localization", None, None,
         "Resistor appeared warm because it carried fault current; not proven defective"),
        ("observation", "mlcc_removal_cleared_board_short", None, None,
         "Source reports board short disappeared after removal of identified MLCC"),
        ("intervention", "flammable_solvent_heating", None, None,
         "Source historical solvent-assisted heating; explicitly prohibited by HS"),
    ],
    "T3": [
        ("intervention", "component_rework", None, None,
         "Source technician fitted donor MLCC without public exact part rating"),
        ("observation", "source_claims_component_replacement", None, None,
         "Source reports replacement of previously isolated capacitor"),
        ("measurement", "board_input_rail", 19.9, "V",
         "Source measured recovered main rail after capacitor substitution"),
        ("measurement", "board_idle_current", 40.0, "mA",
         "Source-reported idle current after short removed"),
        ("measurement", "power_button_logic", 3.3, "V",
         "Source measured button circuit despite continued no-boot condition"),
        ("observation", "main_input_rail_recovered", None, None,
         "External source reports recovered main DC input"),
        ("observation", "no_boot_after_input_recovered", None, None,
         "System remained off at first partial reassembly despite restored input"),
    ],
    "T4": [
        ("observation", "rtc_disconnected_changes_startup", None, None,
         "Original technician reports RTC battery disconnect affected startup state"),
        ("intervention", "powered_rtc_connection", None, None,
         "Source describes powered RTC reconnect; not permitted as an HS procedure"),
    ],
}

EXPECTED_STATES = {
    "T0": "input_loading_suspected",
    "T1": "board_input_short_reported",
    "T2": "component_short_localized_reported",
    "T3": "second_boot_fault_after_rail_recovery",
    "T4": "rtc_dependent_boot_state_reported",
}


def build_event_schedule(case):
    assert case["case_id"] == "dell_latitude_e5250_2026_technician_board_repair"
    assert [x["id"] for x in case["chronology"]] == ["T0", "T1", "T2", "T3", "T4", "T5"]
    results = {}
    for stage, fixtures in SCHEDULE.items():
        results[stage] = []
        for i,(kind,signal,value,unit,condition) in enumerate(fixtures,1):
            row = {
                "event_id": stage + "_E" + f"{i:02d}",
                "stage_id": stage,
                "event_type": kind,
                "signal": signal,
                "actor": "external_technician",
                "provenance": "third_party_source_report",
                "source_url": case["source"]["article_url"],
                "condition": condition,
                "HS_instrument_verified": False,
                "repair_authorized": False,
            }
            if kind == "measurement":
                row.update({"value": value, "unit": unit})
            results[stage].append(row)
    # Invariant: only the seven source numeric readings, not fabricated extra data.
    srcreadings = {(m["target"], m["value"], m["unit"])
                   for event in case["chronology"] for m in event["source_measurements"]}
    evalues = [(r["value"],r["unit"]) for events in results.values() for r in events
               if r["event_type"]=="measurement"]
    assert len(srcreadings) == len(evalues) == 7
    for voltage,unit in evalues:
        assert any(m["value"]==voltage and m["unit"]==unit
                   for event in case["chronology"] for m in event["source_measurements"])
    assert "T5" not in results
    return results


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--case",type=Path,default=CASE)
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    case=json.loads(args.case.read_text())
    original=json.loads(args.baseline.read_text())
    baseline=original["stages"]
    assert len(baseline)==5
    assert [r["stage_id"] for r in baseline]==list(EXPECTED_STATES)
    original_faults = [r["real_engine_output"]["repair_guide"]["top_fault"] for r in baseline]
    assert original_faults == [
        "battery_charge_path_fault",
        "battery_charge_path_fault",
        "battery_charge_path_fault",
        "laptop_usb_c_port_or_input_path_fault",
        "laptop_usb_c_port_or_input_path_fault",
    ], "Original failed predictions were altered: no clean before/after evidence"

    sys.path.insert(0,str(ROOT/"apps/circuit-ai"))
    from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
    from src.intelligence.board_session_store import BoardSessionStore
    from src.intelligence.repair_power_path_evidence import normalize_events
    schedule=build_event_schedule(case)
    output=[]
    cumulative=[]
    args.out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hs_typed_e5250_") as folder:
        evalr=RepairCaseEvaluator(session_store=BoardSessionStore(Path(folder)/"sessions.json"))
        for row in baseline:
            stage=row["stage_id"]
            cumulative+=schedule[stage]
            normalize_events(cumulative)
            entry=dict(row["real_engine_input"])
            entry["evidence_events"]=list(cumulative)
            result=evalr.evaluate_case(entry,commit_session=False)
            state=result["evidence_state"]
            if state["state"]!=EXPECTED_STATES[stage]:
                raise AssertionError("stateful diagnosis failed for "+stage+": "+state["state"])
            if result["repair_guide"]["top_fault"]!=state["fault_id"]:
                raise AssertionError("actual engine still ranks stale generic guess")
            if result["physical_repair_ready"] is not False:
                raise AssertionError("typed evidence improperly authorized real-world repair")
            output.append({
                "stage":stage,
                "input_source_measurements_known":[x["event_id"] for x in cumulative
                    if x["event_type"]=="measurement"],
                "typed_event_ids_known":[x["event_id"] for x in cumulative],
                "input_source_event_records":list(cumulative),
                "original_engine_fault":row["real_engine_output"]["repair_guide"]["top_fault"],
                "stateful_engine_fault":result["repair_guide"]["top_fault"],
                "stateful_engine_verdict":result["verdict"],
                "actual_engine_output":result,
                "actual_evidence_state":state,
                "source_reported_state_not_verified_root_cause":True,
                "source_result_not_used_to_promote_physical_authority":True,
            })
    source_sha=hashlib.sha256(args.case.read_bytes()).hexdigest()
    report={
        "schema_version":"hs.laptop_power_state_development_episode.v1",
        "case_id":case["case_id"],
        "source_file_sha256":source_sha,
        "baseline_engine_output_sha256":hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        "original_unmodified_trace_was_compared":True,
        "study_classification":"known_case_post_failure_development_not_new_unseen_validation",
        "actual_existing_evaluator_used":True,
        "source_measurements_reported":7,
        "HS_independent_measurements":0,
        "physical_repairs_by_HS":0,
        "real_customer_product_acceptance":"NOT_VERIFIED",
        "part_number_verified":False,
        "physical_repair_approved":False,
        "machine_state_progression":output,
    }
    path=args.out/"E5250_TYPED_EVIDENCE_STATE_TRACE.json"
    path.write_text(json.dumps(report,indent=2)+"\n")
    notes=[
        "# E5250: original template diagnosis versus typed-evidence state tracking",
        "",
        "**Study:** Retrospective development on a previously known failure. No independent fault accuracy, physical repair, or new unseen holdout.",
        "",
        "| Step | Original top fault (preserved) | Evidence-state top fault | State transition |",
        "| --- | --- | --- | --- |",
    ]
    for r in output:
        notes.append("| "+r["stage"]+" | "+r["original_engine_fault"]+" | "+
                     r["stateful_engine_fault"]+" | "+r["actual_evidence_state"]["state"]+" |")
    notes.extend([
        "",
        "The typed observations are hand-mapped from a public source already known to the developer. Their source veracity and causal significance have NOT been independently verified.",
        "Every state includes source IDs, explicit rejected alternatives, and required next evidence. No numeric probabilities are claimed.",
        "Source measurement count 7; HS independent measurements 0. Source operator interventions do not authorize repetition.",
        "The known source's BitLocker screen does not mean complete battery, RTC, peripheral, thermal or customer acceptance.",
        "No physical release, MLCC substitution or resale approval. Qualified technician and original component specification required.",
        "",
    ])
    (args.out/"E5250_EVIDENCE_STATE_COMPARISON.md").write_text("\n".join(notes))
    print(json.dumps({
        "actual_existing_engine":True,
        "stages":[{"stage":r["stage"],"from":r["original_engine_fault"],
                   "to":r["stateful_engine_fault"],
                   "state":r["actual_evidence_state"]["state"],
                   "verdict":r["stateful_engine_verdict"]} for r in output],
        "source_measurements":7,"HS_measurements":0,
        "independently_correct_root_causes_claimed":0,
        "physical_repair_or_release_authorized":False,
    },indent=2))


if __name__=="__main__":
    main()
