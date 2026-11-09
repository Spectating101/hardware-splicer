"""Bounded repair-intake triage for external, retrospective restoration cases.

* ACTUAL HS integration: uses native repair_intake.extract_repair_context and
  apply_repair_intake_context, while keeping the output a differential +
  measurement plan, not an authorized repair or electrical specification.
* HYPOTHESES ARE NOT validated diagnoses or calibrated probabilities.
* This is a tiny human-authored generic fault taxonomy, not video vision, an
  LLM or a proof of autonomous generalization.
* Source descriptions of video outcomes must be loaded by the evaluator only
  AFTER diagnostic output is produced. This rule engine imports no gold labels.
"""
from __future__ import annotations
from typing import Any,Mapping

from .repair_intake import extract_repair_context,apply_repair_intake_context

SCHEMA="hs.restoration.triage_report.v1"

# Order is stable; high scores represent evidence ranking, NOT likelihood.
FAULTS={
 "corroded_battery_contact":{
   "name":"High-resistance or corroded battery terminal",
   "verify":["Power removed: inspect battery contacts for corrosion or weak spring force",
             "Measure continuity and voltage drop across contacts using an appropriate safe meter setup",
             "Do not assume cleaning repairs a trace or via beyond the contact"],
   "next_if_found":"Restore/replace confirmed defective battery terminal, then verify supply path",
 },
 "open_power_trace":{
   "name":"Open copper path between battery input and board power rail",
   "verify":["With cells removed, compare continuity between terminal solder joint and next mapped power node",
             "Inspect both sides, solder joints and vias for oxidation or lifted copper",
             "Only bridge after confirming net identity, load and absence of a short"],
   "next_if_found":"Qualified low-voltage conductor restoration plus isolation and continuity checks",
 },
 "power_switch_fault":{
   "name":"Defective power switch",
   "verify":["Remove cells and meter switch contacts in ON/OFF states",
             "Inspect slide-switch solder joints for cracks"],
   "next_if_found":"Repair or replace verified faulty switch, not the entire logic board",
 },
 "damaged_usb_c_port":{
   "name":"Damaged USB-C receptacle or solder connections",
   "verify":["Remove external power and inspect tongue, pins, anchors and underside joints under magnification",
             "Inspect VBUS/GND continuity and CC lines using known-good pinout and dedicated USB-C tester",
             "Check for shorts and lifted pads before any reflow or replacement"],
   "next_if_found":"Qualified microsoldering repair with magnification and post-repair USB-C tester verification",
 },
 "charging_ic_fault":{
   "name":"Charging or power-management controller fault",
   "verify":["Confirm charger/port input path and rail voltages before implicating controller",
             "Compare controller enable/rail signals with verified schematic or boardview"],
   "next_if_found":"Only replace a verified failed charging IC using proper board-level process",
 },
 "battery_management_fault":{
   "name":"Battery pack or battery protection issue",
   "verify":["Inspect pack condition without puncturing or applying uncontrolled direct voltage",
             "Use approved manufacturer diagnostics or a qualified service technician"],
   "next_if_found":"Use correct certified replacement pack or seek professional battery service",
 },
 "optical_pickup_failure":{
   "name":"Disc optical pickup / laser module not reading",
   "verify":["Compare with a known-good undamaged disc and verify normal spindle/focus behavior",
             "Check mechanism and optical pickup service information; do not look into powered laser",
             "Verify failure before replacing matched optical assembly"],
   "next_if_found":"Qualified pickup/drive replacement followed by official alignment and read tests",
 },
 "dirty_disc_or_lens":{
   "name":"Unreadable disc, dirty lens, or optical contamination",
   "verify":["Use known-good disc and inspect readable surfaces for damage",
             "Clean optics using approved nonabrasive procedure only if appropriate"],
   "next_if_found":"Service dirty media/optics and rerun read test before ordering laser",
 },
 "spindle_mechanism_fault":{
   "name":"Disc spindle / lid switch / mechanical alignment fault",
   "verify":["Observe spindle behavior only with standard guard operation",
             "Check switch or alignment according to service procedure; never bypass laser interlock"],
   "next_if_found":"Repair or replace documented mechanical fault, then repeat media-read tests",
 },
 "display_polarizer_damage":{
   "name":"LCD polarizer degradation independent of power failure",
   "verify":["First establish whether LCD glass and signal path work",
             "Compare polarizer condition under light; avoid unnecessary panel replacement"],
   "next_if_found":"Optical film restoration is separate from electrical power recovery",
 },
}
RULES={
 "no_power":{"corroded_battery_contact":2,"open_power_trace":2,
             "power_switch_fault":2,"damaged_usb_c_port":1,
             "charging_ic_fault":1,"battery_management_fault":1},
 "corrosion_visible":{"corroded_battery_contact":6,"open_power_trace":4},
 "screen_damage":{"display_polarizer_damage":3},
 "no_charge_response":{"damaged_usb_c_port":6,"charging_ic_fault":4,
                       "battery_management_fault":2},
 "usb_c_power_input":{"damaged_usb_c_port":3,"charging_ic_fault":1},
 "disc_read_failure":{"optical_pickup_failure":7,"dirty_disc_or_lens":6,
                      "spindle_mechanism_fault":5},
 "boots_normally":{"optical_pickup_failure":1},
 "contacts_cleaned_still_dead":{"corroded_battery_contact":-7,"open_power_trace":4},
 "switch_checked_good":{"power_switch_fault":-7},
 "battery_path_continuity_open":{"open_power_trace":12},
 "charge_ic_checked_good":{"charging_ic_fault":-7,"damaged_usb_c_port":2},
 "charging_port_physically_damaged":{"damaged_usb_c_port":12},
 "optical_pickup_suspected":{"optical_pickup_failure":4},
}
KNOWN_CODES=frozenset(RULES)


def _staged_codes(case:Mapping[str,Any],stage:int)->list[str]:
    if stage not in (0,1):raise ValueError("stage must be 0 or 1")
    codes=case.get("initial_codes",[])
    if not isinstance(codes,list) or not codes:
        raise ValueError("repair case lacks actual visible observations")
    if stage:
        extra=case.get("followup_codes",[])
        if not isinstance(extra,list):raise ValueError("followup observations malformed")
        codes=codes+extra
    # A new code means the diagnostic vocabulary is insufficient. No
    # confident fallback to a guessed repair.
    unknown=set(codes)-KNOWN_CODES
    if unknown:raise ValueError("unrecognized repair observation; needs expert review: "+repr(sorted(unknown)))
    return list(dict.fromkeys(codes))


def triage(case:Mapping[str,Any],stage:int=0)->dict[str,Any]:
    if case.get("schema")!="hs.restoration.video_blind_intake.v1":
        raise ValueError("not a typed restoration case")
    # No gold-fix fields are authorized in any diagnostic input.
    for forbidden in ("root_cause","reported_outcome","repair_steps","hidden_outcome","answer"):
        if forbidden in case:raise ValueError("gold answer must be kept outside intake")
    first=case.get("repair_intake",{})
    if not first.get("symptoms"):raise ValueError("missing symptom intake")
    ctx=extract_repair_context({"repair_intake":first})
    normalized=apply_repair_intake_context({"repair_intake":first})
    assert normalized["repair_intake_context"]["symptoms"]==ctx["symptoms"]
    if stage:
        updated=extract_repair_context({"repair_intake":case.get("followup_repair_intake",{})})
        if not updated["symptoms"]:raise ValueError("no follow-up electrical/visual observation")
    else:
        updated=None
    codes=_staged_codes(case,stage)
    evidence={}
    for code in codes:
        for ident,delta in RULES[code].items():
            evidence.setdefault(ident,[]).append({"observation":code,"delta":delta})
    scores={
        ident:sum(d["delta"] for d in contributions)
        for ident,contributions in evidence.items()
    }
    ranked=[
      {"rank":i+1,"hypothesis_id":k,"hypothesis":FAULTS[k]["name"],
       "support_score_not_probability":v,
       "observation_contributions":evidence[k],
       "tests_before_repair":FAULTS[k]["verify"],
       "conditional_repair_only_after_measurements":FAULTS[k]["next_if_found"]}
      for i,(k,v) in enumerate(
          sorted(scores.items(),key=lambda pair:(-pair[1],pair[0]))[:3]
      ) if v>0
    ]
    if not ranked:raise ValueError("insufficient positive evidence for even a measured triage")
    return {
      "schema":SCHEMA,
      "case_id":str(case["case_id"]),
      "device":str(case["device"]),
      "stage":"followup_after_observation" if stage else "initial_symptoms_only",
      "native_HS_repair_intake_schema":ctx["schema_version"],
      "native_HS_symptoms":ctx["symptoms"],
      "new_observations":updated["symptoms"] if updated else [],
      "evidence_codes_used":codes,
      "ranked_differential":ranked,
      "scoring":"explicit human-authored rules, uncalibrated ranking, not an AI/video diagnosis",
      "safety":{
        "unpowered_visual_and_continuity_checks_first":True,
        "charge_or_power_injection_authorized":False,
        "hot_air_or_microsolder_repair_authorized":False,
        "battery_pack_handling_authorized":False,
        "optical_laser_interlock_bypass_authorized":False,
        "no_unsupported_board_or_parts_substitution":True,
      },
      "release":{
        "fault_confirmed_by_HS_physical_meter":False,
        "repair_executed_by_HS":False,
        "restoration_completed_by_HS":False,
        "fabrication_or_procurement_authorized":False,
      }
    }


def main() -> None:
    """Public entry point: inspect one symptom-only case; never load outcomes."""
    import argparse
    import json
    from pathlib import Path

    p=argparse.ArgumentParser(description="HS source-separated repair triage (no physical authority)")
    p.add_argument('--case',type=Path,required=True,help='Symptom-only JSON case; never answer key')
    p.add_argument('--stage',choices=('initial','followup'),default='initial')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    result=triage(json.loads(args.case.read_text()),stage=int(args.stage=='followup'))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case':result['case_id'],'best_hypothesis':
           result['ranked_differential'][0]['hypothesis_id'],
           'physical_repair_authorized':False},indent=2))


if __name__=='__main__':
    main()
