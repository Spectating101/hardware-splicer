"""Frozen matched model test of CONDITIONAL numeric evidence authority.

Protocol fixed before new inference:
- Sony PS5 Pro: original creator-narrated voltage/resistance claims.
- Original Nintendo Game Boy: PUBLISHED expected thresholds, NO actual meter logs.

Both arms see identical sourced textual claims. Treatment calls the real HS
engineering_source_graph and uses its recorded conditions/authority.
The output only measures source discipline and hypothesis changes, not
completed repairs or model accuracy. No postreview labels are imported.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from hardware_splicer.restoration_numeric_case import build_numeric_case_context
from hardware_splicer.restoration_reasoning_agent import agy_chat, diagnose, sha
from hardware_splicer.restoration_source_numeric_ledger import register_source_numeric_claims

HERE=Path(__file__).resolve().parent
MANIFEST=HERE/"source_numeric_claims.json"
MODEL="gemini-3.8-flash-low"
CASE_ARMS=[
    ("ps5_pro_no_power_hdmi",("plain","hs_numeric_source")),
    ("dmg_reported_battery_only_failure",("hs_numeric_source","plain")),
]
PROTOCOL="hs.restoration.numeric_source_authority_matched_ab.v1"

def protocol():
    return {
        "schema":PROTOCOL,
        "exact_model":MODEL,
        "case_order":[{"id":c,"arm_order":list(arms)} for c,arms in CASE_ARMS],
        "model_calls_per_arm_per_case":1,
        "source_claims_identical_between_arms":True,
        "creator_outcome_or_repair_method_never_loaded":True,
        "control":"same source-backed claim text and source URL without machine provenance ledger",
        "intervention":"same source-backed claim text with actual native engineering source graph, condition IDs and declared-only authority guidance",
        "no_fabricated_measurement_or_manufacturer_specification":True,
        "real_board_revision_never_verified_by_this_test":True,
        "hardware_physical_actions":False,
        "not_an_isolated_graph_effect":"treatment has longer prompt and explicit source-authority instructions",
        "no_gold_accuracy_scoring_in_runner":True,
    }

def source_inputs(*,video_vtt:Path,article_html:Path)->tuple[dict,dict]:
    fixed=json.loads(MANIFEST.read_text())
    ledger=register_source_numeric_claims(fixed,local_artifacts={
        "ps5pro_early_captions":video_vtt,
        "dmg_published_expectations":article_html,
    })
    return fixed,ledger

def run(*,video_vtt:Path,article_html:Path,out:Path,timeout_s:int)->dict:
    manifest,ledger=source_inputs(video_vtt=video_vtt,article_html=article_html)
    record={
        "protocol":protocol(),
        "protocol_sha256":sha(protocol()),
        "original_numeric_source_manifest_sha256":sha(manifest),
        "real_HS_graph_sha256":ledger["native_HS_source_graph_sha256"],
        "numeric_source_validation":ledger,
        "cases":[],
        "complete":False,
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    for cid,order in CASE_ARMS:
        # This runner is the frozen 2026-11-10 v1 model experiment.
        base=build_numeric_case_context(ledger,case_id=cid,assisted=False,render_version="legacy_v1")
        hs=build_numeric_case_context(ledger,case_id=cid,assisted=True,render_version="legacy_v1")
        if base["evidence_sha256"]!=hs["evidence_sha256"]:
            raise ValueError("A/B source evidence is not equal")
        item={
            "case_id":cid,
            "model_arm_order":list(order),
            "evidence_sha256":base["evidence_sha256"],
            "source_numeric_claim_ids":[x["claim_id"] for x in ledger["claims"] if x["case_id"]==cid],
            "arms":{},
        }
        record["cases"].append(item)
        for arm in order:
            context=base if arm=="plain" else hs
            result=diagnose(context,model=MODEL,inference=agy_chat,timeout_s=timeout_s)
            item["arms"][arm]=result
            tmp=out.with_suffix(out.suffix+".tmp")
            tmp.write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n")
            os.replace(tmp,out)
            plan=result.get("plan")
            print(json.dumps({
                "case":cid,"arm":arm,"status":result["status"],
                "seconds":result["elapsed_seconds"],
                "first_hypothesis":plan["hypotheses"][0]["mechanism"] if plan and plan["hypotheses"] else None,
                "next_check":plan["next_safe_check"] if plan else None,
            }),flush=True)
    record["complete"]=True
    tmp=out.with_suffix(out.suffix+".tmp")
    tmp.write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n")
    os.replace(tmp,out)
    return record

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--video-vtt",type=Path,required=True)
    parser.add_argument("--article-html",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--timeout",type=int,default=70)
    args=parser.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing to silently overwrite or reroll a source-locked model trial")
    data=run(video_vtt=args.video_vtt,article_html=args.article_html,
             out=args.out,timeout_s=args.timeout)
    print(json.dumps({
        "complete":data["complete"],
        "cases":len(data["cases"]),
        "clauses":data["numeric_source_validation"]["claim_count"],
        "source_graph_sha":data["real_HS_graph_sha256"],
    },indent=2))
if __name__=="__main__":main()
