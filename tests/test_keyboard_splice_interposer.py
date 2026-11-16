"""Native KiCad evidence: distinct bridge channels and DRC cannot grant physical approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

REPO=Path(__file__).resolve().parents[1]
HELPER=REPO / "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_interposer.py"
SYSTEM="/usr/bin/python3"


def native_ready():
    try:
        proc=subprocess.run([SYSTEM,"-c","import pcbnew"],capture_output=True,timeout=10)
        return proc.returncode==0 and bool(shutil.which("kicad-cli"))
    except (OSError,subprocess.TimeoutExpired):
        return False


pytestmark=pytest.mark.skipif(not native_ready(),reason="native KiCad pcbnew/CLI absent")


def sample_topology():
    edges=[]
    for i,net in enumerate(["row1","row1","col2"],1):
        edges.append({
            "net":net,
            "from_island":f"{net}-source-{i}",
            "to_island":f"{net}-target-{i}",
            "from_candidate_pad":{"ref":f"S{i}","pad":"1","net":net,"x":3,"y":i},
            "to_candidate_pad":{"ref":f"D{i}","pad":"2","net":net,"x":70,"y":i},
            "status":"PROPOSED_MODEL_ONLY_NOT_A_WIRING_AUTHORIZATION",
        })
    result={
        "source_sha256":"c"*64,
        "qualified_for_build":False,
        "release":"BLOCKED_REFERENCE_TOPOLOGY_ONLY",
        "candidate_graph_edges":3,
        "model_replay_remaining_split_components":0,
        "unanchored_split_components":0,
        "bridge_edges":edges,
    }
    result["payload_sha256"]=hashlib.sha256(json.dumps(
        result,sort_keys=True,ensure_ascii=False,separators=(",",":")
    ).encode()).hexdigest()
    return result


def run_generator(tmp_path,body):
    source=tmp_path/"topology.json"
    output=tmp_path/"interposer"
    source.write_text(json.dumps(body),encoding="utf-8")
    proc=subprocess.run([SYSTEM,str(HELPER),"--topology-json",str(source),
                         "--out",str(output)],capture_output=True,text=True,timeout=35)
    return proc,output


def test_edi_board_is_real_kicad_file_and_drc_clean_but_release_blocked(tmp_path):
    process,out=run_generator(tmp_path,sample_topology())
    assert process.returncode==0,process.stderr
    board=out/"reference_bridge_interposer.kicad_pcb"
    assert board.is_file() and board.stat().st_size>1000
    manifest=json.loads((out/"INTERPOSER_CHANNEL_MAP.json").read_text())
    assert manifest["channel_count"]==3
    assert manifest["physical_authority_granted"] is False
    assert manifest["connector_mpn"] is None
    assert not manifest["connector_mating_verified"]
    assert not manifest["cable_pinout_verified"]
    assert not manifest["assembly_bom_complete"]
    assert manifest["fabrication_release"]=="BLOCKED_PREVIEW_ONLY"
    # Two separate rows carrying the same original source net must remain
    # electrically distinct and not acquire a phantom common copper path.
    row1=[r for r in manifest["channel_mapping"] if r["source_net"]=="row1"]
    assert len(row1)==2 and len({r["pcb_net"] for r in row1})==2
    native=subprocess.run(["kicad-cli","pcb","drc","--format","json",
         "--output",str(out/"DRC.json"),str(board)],capture_output=True,text=True,timeout=60)
    assert native.returncode==0,native.stdout+native.stderr
    report=json.loads((out/"DRC.json").read_text())
    assert not report.get("violations")
    assert not report.get("unconnected_items")
    check=subprocess.run([SYSTEM,"-c",(
        "import pcbnew as p,json,sys;"
        "b=p.LoadBoard(sys.argv[1]);"
        "print(json.dumps({'footprints':len(b.GetFootprints()),"
        "'tracks':len(b.GetTracks()),"
        "'pads':sum(len(list(f.Pads())) for f in b.GetFootprints())}))"
    ),str(board)],capture_output=True,text=True,timeout=30)
    assert check.returncode==0,check.stderr
    measured=json.loads(check.stdout)
    assert measured=={"footprints":2,"tracks":3,"pads":6}


@pytest.mark.parametrize("change",["unapproved","wrong_net","tampered_hash","approved"])
def test_interposer_rejects_unproven_or_cross_net_instructions(tmp_path,change):
    body=sample_topology()
    if change=="unapproved":
        body["bridge_edges"][0]["status"]="AUTHORIZED"
    elif change=="wrong_net":
        body["bridge_edges"][0]["to_candidate_pad"]["net"]="col4"
    elif change=="approved":
        body["qualified_for_build"]=True
    else:
        body["candidate_graph_edges"]=4
    if change!="tampered_hash":
        body.pop("payload_sha256")
        body["payload_sha256"]=hashlib.sha256(json.dumps(
            body,sort_keys=True,ensure_ascii=False,separators=(",",":")
        ).encode()).hexdigest()
    proc,_=run_generator(tmp_path,body)
    assert proc.returncode!=0
