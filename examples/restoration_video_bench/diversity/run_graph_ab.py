"""Matched, source-locked, outcome-free Gemini A/B for raw restoration captions.

Control = existing raw native-HS intake + Gemini diagnostic prompt.
Intervention = SAME caption evidence + native HS engineering-source graph
and test-selection constraints. Neither sees creator's later repair outcome.
Identical LLM (gemini-3.8-flash-low) and same schema, one call per arm.

This is a pilot of graph+prompt intervention, NOT proof of video frame vision,
schematic retrieval or physical repair capability.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from hardware_splicer.restoration_caption_ingest import caption_case_context
from hardware_splicer.restoration_engineering_assist import add_engineering_assistance
from hardware_splicer.restoration_reasoning_agent import agy_chat, diagnose, sha

HERE=Path(__file__).resolve().parent
CASES=HERE/"cases.json"
FIXED_ORDER=[
    ("bosch_dryer_slow_heat", "hs_graph", "plain"),
    ("dewalt_blower_intermittent", "plain", "hs_graph"),
    ("tab_s6_lite_dead", "hs_graph", "plain"),
    ("ps5_pro_no_power_hdmi", "plain", "hs_graph"),
    ("delonghi_eletta_faults", "hs_graph", "plain"),
    ("a53_touch_failure", "plain", "hs_graph"),
]
PROTOCOL="hs.restoration.real_caption_graph_paired_ab.v1"
MODEL="gemini-3.8-flash-low"
END_WINDOW_S=120

def protocol_spec():
    return {
        "schema":PROTOCOL,
        "precommitted_case_arm_order":[list(r) for r in FIXED_ORDER],
        "exact_model":MODEL,
        "input_stage":f"first_{END_WINDOW_S}_seconds_actual_video_webvtt",
        "arm_control":"plain_native_hs_intake_and_base_gemini_prompt",
        "arm_treatment":"same_native_intake_plus_HS_engineering_source_graph_and_falsifiable_test_prompt",
        "equal_model_calls_per_arm":True,
        "equal_raw_evidence_per_arm":True,
        "outcomes_not_loaded":True,
        "graph_does_not_retrieve_schematics":True,
        "measured_criteria":[
            "model_valid_output","source_citation_integrity",
            "reported_next_safe_check","model_ranked_fault_mechanisms",
            "manual_blinded_repair_fault_family_score_only_after_prediction_freeze"
        ],
        "no_physical_actions":True,
    }

def build_cases(*, captions_dir:Path):
    items={x["id"]:x for x in json.loads(CASES.read_text())["cases"]}
    prepared=[]
    for case_id,first,second in FIXED_ORDER:
        c=items[case_id]
        p=captions_dir/(c["video_id"]+".en-orig.vtt")
        if not p.is_file():
            raise ValueError("actual source caption missing: "+str(p))
        plain=caption_case_context(
            case_id=case_id,device=c["device"],title_symptom=c["title_symptom"],
            video_url=c["source_url"],hazards=c["hazards"],vtt_path=p,
            cutoff_s=END_WINDOW_S,
        )
        enhanced=add_engineering_assistance(plain)
        assert plain["evidence"]==enhanced["evidence"]
        assert plain["evidence_sha256"]==enhanced["evidence_sha256"]
        assert plain["caption_provenance"]==enhanced["caption_provenance"]
        prepared.append((case_id,(first,second),{"plain":plain,"hs_graph":enhanced}))
    return prepared

def run(*, captions_dir:Path,out:Path,timeout_s:int=60)->dict:
    prepared=build_cases(captions_dir=captions_dir)
    result={"protocol":protocol_spec(),"protocol_sha256":sha(protocol_spec()),
            "model":MODEL,"cases":[],"complete":False}
    # Do not open or import any postreview outcome, accuracy score or repair
    # label. Results are committed before scoring.
    out.parent.mkdir(parents=True,exist_ok=True)
    for case_id,order,arms in prepared:
        row={"case_id":case_id,"arm_order":list(order),
             "identical_evidence_sha256":arms["plain"]["evidence_sha256"],
             "source_raw_vtt_sha256":arms["plain"]["caption_provenance"]["raw_vtt_sha256"],
             "arms":{}}
        result["cases"].append(row)
        for arm_name in order:
            context=arms[arm_name]
            receipt=diagnose(context,model=MODEL,inference=agy_chat,timeout_s=timeout_s)
            row["arms"][arm_name]={
                "hs_source_graph_sha256":context.get("hs_engineering_ledger",{}).get("graph_sha256"),
                "receipt":receipt,
            }
            # Resume support is deliberately absent: each failed run must
            # become an explicit failed artifact, not a silent reroll.
            temp=out.with_name(out.name+".tmp")
            temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
            os.replace(temp,out)
            print(json.dumps({
                "case_id":case_id,"arm":arm_name,"status":receipt["status"],
                "secs":receipt["elapsed_seconds"],
                "first_mechanism":(
                    receipt["plan"]["hypotheses"][0]["mechanism"][:160]
                    if receipt.get("plan") and receipt["plan"]["hypotheses"] else None
                ),
            }),flush=True)
    result["complete"]=True
    temp=out.with_name(out.name+".tmp")
    temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    os.replace(temp,out)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--captions-dir",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--timeout",type=int,default=60)
    args=parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing to overwrite previous model evidence; use a NEW path")
    result=run(captions_dir=args.captions_dir,out=args.out,timeout_s=args.timeout)
    print(json.dumps({
        "complete":result["complete"],
        "cases":len(result["cases"]),
        "valid_by_arm":{a:sum(
            c["arms"][a]["receipt"]["status"]=="proposed_unverified_differential"
            for c in result["cases"]
        ) for a in ("plain","hs_graph")},
    },indent=2))

if __name__=="__main__":
    main()
