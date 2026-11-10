"""Run one real HS Repair Investigator protocol with pinned external sources.

Creates sealed inference results first. Later report rendering reads only
the already frozen results. It has no creator outcome scoring or repair
actions and never auto-rerolls a failed Gemini call.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from hardware_splicer.repair_investigator import file_sha256,load_case,perform

HERE=Path(__file__).resolve().parent
CASE=HERE/"c64_250407/case.json"

def main():
    p=argparse.ArgumentParser(description="Run one repair video against plain and HS-reference diagnostic arms")
    p.add_argument("--case",type=Path,default=CASE)
    p.add_argument("--captions-vtt",type=Path,required=True)
    p.add_argument("--schematic-checkout",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=70)
    args=p.parse_args()
    if args.out.exists():
        raise SystemExit("The output already exists. Refusing to reroll a frozen model experiment.")
    manifest,snapshot=load_case(args.case,captions_vtt=args.captions_vtt,
                                schematic_checkout=args.schematic_checkout)
    def checkpoint(state):
        tmp=args.out.with_name(args.out.name+".tmp")
        tmp.parent.mkdir(parents=True,exist_ok=True)
        tmp.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n")
        os.replace(tmp,args.out)
        for arm in ("plain","hs_circuit"):
            if not state["results"][arm]:
                continue
            row=state["results"][arm][-1]
            receipt=row.get("model_receipt")
            if receipt:
                print(json.dumps({
                    "arm":arm,"stage":row["stage"],"status":receipt["status"],
                    "model":receipt.get("model_reported"),
                    "seconds":receipt.get("elapsed_seconds"),
                    "top_fault":(
                        receipt["plan"]["hypotheses"][0]["mechanism"]
                        if receipt.get("plan") and receipt["plan"]["hypotheses"]
                        else None
                    ),
                }),flush=True)
    result=perform(manifest,snapshot,captions_vtt=args.captions_vtt,
                   timeout_s=args.timeout,on_step=checkpoint)
    checkpoint(result)
    print(json.dumps({"complete":result["complete"],
        "case":manifest["id"],"actual_source_video":manifest["video_url"],
        "original_schematic_commit":snapshot["source_commit"],
        "source_graph_sha256":result["native_graph"]["native_source_graph_sha256"],
        "source_verified_board":False,
    },indent=2))
if __name__=="__main__":
    main()
