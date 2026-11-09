"""No-gold, source-bound validation and summary of the matched graph A/B.

This intentionally does not determine which model guessed the right fault
mechanism; exact/string comparison to a repair outcome is not sufficient.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.restoration_reasoning_agent import sha

def verify(report: dict)->dict:
    from run_graph_ab import protocol_spec, FIXED_ORDER, MODEL
    assert report["protocol"]==protocol_spec()
    assert report["protocol_sha256"]==sha(protocol_spec())
    if not report["complete"] or len(report["cases"])!=len(FIXED_ORDER):
        raise ValueError("A/B evidence not yet complete")
    output=[]
    for row,(cid,a,b) in zip(report["cases"],FIXED_ORDER):
        if row["case_id"]!=cid or row["arm_order"]!=[a,b]:
            raise ValueError("A/B case/order swapped after preregistration")
        items={}
        for name in ("plain","hs_graph"):
            arm=row["arms"][name]
            r=arm["receipt"]
            if r["case_id"]!=cid:
                raise ValueError("case mismatch")
            if r["evidence_sha256"]!=row["identical_evidence_sha256"]:
                raise ValueError("different source evidence given to model arms")
            assert r["model_requested"]==MODEL
            assert r["model_reported"]==MODEL
            assert r["provider_reported"]=="agy_antigravity_subscription_cli"
            assert r["repair_authorized"] is False
            assert r["actual_video_frames_analyzed"] is False
            assert r["physical_measurements_by_HS"] is False
            assert r["caption_provenance"]["raw_vtt_sha256"]==row["source_raw_vtt_sha256"]
            if sha({k:v for k,v in r.items() if k not in ("receipt_sha256","elapsed_seconds")})!=r["receipt_sha256"]:
                raise ValueError("model receipt content tampered")
            if name=="hs_graph" and r.get("hs_source_graph_sha256")!=arm["hs_source_graph_sha256"]:
                raise ValueError("HS engineering source graph changed after inference")
            if name=="plain" and "hs_source_graph_sha256" in r:
                raise ValueError("plain Gemini was supplied HS tool results")
            plan=r.get("plan")
            items[name]={
                "status":r["status"],
                "elapsed_seconds":r["elapsed_seconds"],
                "prompt_sha256":r["prompt_sha256"],
                "first_ranked_mechanism":(
                    plan["hypotheses"][0]["mechanism"] if plan and plan["hypotheses"] else None
                ),
                "next_safe_check":plan["next_safe_check"] if plan else None,
                "hypotheses_count":len(plan["hypotheses"]) if plan else 0,
                "tokens_estimated":r.get("usage",{}),
            }
        if items["plain"]["prompt_sha256"]==items["hs_graph"]["prompt_sha256"]:
            raise ValueError("arms used identical prompts; experimental treatment missing")
        output.append({"case_id":cid,"same_source_sha256":row["identical_evidence_sha256"],
                       "plain":items["plain"],"hs_graph":items["hs_graph"]})
    return {
        "schema":"hs.restoration.graph_ab_no_gold_summary.v1",
        "model":MODEL,
        "cases":len(output),
        "valid_output_count_by_arm":{
            arm:sum(r[arm]["status"] in ("proposed_unverified_differential","model_abstained") for r in output)
            for arm in ("plain","hs_graph")
        },
        "inference_seconds_by_arm":{
            arm:round(sum(r[arm]["elapsed_seconds"] for r in output),2)
            for arm in ("plain","hs_graph")
        },
        "accuracy_not_scored_without_external_adjudication":True,
        "no_claim_of_tools_improving_fault_identification":True,
        "results":output
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--infile",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=verify(json.loads(args.infile.read_text()))
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        "cases":result["cases"],
        "valid":result["valid_output_count_by_arm"],
        "seconds":result["inference_seconds_by_arm"],
    },indent=2))

if __name__=="__main__":
    main()
