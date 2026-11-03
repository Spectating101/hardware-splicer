#!/usr/bin/env python3
"""Compile field-usable device recovery work orders from EXISTING HS repair lanes.

No new repair UI or autopilot. Sources:
* Existing apps/circuit-ai repair_lane_packs.py (directly imported for actual
  source prompts and stop conditions)
* Existing sourced real_repair_cases/cases.json
* Existing six real_hardware_recovery pilot catalog

Only a blank physically executable human work order and measurable acceptance
checklist are emitted. No measurements, identity, part validation, repair,
power-on, sale, or flight authorizations are fabricated.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import hashlib
import math
from pathlib import Path

DEFAULT_CATALOG=Path("examples/real_hardware_recovery/pilots_2026_11.json")
REPAIR_CASES=Path("apps/circuit-ai/eval/real_repair_cases/cases.json")
REPAIR_LANES=Path("apps/circuit-ai/src/intelligence/repair_lane_packs.py")
SCHEMA="hardware_splicer.real_device_field_work_order.v1"

REUSE_LANES={
  "usb_fan_contact_driver_repair":"small_motor_usb",
  "thinkpad_t480_recover":None,
  "pixel9_mobile_service":None,
  "framework_reuse_mini_pc":None,
  "printer_scrap_camera_slider":"small_motor_usb",
  "salvaged_quad_bench_only":None,
}
WORKFLOWS={
 "usb_fan_contact_driver_repair":{
   "identify":["Record exact fan model and original operating USB voltage/current labels",
               "Confirm fan is USB-powered without mains or compromised lithium battery"],
   "deenergized":["Disconnect USB completely and inspect casing for frayed leads/visible damage",
                  "Perform disconnected harness and switch continuity tests; preserve original pinout"],
   "compare":["Compare measured input voltage and motor voltage to actual device rating",
              "Check motor winding resistance and connector continuity under flex"],
   "supervised_test":["With appropriately rated current-limited supply and qualified operator, observe no-load current and motor speed",
                      "Check stable low/high speed only if those modes exist on THIS fan"],
   "final":["Confirm reassembled guard securely covers moving blades",
            "Record functional operation at documented modes and absence of abnormal current/heat/noise"],
   "measurement_templates":[
     {"name":"rated_input_voltage","unit":"V","bounds_from":"original device nameplate/manual","capture":"documented_not_assumed"},
     {"name":"input_voltage_idle","unit":"V","bounds_from":"actual device rating"},
     {"name":"input_current_during_run","unit":"A","bounds_from":"nameplate or known-good measured baseline"},
     {"name":"harness_resistance_unplugged","unit":"ohm","bounds_from":"actual harness comparison"},
     {"name":"motor_winding_resistance_unplugged","unit":"ohm","bounds_from":"service reference or same known-good part"},
   ]
 },
 "thinkpad_t480_recover":{
   "identify":["Record exact laptop machine type/FRU and symptom; hide serial numbers",
               "Obtain recorded consent for storage handling and repair"],
   "deenergized":["Disconnect AC; isolate battery as described by OEM before disassembly",
                  "Inspect power port, storage, fan and swollen/compromised battery"],
   "compare":["Verify donor/replacement RAM, SSD, fan FRU against official model service references",
              "Check adapter rating and measured electrical behavior if no-power"],
   "supervised_test":["Operator-authorized first boot, storage health, memory diagnostics",
                      "Observe fan response and temperature under documented workload"],
   "final":["Record boot stability, storage health, ports, Wi-Fi and thermal log",
            "Return or sanitize storage only according to owner-authorized instruction"],
   "measurement_templates":[
      {"name":"adapter_output_voltage","unit":"V","bounds_from":"OEM rated adapter and service manual"},
      {"name":"storage_health_status","unit":"categorical","bounds_from":"device diagnostic"},
      {"name":"cpu_temperature_idle","unit":"C","bounds_from":"documented thermal profile"},
      {"name":"cpu_temperature_under_load","unit":"C","bounds_from":"model-specific limits"},
      {"name":"successful_boot_duration","unit":"min","bounds_from":"operator-defined acceptance"}
   ]
 },
 "pixel9_mobile_service":{
   "identify":["Confirm exact Pixel submodel/revision and official repair procedure availability",
               "Record owner authorization without copying customer account content"],
   "deenergized":["Check battery deformation/heat; halt if unsafe",
                  "Have qualified operator follow vendor battery/display opening precautions"],
   "compare":["Verify genuine-compatible model-specific display or USB-C assembly",
              "Confirm availability of any required post-repair calibration"],
   "supervised_test":["Operator uses official post-repair diagnostic procedure",
                      "Check screen, touch, cameras, charging and biometrics with owner consent"],
   "final":["Record all functions and closure/adhesive status",
            "Do not claim factory ingress resistance without verified factory test"],
   "measurement_templates":[
      {"name":"usb_charge_input_voltage","unit":"V","bounds_from":"OEM charger + repair documentation"},
      {"name":"charge_current","unit":"A","bounds_from":"OEM supported behavior"},
      {"name":"postrepair_functional_pass_count","unit":"count","bounds_from":"operator's complete model-specific checklist"}
   ]
 },
 "framework_reuse_mini_pc":{
   "identify":["Record exact Framework mainboard generation and revision and original CAD interface",
               "Confirm donor mainboard ownership and allowed storage usage"],
   "deenergized":["Verify original thermal assembly and power connection are suitable for reuse",
                  "Inspect stand-offs, external expansion ports and enclosure design"],
   "compare":["Use exact OEM 2D/3D case mounts and standoff geometry",
              "Verify memory, storage, power supply and fan matched to THIS board"],
   "supervised_test":["Operator-authorized board bring-up with original cooler, airflow and isolation",
                      "Monitor storage, OS boot and temperatures under defined load"],
   "final":["Confirm stable independent mini-PC function, safe enclosure clearance and port access",
            "Record actual salvage valuation, case cost and power consumption"],
   "measurement_templates":[
      {"name":"power_input_voltage","unit":"V","bounds_from":"original mainboard manual"},
      {"name":"idle_power_draw","unit":"W","bounds_from":"measured with validated meter"},
      {"name":"load_power_draw","unit":"W","bounds_from":"tested system capacity"},
      {"name":"cpu_temperature_under_load","unit":"C","bounds_from":"OEM thermal limit"},
      {"name":"system_stable_runtime","unit":"min","bounds_from":"agreed test duration"}
   ]
 },
 "printer_scrap_camera_slider":{
   "identify":["Record donor printer model and exact motor/driver identification",
               "Inspect recovered carriage/rail and mechanical end-stops"],
   "deenergized":["With AC fully disconnected, identify and segregate mains supply components",
                  "Measure motor winding and harness continuity"],
   "compare":["Compare true winding rating, stepper driver current settings and actual wiring",
              "Dimension camera load, belt travel, rail standoffs and carriage stability"],
   "supervised_test":["Using separate rated current-limited low-voltage supply, verify limit switches and emergency stop BEFORE any motion",
                      "Qualified operator runs low-speed empty-carriage motion, then controlled load"],
   "final":["Reassemble secure camera mount and guards",
            "Measure endstop behavior, speed consistency, repeatability and no thermal overload"],
   "measurement_templates":[
      {"name":"motor_winding_resistance","unit":"ohm","bounds_from":"original motor winding spec"},
      {"name":"driver_voltage","unit":"V","bounds_from":"original motor+driver datasheets"},
      {"name":"driver_limit_current","unit":"A","bounds_from":"actual verified driver limits"},
      {"name":"slider_travel","unit":"mm","bounds_from":"actual measured physical rail"},
      {"name":"endstop_response_ms","unit":"ms","bounds_from":"safety and control test requirement"}
   ]
 },
 "salvaged_quad_bench_only":{
   "identify":["Record donor drone make/model, frame and regulator information",
               "Identify recovered motor, ESC, FC, receiver and damaged components"],
   "deenergized":["REMOVE ALL PROPELLERS; quarantine any unknown or damaged batteries",
                  "Inspect ESC and motor condition with all power sources removed"],
   "compare":["Compare motor KV/rating, ESC current, control protocol and frame layout",
              "Use supported ArduPilot/PX4/Betaflight firmware and QGroundControl conventions"],
   "supervised_test":["Run SITL simulations and log arming/failsafe behavior without powering flight hardware",
                      "If separately human-authorized, perform only propeller-free secured bench motor direction check"],
   "final":["Preserve measured electrical/failsafe logs and nonflying bench rig",
            "Never claim flightworthiness or authorize outdoor flight from bench result"],
   "measurement_templates":[
      {"name":"motor_winding_resistance","unit":"ohm","bounds_from":"identified manufacturer motor"},
      {"name":"esc_max_current_rating","unit":"A","bounds_from":"original ESC spec"},
      {"name":"undamaged_battery_voltage","unit":"V","bounds_from":"chemistry and safe pack spec"},
      {"name":"failsafe_activation_time","unit":"s","bounds_from":"OEM firmware/config requirement"}
   ]
 },
}
STAGES=("intake","safety_isolation","diagnosis","compatibility","supervised_bench","full_product_acceptance")

def need(ok,msg):
    if not ok:raise ValueError("HS field work order: "+msg)

def load_existing_lane_packs(root:Path)->dict:
    path=root/REPAIR_LANES
    spec=importlib.util.spec_from_file_location("hs_existing_circuitai_repair_lanes",path)
    need(spec is not None and spec.loader is not None,"existing repair lane module cannot be loaded")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return {key:mod.RepairLanePacks().get_pack(key) for key in ("controller_input","battery_charging","small_motor_usb")}

def build(root:Path,catalog:Path,pilot_id:str)->dict:
    meta=json.loads(catalog.read_text())
    need(meta["schema_version"]=="hardware_splicer.real_hardware_recovery_pilot_catalog.v1",
         "unexpected existing source pilot schema")
    catalog_pilots={row["id"]:row for row in meta["pilots"]}
    need(pilot_id in catalog_pilots,"unknown source physical product pilot")
    source=catalog_pilots[pilot_id]
    need(source["status"]=="candidate_no_hardware" and
         not any(source["authority"].values()),"source pilot already declares physical success")
    need(pilot_id in WORKFLOWS and pilot_id in REUSE_LANES,
         "no source product test protocol; do not infer")
    existing_cases={row["case_id"]:row for row in json.loads((root/REPAIR_CASES).read_text())}
    case=existing_cases.get(source["existing_case_id"]) if source.get("existing_case_id") else None
    lane_name=REUSE_LANES[pilot_id]
    lanes=load_existing_lane_packs(root)
    lane=lanes[lane_name] if lane_name else None
    need(lane_name is None or lane is not None,"existing repair lane absent")
    plan=WORKFLOWS[pilot_id]
    groups=[
        ("intake",plan["identify"]),
        ("safety_isolation",plan["deenergized"]),
        ("diagnosis",plan["compare"]+(lane["measurements"] if lane else [])),
        ("compatibility",["Validate actual replacement parts, ratings and connectors against OEM specifications"]),
        ("supervised_bench",plan["supervised_test"]),
        ("full_product_acceptance",plan["final"]),
    ]
    need(tuple(key for key,_ in groups)==STAGES,"missing source device lifecycle stage")
    tasks=[]
    for stage,items in groups:
        for i,instruction in enumerate(items,1):
            tasks.append({"task_id":stage+"_"+str(i).zfill(2),
                          "stage":stage,"instruction":instruction,
                          "status":"NOT_PERFORMED","source":"existing_HS_repair_lane" if
                          lane and instruction in lane["measurements"] else "source_device_protocol",
                          "evidence_sha256":None,"observed_by":None,
                          "observed_at_utc":None})
    required=[{"evidence_gate":gate,"status":"NOT_SUBMITTED",
               "source_evidence_file":None,"sha256":None,
               "observed_value":None,"operator_review":None}
              for gate in source["required_evidence"]]
    readings=[{"measurement_id":x["name"],"unit":x["unit"],
               "source_of_acceptable_limits":x["bounds_from"],
               "accepted_min":None,"accepted_max":None,
               "observed_value":None,"instrument_id":None,
               "observed_at_utc":None,"operator_signature":None}
              for x in plan["measurement_templates"]]
    safety=list(dict.fromkeys(source["stop_conditions"]+(lane["stop_conditions"] if lane else [])))
    need(len(safety)>=2 and len(readings)>=3 and len(tasks)>=10 and len(required)>=5,
         "incomplete measurement and source safety gates")
    report={
      "schema_version":SCHEMA,"pilot_id":pilot_id,"hardware_state":"NO_DONOR_ASSIGNED",
      "product_goal":source["final_product"],
      "source_pilot_catalog_sha256":hashlib.sha256(catalog.read_bytes()).hexdigest(),
      "source_existing_repair_lane_path":str(REPAIR_LANES) if lane else None,
      "reused_repair_lane_id":lane_name,
      "reused_source_repair_case":source.get("existing_case_id"),
      "reused_source_repair_case_title":case["title"] if case else None,
      "source_repair_case_reference":case.get("source_url") if case else None,
      "original_existing_HS_paths":source["existing_hs_paths"],
      "source_repair_lane_evidence_prompts":lane["evidence_prompts"] if lane else [],
      "product_specific_stages":tasks,
      "required_physical_evidence_gates":required,
      "measurable_acceptance_template":readings,
      "operator_identity_redacted":None,"owner_consent_document":None,
      "device_model_label":None,"safety_stop_conditions":safety,
      "source_guides_not_actual_evidence":source["guides"],
      "estimated_and_actual_economics":{"currency":None,
          "acquisition_cost":None,"parts_cost":None,"labor_minutes":None,
          "hourly_labor_rate":None,"test_and_energy_cost":None,
          "warranty_reserve":None,"realized_recovery_value":None,
          "net_unit_value":None},
      "evaluation":{"physical_repair_completed":False,
                    "original_device_actually_tested":False,
                    "source_compatibility_qualified":False,
                    "all_real_measurements_passed":False,
                    "finished_product_accepted":False,
                    "human_operator_authorized_bench_power":False,
                    "flight_or_drone_movement_authorized":False,
                    "commercial_proceeds_verified":False,
                    "verdict":"AWAITING_OWNED_DONOR_AND_ORIGINAL_MEASUREMENTS"},
    }
    return report

def to_markdown(work:dict)->str:
    lines=[
        "# HS real-device field work order — "+work["pilot_id"],
        "",
        "**FIELD STATUS:** NO OWNED DONOR OR PHYSICAL TEST HAS BEEN SUBMITTED.",
        "**Authority:** No powered test, drone flight, completed repair, or sale is authorized by this work order.",
        "",
        "## Finished physical product acceptance goal",
        work["product_goal"],"",
        "## Existing HS repair/reuse paths",
    ]
    lines+=["- "+x for x in work["original_existing_HS_paths"]]
    if work["reused_repair_lane_id"]:
        lines+=["","Existing Circuit-AI repair lane: "+work["reused_repair_lane_id"]]
    if work["source_repair_case_reference"]:
        lines+=["Existing reference case (not physical evidence): "+work["source_repair_case_reference"]]
    lines+=["","## Human-operated step sequence"]
    for stage in STAGES:
        lines+=["","### "+stage.replace("_"," ").title()]
        lines+=["- [ ] "+item["instruction"] for item in work["product_specific_stages"]
                if item["stage"]==stage]
    lines+=["","## Actual observations (blank until measured)"]
    lines+=["| Measurement | Unit | Real acceptance limit source | Observed | Instrument |",
            "| --- | --- | --- | --- | --- |"]
    for m in work["measurable_acceptance_template"]:
        lines+=["| "+m["measurement_id"]+" | "+m["unit"]+
                " | "+m["source_of_acceptable_limits"]+" | — | — |"]
    lines+=["","## Evidence required before an outcome can be evaluated"]
    lines+=["- [ ] "+e["evidence_gate"] for e in work["required_physical_evidence_gates"]]
    lines+=["","## Immediate stop conditions"]
    lines+=["- "+text for text in work["safety_stop_conditions"]]
    lines+=["","## Economic outcome"]
    lines+=["Acquisition, labor, parts, test costs, warranty and recovered value: "
            "**all unmeasured**; do not make positive ROI claims.",""]
    return "\n".join(lines)

def output_bundle(root:Path,catalog:Path,pilot_id:str,out:Path)->dict:
    need(not out.exists() or not any(out.iterdir()),"refuse to overwrite a previous field work order")
    out.mkdir(parents=True,exist_ok=True)
    work=build(root,catalog,pilot_id)
    (out/"FIELD_WORK_ORDER.json").write_text(json.dumps(work,indent=2)+"\n")
    (out/"HUMAN_BENCH_CARD.md").write_text(to_markdown(work))
    return {"pilot_id":pilot_id,"task_count":len(work["product_specific_stages"]),
            "unperformed_operator_tasks":len(work["product_specific_stages"]),
            "required_physical_evidence_gates":len(work["required_physical_evidence_gates"]),
            "measurement_fields_blank":len(work["measurable_acceptance_template"]),
            "physical_hardware_tested":False,"power_on_authorized":False,
            "new_repair_web_app_created":False}

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",type=Path,default=Path("."))
    ap.add_argument("--catalog",type=Path,default=DEFAULT_CATALOG)
    ap.add_argument("--pilot",required=True,choices=tuple(REUSE_LANES))
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    print(json.dumps(output_bundle(args.root,args.catalog,args.pilot,args.output),indent=2))
