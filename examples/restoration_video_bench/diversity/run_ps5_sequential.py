"""PS5 sequential caption diagnostic trial with actual AGY inference.

One prior model receipt was committed in PR #322 before these later video
segments were processed. We admit only 120-300 and 300-360 seconds, before
the creator's confirmed component removal/replacement.

No creator postreview JSON, root-cause label, repair-success transcript, or
later diagnosis is imported by this runner.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from hardware_splicer.restoration_caption_ingest import caption_case_context
from hardware_splicer.restoration_measurement_feedback import extend_caption_context, validate_predecessor
from hardware_splicer.restoration_reasoning_agent import agy_chat, diagnose

D = Path(__file__).resolve().parent
VIDEO_ID="xbp8lIggbxY"
CASE_ID="ps5_pro_no_power_hdmi"
INITIAL_RECEIPT=D/"evidence/live_raw_vtt/ps5_pro_no_power_hdmi.json"
MANIFEST=D/"cases.json"


def run(*, captions:Path, timeout_s:int = 60, model:str="gemini-3.8-flash-low")->dict:
    if VIDEO_ID not in captions.name:
        raise ValueError("cannot replace the sealed PS5 video with a different source")
    cases=json.loads(MANIFEST.read_text())["cases"]
    case=next(x for x in cases if x["id"]==CASE_ID)
    previous=json.loads(INITIAL_RECEIPT.read_text())["results"][0]
    if previous["case_id"]!=CASE_ID:
        raise ValueError("wrong original source receipt")
    context=caption_case_context(
        case_id=case["id"],device=case["device"],
        title_symptom=case["title_symptom"],video_url=case["source_url"],
        hazards=case["hazards"],vtt_path=captions,cutoff_s=120,
    )
    validate_predecessor(context,previous)
    results=[]
    for start,end in [(120,300),(300,360)]:
        next_context=extend_caption_context(
            context,previous,vtt_path=captions,start_s=start,cutoff_s=end
        )
        result=diagnose(next_context,inference=agy_chat,model=model,timeout_s=timeout_s)
        results.append({
            "window_start_s":start, "window_end_s":end,
            "new_evidence_ids":[e["id"] for e in next_context["evidence"][len(context["evidence"]):]],
            "receipt":result,
        })
        if result["status"] not in (
            "proposed_unverified_differential","model_abstained"
        ):
            break
        context,previous=next_context,result
    return {
        "schema":"hs.restoration.sequential_measurement_trial.v1",
        "case_id":CASE_ID,"video_id":VIDEO_ID,
        "previous_sealed_prediction_sha256":json.loads(INITIAL_RECEIPT.read_text())["results"][0]["receipt_sha256"],
        "provider":"agy_antigravity_subscription_cli",
        "model":model,
        "max_video_second_admitted":360,
        "source_kind":"unverified_creator_narration_from_timestamped_auto_captions",
        "no_post_repair_outcomes_opened":True,
        "independent_bench_measurements":False,
        "automatic_video_frame_analysis":False,
        "physical_repair_authorized":False,
        "turns":results,
    }


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--captions-vtt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--model",default="gemini-3.8-flash-low")
    p.add_argument("--timeout",type=int,default=60)
    a=p.parse_args()
    result=run(captions=a.captions_vtt,model=a.model,timeout_s=a.timeout)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    for stage in result["turns"]:
        plan=stage["receipt"].get("plan")
        first=(plan or {}).get("hypotheses") or []
        print(json.dumps({
            "video_window":[stage["window_start_s"],stage["window_end_s"]],
            "status":stage["receipt"]["status"],
            "first_ranked_mechanism":first[0]["mechanism"] if first else None,
            "elapsed_seconds":stage["receipt"]["elapsed_seconds"],
            "preceding_receipt_sha256":stage["receipt"]["preceding_receipt_sha256"],
        }))

if __name__=="__main__":
    main()
