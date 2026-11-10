"""One end-to-end, source-pinned HS Repair Investigator workflow.

Loads actual video auto captions and a real KiCad-derived source reference,
uses native HS repair_intake and engineering_source_graph, calls the same
model with and without actual source topology, and appends one pre-repair
video observation window to both arms.

No footage frames, independently observed measurements, physical board
identity, purchases, bench operation or final repair outcomes are assumed.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from .engineering_source_graph import build_engineering_source_graph
from .restoration_caption_ingest import caption_case_context
from .restoration_measurement_feedback import extend_caption_context
from .restoration_reasoning_agent import (
    agy_chat, build_messages, diagnose, sha,
)

SCHEMA="hs.repair_investigator.v1"
NET_SCHEMA="hs.circuit_kicad_reference_snapshot.v1"
HEX64=re.compile(r"^[a-f0-9]{64}$")
REFNETS=(
    "+5V","+12V","~{RESET}","/9VAC","/9VAC~",
    "PHI0","D0","/250407_sheet2/~{RAS}",
)
# We never pass the entire 250-net corpus to the model. The actual
# inspector and report retain all selected nets; the prompt provides a
# bounded, explicit subgraph of original KiCad pin claims.
TOP_REFS=frozenset({"SW1","F1","VR1","VR2","U7","U11","U12","U17","U19","U20","CN2","CN6"})

def file_sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_case(case_path:Path, *, captions_vtt:Path,
              schematic_checkout:Path|None=None)->tuple[dict[str,Any],dict[str,Any]]:
    manifest=json.loads(case_path.read_text(encoding="utf-8"))
    if manifest.get("schema")!="hs.restoration.investigator_case.v1":
        raise ValueError("unknown repair investigator case manifest")
    if manifest.get("video_frames_analyzed") is not False or manifest.get("no_creator_outcome_in_inputs") is not True:
        raise ValueError("case claims unavailable visual or post-outcome observation")
    if manifest.get("reference_board_photographed_and_independently_verified") is not False:
        raise ValueError("cannot certify physical PCB identity from a public video title")
    if manifest.get("physical_repairs_authorized") is not False:
        raise ValueError("a research demo may not authorize a physical repair")
    if captions_vtt.name!=manifest["captions_filename"]:
        raise ValueError("video auto-captions do not match expected source video ID")
    if file_sha256(captions_vtt)!=manifest["video_auto_captions_sha256"]:
        raise ValueError("source video captions changed after the initial experiment was frozen")
    if not manifest["video_url"].startswith("https://www.youtube.com/watch?v="):
        raise ValueError("source must be an exact video URL")
    if not (10<=manifest["opening_cutoff_seconds"]<manifest["inspection_cutoff_seconds"]<=600):
        raise ValueError("initial/follow-up source-window bounds invalid")
    snapshot_path=case_path.parent/manifest["source_reference_file"]
    if not HEX64.fullmatch(manifest["reference_snapshot_sha256"]):
        raise ValueError("reference snapshot SHA malformed")
    if file_sha256(snapshot_path)!=manifest["reference_snapshot_sha256"]:
        raise ValueError("source derived KiCad snapshot changed after registration")
    snap=json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snap.get("schema")!=NET_SCHEMA:
        raise ValueError("unknown netlist data format")
    if snap.get("physical_target_revision_verified") is not False:
        raise ValueError("physical board revision falsely marked as verified")
    if snap.get("board_replica_not_identical_to_all_original_revisions") is not True:
        raise ValueError("revision uncertainty lost")
    if snap.get("source_license")!="CERN-OHL-1.2":
        raise ValueError("upstream source attribution/licensing incomplete")
    if snap.get("full_netlist_component_count",0)<40 or snap.get("full_netlist_net_count",0)<30:
        raise ValueError("actual exported reference insufficient")
    refs=set()
    netnames=set()
    for n in snap["selected_nets"]:
        name=n.get("name")
        if not isinstance(name,str) or not name or name in netnames:
            raise ValueError("missing or duplicate KiCad net names")
        netnames.add(name)
        if not n.get("pins") or len(n["pins"])!=n["pin_count"]:
            raise ValueError("KiCad pin references missing or inconsistent")
        for node in n["pins"]:
            if not isinstance(node.get("ref"),str) or not isinstance(node.get("pin"),str):
                raise ValueError("net terminal not a physical KiCad reference")
            refs.add(node["ref"])
    comps={c["ref"] for c in snap["referenced_components"]}
    if not refs<=comps:
        raise ValueError("KiCad selected nets reference unknown parts")
    if not set(REFNETS)<=netnames:
        raise ValueError("key power, reset or memory nets absent")
    if schematic_checkout is not None:
        if schematic_checkout.is_symlink():
            raise ValueError("upstream checkout must be a concrete directory")
        head=subprocess.check_output(
            ["git","-C",str(schematic_checkout),"rev-parse","HEAD"],text=True,timeout=15
        ).strip()
        if head!=snap["source_commit"]:
            raise ValueError("upstream KiCad reference commit mismatch")
        for name,digest in snap["source_files"].items():
            source=schematic_checkout/name
            if source.is_symlink() or not source.is_file() or file_sha256(source)!=digest:
                raise ValueError("original KiCad source bytes failed checksum: "+name)
    return manifest,snap


def opening_context(manifest:Mapping[str,Any],*,captions_vtt:Path)->dict[str,Any]:
    context=caption_case_context(
        case_id=manifest["id"],device=manifest["device"],
        title_symptom=manifest["video_title_symptom"],
        video_url=manifest["video_url"],
        hazards=manifest["hazards"],
        vtt_path=captions_vtt,cutoff_s=manifest["opening_cutoff_seconds"],
    )
    if context["caption_provenance"]["raw_vtt_sha256"]!=manifest["video_auto_captions_sha256"]:
        raise ValueError("source digest changed between caption parser and source manifest")
    return context


def genuine_graph(context:Mapping[str,Any],snap:Mapping[str,Any])->dict[str,Any]:
    claims=[{
        "claim_id":e["id"],
        "subject_id":context["case_id"],
        "predicate":"source_reported_video_opening",
        "value":e["text"],"authority":"declared",
        "evidence_locator":{"source_stage":e["stage"],"evidence_id":e["id"]},
        "metadata":{"caption_is_auto_generated":True,"independent_video_frame_reading":False},
    } for e in context["evidence"]]
    nets=[{
        "claim_id":f"N{index+1}",
        "subject_id":f'{snap["board_design_id"]}::{net["name"]}',
        "predicate":"kicad_reference_net_connectivity",
        "value":{"net":net["name"],"pins":net["pins"],"pin_count":net["pin_count"]},
        "authority":"declared",
        "evidence_locator":{"net_name":net["name"],"source_sha256":snap["source_files"]["250407_.kicad_sch"]},
        "metadata":{"reference_board_only":True,"actual_target_verified":False},
    } for index,net in enumerate(snap["selected_nets"])]
    return_graph=build_engineering_source_graph([
        {
            "source_id":"c64-opening-captions",
            "source_type":"video",
            "uri":context["source_url"],
            "content_hash":"sha256:"+context["caption_provenance"]["raw_vtt_sha256"],
            "authority_ceiling":"declared","claims":claims,
        },
        {
            "source_id":"c64-kicad-reference",
            "source_type":"schematic",
            "uri":snap["source_repository"]+"/tree/"+snap["source_commit"],
            "content_hash":"sha256:"+snap["source_files"]["250407_.kicad_sch"],
            "authority_ceiling":"declared","claims":nets,
        },
    ],unresolved_source_ids=[
        "physical_board_revision_unverified",
        "replica_schematic_pin_mapping_not_independently_authenticated",
        "kicad_source_has_annotation_warnings",
        "no_independent_voltage_or_logic_analyzer_measurements",
        "no_component_datasheet_provided",
        "no_verified_meter_observations",
    ])
    if len(return_graph.claims)!=len(claims)+len(nets):
        raise ValueError("source graph lost a video or schematic claim")
    if any(c.authority.value!="declared" for c in return_graph.claims):
        raise ValueError("source graph falsely promoted claims to verified")
    return {
        "schema":"hs.repair_investigator.reference_graph.v1",
        "native_source_graph_sha256":sha(return_graph.model_dump(mode="json")),
        "native_source_graph_schema":return_graph.schema_version,
        "video_claim_ids":[c["claim_id"] for c in claims],
        "schematic_claim_ids":[c["claim_id"] for c in nets],
        "source_claim_authority":"declared",
        "source_code_commit":snap["source_commit"],
        "source_license":snap["source_license"],
        "video_source_sha256":context["caption_provenance"]["raw_vtt_sha256"],
        "schematic_source_sha256":snap["source_files"]["250407_.kicad_sch"],
        "unresolved_source_ids":return_graph.unresolved_source_ids,
        "target_board_physically_verified":False,
        "source_graph_does_not_validate_hardware":True,
    }


def schematic_context(plain:Mapping[str,Any],snap:Mapping[str,Any])->dict[str,Any]:
    updated=deepcopy(dict(plain))
    graph=genuine_graph(updated,snap)
    prompt_nets=[]
    for net in snap["selected_nets"]:
        if net["name"] not in REFNETS:
            continue
        eligible=[n for n in net["pins"] if n["ref"] in TOP_REFS]
        prompt_nets.append({
            "name":net["name"],
            "actual_net_total_pins":net["pin_count"],
            "shown_terminal_subset":eligible[:12],
            "subset_is_not_complete":len(eligible[:12])!=net["pin_count"],
        })
    updated["investigator_reference"]={
        "schema":"hs.repair_investigator.reference_tool.v1",
        "case_id":updated["case_id"],
        "source_commit":snap["source_commit"],
        "source_repository":snap["source_repository"],
        "source_license":snap["source_license"],
        "reference_board":snap["board_design_id"],
        "physical_target_revision_verified":False,
        "different_historical_board_revisions_exist":True,
        "kicad_annotation_warnings":True,
        "source_snapshot_sha256":sha(snap),
        "source_graph_sha256":graph["native_source_graph_sha256"],
        "source_claims":graph["schematic_claim_ids"],
        "reference_nets":prompt_nets,
        "all_selected_net_names":[n["name"] for n in snap["selected_nets"]],
        "unresolved_source_ids":graph["unresolved_source_ids"],
        "repair_authorized":False,
        "verified_external_measurements":False,
        "manufacturer_specifications_verified":False,
    }
    if updated["evidence_sha256"]!=plain["evidence_sha256"]:
        raise ValueError("engineering evidence cannot edit original video symptom text")
    return updated


def perform(
    manifest:Mapping[str,Any],snap:Mapping[str,Any],*,captions_vtt:Path,
    inference:Callable[...,dict[str,Any]]=agy_chat,
    model:str="gemini-3.8-flash-low",timeout_s:int=70,
    on_step:Callable[[dict[str,Any]],None]|None=None
)->dict[str,Any]:
    """Execute two arms over two timestamped stages, preserving failed calls.

    One callable can be mocked in deterministic CI; genuine default uses
    authorized Antigravity subscription and has no paid API fallback.
    """
    opening=opening_context(manifest,captions_vtt=captions_vtt)
    graph=genuine_graph(opening,snap)
    arms={
        "plain":{"context":opening,"turns":[]},
        "hs_circuit":{"context":schematic_context(opening,snap),"turns":[]},
    }
    record={
        "schema":SCHEMA,
        "protocol":{
            "case_id":manifest["id"],
            "source_url":manifest["video_url"],
            "source_cutoffs":[manifest["opening_cutoff_seconds"],manifest["inspection_cutoff_seconds"]],
            "model":model,
            "arm_order_by_stage":[["plain","hs_circuit"],["hs_circuit","plain"]],
            "source_outcome_not_passed":True,
            "same_raw_video_evidence":True,
            "physical_board_verified":False,
            "no_external_tools_or_power_authorized":True,
            "data_modes":"opening auto-caption, later pre-repair visual-inspection narration; no video frames",
        },
        "source_manifest_sha256":sha(manifest),
        "source_snapshot_sha256":sha(snap),
        "video_source_sha256":manifest["video_auto_captions_sha256"],
        "native_graph":graph,
        "results":{"plain":[],"hs_circuit":[]},
        "complete":False,
    }
    # Prediction sequence is explicit and precommitted rather than
    # alternating until one model gives a preferred fault prediction.
    for stage,order in enumerate(record["protocol"]["arm_order_by_stage"]):
        for arm_name in order:
            state=arms[arm_name]
            context=state["context"]
            if stage==1:
                old=state["turns"][-1]
                # Fail gracefully: no results or rewritten hypotheses after
                # an unavailable initial inference. The report records this.
                if old["status"] not in ("proposed_unverified_differential","model_abstained"):
                    row={"stage":stage,"status":"blocked_by_invalid_preceding_model",
                         "previous_receipt_sha256":old["receipt_sha256"]}
                    record["results"][arm_name].append(row)
                    if on_step:on_step(record)
                    continue
                context=extend_caption_context(
                    context,old,vtt_path=captions_vtt,
                    start_s=manifest["opening_cutoff_seconds"],
                    cutoff_s=manifest["inspection_cutoff_seconds"],
                )
            receipt=diagnose(context,inference=inference,model=model,timeout_s=timeout_s)
            state["turns"].append(receipt)
            state["context"]=context
            record["results"][arm_name].append({
                "stage":stage,
                "evidence_sha256":context["evidence_sha256"],
                "evidence":context["evidence"],
                "new_video_observations":len(context["evidence"])-len(opening["evidence"]),
                "model_receipt":receipt,
            })
            if on_step:on_step(record)
    record["complete"]=True
    return record
