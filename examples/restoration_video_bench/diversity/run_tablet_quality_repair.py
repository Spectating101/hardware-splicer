"""Real bounded source-only correction of the tablet's unsourced current cutoffs.

Uses the sealed HS-assisted first-window A/B response from PR #324, NOT
the post-outcome labels from a later branch. Preserves the invalid original
receipt and runs exactly ONE live Gemini correction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.restoration_caption_ingest import caption_case_context
from hardware_splicer.restoration_engineering_assist import add_engineering_assistance
from hardware_splicer.restoration_quality_correction import correct_unsourced_thresholds

D=Path(__file__).resolve().parent
CASE_ID="tab_s6_lite_dead"
FROZEN=D/"evidence/graph_ab_six_live.json"
CASES=D/"cases.json"

def run(*,caption_vtt:Path,timeout_s:int=65)->dict:
    c=next(x for x in json.loads(CASES.read_text())["cases"]
           if x["id"]==CASE_ID)
    if c["video_id"] not in caption_vtt.name:
        raise ValueError("caption file does not identify the sealed original video")
    receipt=json.loads(FROZEN.read_text())
    row=next(x for x in receipt["cases"] if x["case_id"]==CASE_ID)
    first=row["arms"]["hs_graph"]["receipt"]
    context=caption_case_context(
        case_id=c["id"],device=c["device"],
        title_symptom=c["title_symptom"],video_url=c["source_url"],
        hazards=c["hazards"],vtt_path=caption_vtt,cutoff_s=120,
    )
    enhanced=add_engineering_assistance(context)
    return correct_unsourced_thresholds(
        enhanced,first,model="gemini-3.8-flash-low",timeout_s=timeout_s,
    )

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--captions-vtt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():
        raise SystemExit("Refusing silent overwrite or multiple correction attempts")
    report=run(caption_vtt=a.captions_vtt)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    result=report["correction"]
    print(json.dumps({
        "original_unsupported_thresholds":[x["limit"] for x in report["original_violations"]],
        "correction_status":result["status"],
        "correction_model":result.get("model_reported"),
        "corrected_next_check":result.get("plan",{}).get("next_safe_check") if result.get("plan") else None,
        "correction_seconds":result["elapsed_seconds"],
        "original_receipt_sha256":report["original_receipt_sha256"],
    },indent=2))

if __name__=="__main__":main()
