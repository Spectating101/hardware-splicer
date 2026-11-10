"""Real C64 KiCad provenance and one continuous two-stage investigator workflow.

The local raw caption and original upstream files are deliberately not
redistributed in GitHub. CI exercises a synthetic VTT over the SAME
production flow; Optiplex separately verifies the actual source hashes.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.repair_investigator import (
    REFNETS,file_sha256,genuine_graph,load_case,opening_context,
    perform,schematic_context,
)
from hardware_splicer.restoration_reasoning_agent import (
    build_messages,diagnose,validate_model_output,sha,
)

HERE=Path(__file__).resolve().parents[1]/"examples/restoration_video_bench/investigator/c64_250407"
SOURCE=Path("/tmp/hs-source-c64-250407")
CAP=Path("/tmp/hs-c64-video-unseen-20261110/mkGEXlQ84wk.en-orig.vtt")

def fixture(tmp_path):
    raw="""WEBVTT

00:00:02.000 --> 00:00:02.010
This C64 does not work and has previous repair work.

00:00:45.000 --> 00:00:45.010
Some important chips appear to be missing.

00:02:04.000 --> 00:02:04.010
There is a strange power switch on the circuit board.

00:03:18.000 --> 00:03:18.010
The previous solder joints do not look good.

00:12:55.000 --> 00:12:55.010
The power supply voltage is twelve volts.

00:28:45.000 --> 00:28:45.010
The repairs restored the screen.
"""
    p=tmp_path/"mkGEXlQ84wk.en-orig.vtt"
    p.write_text(raw)
    m=json.loads((HERE/"case.json").read_text())
    m["video_auto_captions_sha256"]=hashlib.sha256(raw.encode()).hexdigest()
    snap=json.loads((HERE/"c64_250407_reference.json").read_text())
    return m,snap,p

def fake_model(messages, **kwargs):
    body=json.loads(next(x["content"] for x in messages if x["role"]=="user"))
    assisted="REAL_ENGINEERING_TOOL=" in messages[0]["content"]
    evid=body["evidence"]
    if len(evid)>7:
        hypothesis="Possible damaged rework around an electrical connector"
    else:
        hypothesis="Possible supply rail or power switch fault"
    return {
        "provider":"mock_no_physical_access","model":kwargs.get("model","test_model"),
        "content":json.dumps({
            "summary":"No fault is yet confirmed by a measured instrument.",
            "hypotheses":[{
                "mechanism":hypothesis,
                "why":"Source schematic mentions +5V and ~{RESET} as circuit references; "
                      "the actual board layout is not physically authenticated."
                      if assisted else "The video describes a nonworking board.",
                "evidence_ids":["E1"],
                "safe_test":"Request close-up photos of the board revision and any altered solder joints, with power removed."
            }],
            "next_safe_check":"Confirm the board silkscreen revision and inspect visibly damaged connections with all power removed.",
            "uncertainty":"No independently measured voltages; schematic is replica reference only.",
            "abstain":False,
        })
    }

def test_real_reference_has_nonfabricated_multi_domain_circuit_nodes():
    snap=json.loads((HERE/"c64_250407_reference.json").read_text())
    names={n["name"] for n in snap["selected_nets"]}
    assert set(REFNETS)<=names
    assert snap["full_netlist_net_count"]==250
    assert snap["full_netlist_component_count"]==230
    assert len(names)==17
    assert snap["source_commit"]=="9bf17bb868248b12fb12210d66be3a37ec4ab832"
    assert snap["source_license"]=="CERN-OHL-1.2"
    assert snap["physical_target_revision_verified"] is False
    assert "annotation errors" in snap["kicad_export_warning"]
    name={n["name"]:n for n in snap["selected_nets"]}
    assert {"ref":"U7","pin":"6"} in name["+5V"]["pins"]
    assert {"ref":"U7","pin":"40"} in name["~{RESET}"]["pins"]
    assert {"ref":"U7","pin":"1"} in name["PHI0"]["pins"]

def test_real_video_and_upstream_artifacts_match_pinned_sha_if_locally_present():
    if not CAP.is_file() or not SOURCE.is_dir():
        pytest.skip("real external source bytes deliberately omitted in GitHub CI")
    manifest,snap=load_case(HERE/"case.json",captions_vtt=CAP,schematic_checkout=SOURCE)
    assert snap["source_repository"].startswith("https://github.com/bwack")
    opening=opening_context(manifest,captions_vtt=CAP)
    assert len(opening["evidence"])==7
    assert opening["caption_provenance"]["total_early_final_cues"]==45
    assert "Bad RAM" not in str(build_messages(opening))
    assert opening["caption_provenance"]["no_video_frames"]

def test_tampered_video_and_source_snapshot_rejected(tmp_path):
    m,s,p=fixture(tmp_path)
    src=tmp_path/"case"
    src.mkdir()
    (src/"case.json").write_text(json.dumps(m))
    shutil_ref=HERE/"c64_250407_reference.json"
    (src/"c64_250407_reference.json").write_bytes(shutil_ref.read_bytes())
    load_case(src/"case.json",captions_vtt=p)
    p.write_text(p.read_text()+"\n")
    with pytest.raises(ValueError,match="captions changed"):
        load_case(src/"case.json",captions_vtt=p)
    p.write_text("""WEBVTT

00:00:02.000 --> 00:00:02.010
This C64 does not work and has previous repair work.
""")
    m["video_auto_captions_sha256"]=file_sha256(p)
    (src/"case.json").write_text(json.dumps(m))
    (src/"c64_250407_reference.json").write_text(shutil_ref.read_text()+" ")
    with pytest.raises(ValueError,match="KiCad snapshot changed"):
        load_case(src/"case.json",captions_vtt=p)

def test_source_board_applicability_must_remain_unverified(tmp_path):
    m,s,p=fixture(tmp_path)
    s["physical_target_revision_verified"]=True
    d=tmp_path/"case"
    d.mkdir()
    raw=(json.dumps(s,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode()
    (d/"c64_250407_reference.json").write_bytes(raw)
    m["reference_snapshot_sha256"]=hashlib.sha256(raw).hexdigest()
    (d/"case.json").write_text(json.dumps(m))
    with pytest.raises(ValueError,match="falsely marked as verified"):
        load_case(d/"case.json",captions_vtt=p)

def test_actual_native_source_graph_was_called_with_separate_evidence(tmp_path):
    m,s,p=fixture(tmp_path)
    ctx=opening_context(m,captions_vtt=p)
    graph=genuine_graph(ctx,s)
    assert graph["native_source_graph_schema"]=="hardware_splicer.engineering_source_graph.v1"
    assert len(graph["video_claim_ids"])==len(ctx["evidence"])
    assert len(graph["schematic_claim_ids"])==17
    assert graph["source_claim_authority"]=="declared"
    assert graph["target_board_physically_verified"] is False
    assert "kicad_source_has_annotation_warnings" in graph["unresolved_source_ids"]

def test_model_evidence_identical_plain_and_hs(tmp_path):
    m,s,p=fixture(tmp_path)
    ctx=opening_context(m,captions_vtt=p)
    enhanced=schematic_context(ctx,s)
    assert ctx["evidence"]==enhanced["evidence"]
    assert ctx["evidence_sha256"]==enhanced["evidence_sha256"]
    plain,with_tool=build_messages(ctx),build_messages(enhanced)
    assert plain[1]==with_tool[1]
    assert plain[0]!=with_tool[0]
    assert "REAL_ENGINEERING_TOOL=" in with_tool[0]["content"]
    assert "source_commit" in with_tool[0]["content"]
    assert len(enhanced["investigator_reference"]["reference_nets"])==len(REFNETS)

def test_unverified_board_pin_test_and_invented_voltage_fail_closed(tmp_path):
    m,s,p=fixture(tmp_path)
    ctx=schematic_context(opening_context(m,captions_vtt=p),s)
    candidate=json.loads(fake_model(build_messages(ctx),model="test_model")["content"])
    candidate["next_safe_check"]="Measure U7 pin 6 to confirm the CPU rail."
    from hardware_splicer.restoration_board_action_gate import UnverifiedBoardPinAction
    with pytest.raises(UnverifiedBoardPinAction):
        validate_model_output(candidate,ctx)
    candidate["next_safe_check"]="Conclude healthy if voltage is above 5.3V."
    from hardware_splicer.restoration_numeric_truth_gate import UnsupportedQuantitativeThreshold
    with pytest.raises(UnsupportedQuantitativeThreshold):
        validate_model_output(candidate,ctx)

def test_integrated_mock_two_stage_workflow_preserves_all_receipts(tmp_path):
    m,s,p=fixture(tmp_path)
    calls=[]
    def model(msg,**kwargs):
        calls.append((msg,kwargs))
        return fake_model(msg,**kwargs)
    steps=[]
    result=perform(m,s,captions_vtt=p,inference=model,model="test_model",
                   on_step=lambda state: steps.append(
                       sum(len(v) for v in state["results"].values())
                   ))
    assert result["complete"] is True
    assert calls and len(calls)==4
    assert steps==[1,2,3,4]
    assert result["protocol"]["arm_order_by_stage"]==[
        ["plain","hs_circuit"],["hs_circuit","plain"],
    ]
    assert result["protocol"]["source_outcome_not_passed"]
    for arm in ("plain","hs_circuit"):
        rows=result["results"][arm]
        assert len(rows)==2
        assert rows[0]["model_receipt"]["status"]=="proposed_unverified_differential"
        assert rows[1]["model_receipt"]["status"]=="proposed_unverified_differential"
        assert rows[1]["model_receipt"]["preceding_receipt_sha256"]==rows[0]["model_receipt"]["receipt_sha256"]
        assert rows[0]["evidence_sha256"]!=rows[1]["evidence_sha256"]
        assert "repairs restored the screen" not in json.dumps(rows)
        assert rows[1]["new_video_observations"]>0
        for row in rows:
            receipt=row["model_receipt"]
            assert receipt["repair_authorized"] is False
            assert receipt["actual_video_frames_analyzed"] is False
            assert receipt["physical_measurements_by_HS"] is False
            assert receipt["receipt_sha256"]==sha({
                k:v for k,v in receipt.items()
                if k not in ("receipt_sha256","elapsed_seconds")
            })
    assert (result["results"]["plain"][1]["evidence_sha256"]==
            result["results"]["hs_circuit"][1]["evidence_sha256"])
    assert "source" in result["native_graph"]["source_license"].lower() or result["native_graph"]["source_license"]=="CERN-OHL-1.2"

def test_invalid_parent_diagnosis_blocks_followup_without_fake_success(tmp_path):
    m,s,p=fixture(tmp_path)
    def bad(msg,**kwargs):
        if "REAL_ENGINEERING_TOOL" in msg[0]["content"]:
            return {"provider":"test","model":"fake","content":"bad json"}
        return fake_model(msg,**kwargs)
    result=perform(m,s,captions_vtt=p,inference=bad,model="test_model")
    assert result["complete"]
    assert result["results"]["hs_circuit"][0]["model_receipt"]["status"]=="rejected_model_output_or_unavailable"
    assert result["results"]["hs_circuit"][1]["status"]=="blocked_by_invalid_preceding_model"
    assert result["results"]["hs_circuit"][1]["previous_receipt_sha256"]
