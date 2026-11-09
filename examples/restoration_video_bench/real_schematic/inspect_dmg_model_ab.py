"""Offline audit of one frozen real-KiCad repair A/B, not a gold accuracy score."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from hardware_splicer.restoration_reasoning_agent import build_messages, sha
from hardware_splicer.restoration_schematic_grounding import (
    build_case_context, build_reference_tool_result,
)
from run_dmg_real_schematic_ab import ORDER, MODEL, protocol

HERE=Path(__file__).resolve().parent

def inspect(report: dict)->dict:
    if not report.get("complete") or report.get("protocol")!=protocol():
        raise ValueError("pilot incomplete or preregistration changed")
    if report.get("protocol_sha256")!=sha(protocol()):
        raise ValueError("trial protocol SHA invalid")
    expected_tool=build_reference_tool_result(reported_board_revision="DMG-CPU-06")
    if report["tool_result"]!=expected_tool:
        raise ValueError("real source-derived KiCad reference has changed")
    if report["real_reference_netlist_sha256"]!=expected_tool["reference_snapshot_sha256"]:
        raise ValueError("real KiCad snapshot sha mismatch")
    plain=build_case_context(reported_board_revision="DMG-CPU-06")
    hs=build_case_context(reported_board_revision="DMG-CPU-06",tool_reference=expected_tool)
    if plain["evidence_sha256"]!=hs["evidence_sha256"] or plain["evidence_sha256"]!=report["native_repair_intake_evidence_sha256"]:
        raise ValueError("model arms did not see exact same source symptoms")
    entries={}
    for name,context in (("plain",plain),("hs_real_kicad",hs)):
        r=report["arms"][name]
        digest=sha({k:v for k,v in r.items() if k not in ("receipt_sha256","elapsed_seconds")})
        if r["receipt_sha256"]!=digest:
            raise ValueError("model response was modified after being frozen")
        for key,expected in (
            ("evidence_sha256",context["evidence_sha256"]),
            ("prompt_sha256",sha(build_messages(context))),
            ("model_requested",MODEL),("model_reported",MODEL),
        ):
            if r.get(key)!=expected:
                raise ValueError(f"{name} source/model/prompt mismatch: {key}")
        if r["provider_reported"]!="agy_antigravity_subscription_cli":
            raise ValueError("not an actual Antigravity model inference receipt")
        if r["repair_authorized"] is not False or r["actual_video_frames_analyzed"] is not False:
            raise ValueError("false physical or video authority in model result")
        if name=="plain" and "real_schematic_tool_result_sha256" in r:
            raise ValueError("control received the real KiCad data")
        if name=="hs_real_kicad":
            if r["real_schematic_tool_result_sha256"]!=sha(expected_tool):
                raise ValueError("model's attached actual schematic tool changed")
            if r["target_board_physically_verified"] is not False:
                raise ValueError("reported board revision silently promoted to physical verification")
        p=r.get("plan")
        entries[name]={
            "status":r["status"],
            "first_hypothesis":p["hypotheses"][0]["mechanism"] if p and p["hypotheses"] else None,
            "next_safe_check":p["next_safe_check"] if p else None,
            "elapsed_seconds":r["elapsed_seconds"],
            "actual_pinout_verified_against_target":False,
        }
    return {
        "schema":"hs.restoration.real_kicad_pilot_no_gold_audit.v1",
        "source_reference_board":"DMG-CPU-06",
        "reported_target_board_only":True,
        "same_initial_evidence":True,
        "real_source_pinned":expected_tool["source_commit"],
        "source_netlist_sha256":expected_tool["reference_snapshot_sha256"],
        "board_variant_match_not_physically_verified":True,
        "creator_repair_accuracy_not_scored":True,
        "genuine_new_information":"Gekkio KiCad pin-to-net connectivity from actual exported reverse-engineered source",
        "results":entries,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--infile",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    summary=inspect(json.loads(args.infile.read_text()))
    args.out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(summary,indent=2,ensure_ascii=False))
if __name__=="__main__":main()
