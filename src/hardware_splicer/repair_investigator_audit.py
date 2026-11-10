"""Offline reconstruction of exact HS Repair Investigator model prompts.

Does not need private captions, video frames, provider access or creator
outcome files: every actual E evidence row is preserved in the frozen
receipt. Verifies original source manifest hashes and complete model-turn
chains including the generated source-backed system prompt.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any,Mapping

from .repair_investigator import genuine_graph,schematic_context
from .restoration_reasoning_agent import SCHEMA as DIAG_SCHEMA, build_messages,sha

VALID=("proposed_unverified_differential","model_abstained")
ORDER=[["plain","hs_circuit"],["hs_circuit","plain"]]


def verify_investigation(
    report:Mapping[str,Any],manifest:Mapping[str,Any],snap:Mapping[str,Any]
)->dict[str,Any]:
    if report.get("schema")!="hs.repair_investigator.v1" or not report.get("complete"):
        raise ValueError("unsealed or incomplete investigator execution")
    protocol=report["protocol"]
    if protocol["case_id"]!=manifest["id"] or protocol["source_url"]!=manifest["video_url"]:
        raise ValueError("case source changed")
    if protocol["source_cutoffs"]!=[manifest["opening_cutoff_seconds"],manifest["inspection_cutoff_seconds"]]:
        raise ValueError("source time gates changed")
    if protocol["arm_order_by_stage"]!=ORDER:
        raise ValueError("model call order changed after registration")
    if report["source_manifest_sha256"]!=sha(manifest) or report["source_snapshot_sha256"]!=sha(snap):
        raise ValueError("pinned external source hashes differ from model receipts")
    if report["video_source_sha256"]!=manifest["video_auto_captions_sha256"]:
        raise ValueError("video auto-caption hash changed")
    results=report["results"]
    if set(results)!={"plain","hs_circuit"}:
        raise ValueError("matched-control model arms missing or altered")
    all_turns=[]
    initial_source_sha=None
    for arm in ("plain","hs_circuit"):
        rows=results[arm]
        if len(rows)!=2:
            raise ValueError("each model must have two attempt records")
        previous=None
        base=None
        for stage,row in enumerate(rows):
            if row.get("stage")!=stage:
                raise ValueError("video evidence stage out of order")
            if row.get("status")=="blocked_by_invalid_preceding_model":
                if stage!=1 or not previous or previous["status"] in VALID:
                    raise ValueError("invalid model block is fabricated")
                if row["previous_receipt_sha256"]!=previous["receipt_sha256"]:
                    raise ValueError("blocked step references wrong previous receipt")
                continue
            if "model_receipt" not in row:
                raise ValueError("missing real attempted inference")
            rec=row["model_receipt"]
            if rec.get("schema")!=DIAG_SCHEMA or rec.get("case_id")!=manifest["id"]:
                raise ValueError("receipt wrong schema or device")
            if rec.get("source_url")!=manifest["video_url"]:
                raise ValueError("receipt source URL changed")
            if rec.get("evidence_sha256")!=sha(row["evidence"]) or row["evidence_sha256"]!=rec["evidence_sha256"]:
                raise ValueError("retained evidence differs from signed model input")
            digest=sha({k:v for k,v in rec.items() if k not in ("receipt_sha256","elapsed_seconds")})
            if digest!=rec.get("receipt_sha256"):
                raise ValueError("model receipt digest mismatch")
            if any(rec.get(k) is not False for k in (
                "repair_authorized","physical_measurements_by_HS",
                "actual_video_frames_analyzed","device_repaired_by_HS"
            )):
                raise ValueError("model falsely claims physical action or visual observation")
            if rec.get("model_requested")!=protocol["model"]:
                raise ValueError("model changed during matched trial")
            if stage==0:
                base={
                    "schema":DIAG_SCHEMA,"case_id":manifest["id"],"device":manifest["device"],
                    "source_url":manifest["video_url"],"hazards":manifest["hazards"],
                    "evidence_stage":f'auto_vtt_first_{manifest["opening_cutoff_seconds"]}s',
                    "preceding_receipt_sha256":None,
                    "native_HS_repair_intake_schema":"hardware_splicer.repair_intake.v1",
                    "evidence":row["evidence"],"evidence_sha256":rec["evidence_sha256"],
                    "caption_provenance":rec["caption_provenance"],
                    "repair_authorized":False,
                }
                if arm=="hs_circuit":
                    base=schematic_context(base,snap)
                if initial_source_sha is None:
                    initial_source_sha=rec["evidence_sha256"]
                elif rec["evidence_sha256"]!=initial_source_sha:
                    raise ValueError("plain and tool arms received different opening source evidence")
                ctx=base
                if row["new_video_observations"]!=0:
                    raise ValueError("opening stage includes later video outcome")
            else:
                if not previous or previous["status"] not in VALID:
                    raise ValueError("follow-up lacks valid model parent")
                if rec["preceding_receipt_sha256"]!=previous["receipt_sha256"]:
                    raise ValueError("follow-up prediction is not hash chained to earlier one")
                ctx=deepcopy(base)
                ctx["evidence"]=row["evidence"]
                ctx["evidence_sha256"]=rec["evidence_sha256"]
                ctx["preceding_receipt_sha256"]=previous["receipt_sha256"]
                ctx["prior_model_hypotheses"]=[
                    str(h["mechanism"])[:200] for h in previous["plan"]["hypotheses"]
                ]
                ctx["evidence_stage"]=f'video_caption_until_{manifest["inspection_cutoff_seconds"]}s'
                ctx["source_windows"]=rec.get("source_windows")
                if not ctx["source_windows"] or ctx["source_windows"][-1]["cutoff_second"]!=manifest["inspection_cutoff_seconds"]:
                    raise ValueError("missing or wrong followup time gate")
                if ctx["source_windows"][0]["cutoff_second"]!=manifest["opening_cutoff_seconds"]:
                    raise ValueError("followup omitted original video window")
                if ctx["source_windows"][1]["start_second"]!=manifest["opening_cutoff_seconds"]:
                    raise ValueError("noncontiguous video evidence source")
                if row["evidence"][:len(base["evidence"])]!=base["evidence"]:
                    raise ValueError("later model evidence rewrote opening observations")
                if row["new_video_observations"]!=len(row["evidence"])-len(base["evidence"]):
                    raise ValueError("follow-up observation count inaccurate")
            if sha(build_messages(ctx))!=rec["prompt_sha256"]:
                raise ValueError("model system prompt / source tool not reconstructable")
            if arm=="hs_circuit":
                if rec["investigator_reference_sha256"]!=sha(ctx["investigator_reference"]):
                    raise ValueError("real circuit tool was swapped after model inference")
                if rec["investigator_source_graph_sha256"]!=report["native_graph"]["native_source_graph_sha256"] and stage==0:
                    raise ValueError("initial circuit graph was changed")
                if rec.get("target_board_physically_verified") is not False:
                    raise ValueError("actual board revision was not physically confirmed")
            else:
                if "investigator_reference_sha256" in rec:
                    raise ValueError("control arm contaminated with the engineering source tool")
            all_turns.append({"arm":arm,"stage":stage,"status":rec["status"],
                              "sha256":rec["receipt_sha256"],
                              "first_hypothesis":(
                                  rec["plan"]["hypotheses"][0]["mechanism"]
                                  if rec.get("plan") and rec["plan"]["hypotheses"] else None
                              ),"seconds":rec.get("elapsed_seconds")})
            previous=rec
    reference_graph=genuine_graph({
        "case_id":manifest["id"],"source_url":manifest["video_url"],
        "caption_provenance":{"raw_vtt_sha256":manifest["video_auto_captions_sha256"]},
        "evidence":results["plain"][0]["evidence"],
    },snap)
    if report["native_graph"]!=reference_graph:
        raise ValueError("native HS engineering graph changed after model prediction")
    return {
        "schema":"hs.repair_investigator.offline_integrity_audit.v1",
        "case_id":manifest["id"],
        "board_source_commit":snap["source_commit"],
        "video_raw_vtt_sha256":manifest["video_auto_captions_sha256"],
        "source_graph_sha256":reference_graph["native_source_graph_sha256"],
        "model_attempts":len(all_turns),
        "valid_by_arm":{arm:sum(x["arm"]==arm and x["status"] in VALID for x in all_turns)
                        for arm in ("plain","hs_circuit")},
        "no_independent_physical_measurements":True,
        "no_video_frame_vision":True,
        "board_revision_not_verified":True,
        "no_repair_success_or_accuracy_scored":True,
        "results":all_turns,
    }
