"""End-to-end real KiCad 9 keypad source -> virtual split -> interposer PCB.

This is a simulated original 1x6 keypad with a 7-pin controller interface,
not a physically tested USB keyboard.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO=Path(__file__).resolve().parents[1]
FIXTURE=REPO/"examples/arbitrage_lab/keyboard_splice/reference_1x6"
SOURCE=FIXTURE/"one_row_six_key_source.kicad_pcb"
SYSTEM="/usr/bin/python3"


def topology_python():
    if not shutil.which("kicad-cli"):
        return ""
    try:
        native=subprocess.run([SYSTEM,"-c","import pcbnew"],capture_output=True,timeout=8)
        if native.returncode:
            return ""
        for candidate in (sys.executable,SYSTEM):
            available=subprocess.run([candidate,"-c","import shapely,pydantic,numpy"],
                                     capture_output=True,timeout=8)
            if available.returncode==0:
                return candidate
    except (OSError,subprocess.TimeoutExpired):
        pass
    return ""


TOPOLOGY_PYTHON = topology_python()
@pytest.mark.skipif(not TOPOLOGY_PYTHON,reason="KiCad+Shapely native test environment unavailable")
def test_complete_six_key_reference_source_cut_and_reconnection(tmp_path):
    pcb=tmp_path/"reference_keypad.kicad_pcb"
    generator=FIXTURE/"build_source.py"
    created=subprocess.run([SYSTEM,str(generator),"--output",str(pcb)],
                           capture_output=True,text=True,timeout=30)
    assert created.returncode==0,created.stderr
    drc=tmp_path/"source_drc.json"
    checked=subprocess.run(["kicad-cli","pcb","drc","--format","json",
                            "--output",str(drc),str(pcb)],
                            capture_output=True,text=True,timeout=50)
    assert checked.returncode==0,checked.stdout+checked.stderr
    native=json.loads(drc.read_text())
    assert not native.get("violations")
    assert not native.get("unconnected_items")
    scan=subprocess.run([SYSTEM,"-c",(
        "import pcbnew as p,json,sys;"
        "b=p.LoadBoard(sys.argv[1]);"
        "s=[f for f in b.GetFootprints() if f.GetReference().startswith('SW')];"
        "h=[f for f in b.GetFootprints() if f.GetReference()=='J1'];"
        "print(json.dumps({'switches':len(s),'headers':len(h),"
        "'switch_nets':sorted({pad.GetNetname() for f in s for pad in f.Pads() if pad.GetNetname()}),"
        "'header_nets':sorted({pad.GetNetname() for f in h for pad in f.Pads() if pad.GetNetname()})}))"
    ),str(pcb)],capture_output=True,text=True,timeout=30)
    assert scan.returncode==0,scan.stderr
    original=json.loads(scan.stdout)
    expected=["COL_"+str(i) for i in range(6)]+["ROW_0"]
    assert original["switches"]==6 and original["headers"]==1
    assert original["header_nets"]==expected
    assert original["switch_nets"]==expected
    target=tmp_path/"result"
    target.mkdir()
    cmd=[
        sys.executable,str(REPO/"scripts/hs_keyboard_splice_probe.py"),
        "--pcb",str(pcb),
        "--system-python",SYSTEM,
        "--topology-python",TOPOLOGY_PYTHON,
        "--out",str(target/"CUT.json"),
        "--postcut-islands-json",str(target/"ISLANDS.json"),
        "--postcut-edges-csv",str(target/"BRIDGES.csv"),
        "--machine-project-json",str(target/"MACHINE.json"),
        "--optimize-stepped",
        "--stepped-path-json",str(target/"CUT_PATH.json"),
        "--repair-mode","auto",
        "--repair-iterations-json",str(target/"ITERATIONS.json"),
        "--passive-matrix-json",str(target/"MATRIX_PROOF.json"),
        "--interposer-out",str(target/"interposer"),
    ]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=120,
                          env={**os.environ,"PYTHONPATH":str(REPO/"src")})
    assert result.returncode==0,result.stderr
    cut=json.loads((target/"CUT.json").read_text())
    path=json.loads((target/"CUT_PATH.json").read_text())
    topology=json.loads((target/"ISLANDS.json").read_text())
    iters=json.loads((target/"ITERATIONS.json").read_text())
    board=json.loads((target/"interposer/INTERPOSER_CHANNEL_MAP.json").read_text())
    verification=json.loads((target/"interposer/INTERPOSER_VERIFICATION.json").read_text())
    machine=json.loads((target/"MACHINE.json").read_text())
    proof=json.loads((target/"MATRIX_PROOF.json").read_text())
    assert proof["keys"]==6
    assert proof["ideal_switch_combinations_tested"]==64
    assert proof["ideal_switch_combinations_failed"]==[]
    assert proof["passive_keyboard_matrix_model_passed"] is True
    assert not proof["physical_repair_verified"]
    assert cut["passive_matrix_summary"]["payload_sha256"]==proof["payload_sha256"]
    assert cut["source_file_sha256"]==hashlib.sha256(pcb.read_bytes()).hexdigest()
    assert cut["repair_loop_summary"]["required_graph_connected_in_model"] is True
    assert topology["preexisting_unconnected_terminal_net_count"]==0
    assert topology["model_replay_remaining_required_components"]==0
    assert topology["model_replay_remaining_split_components"]==0
    assert topology["damaged_electrical_pad_count"]==0
    assert topology["planned_inert_track_remnants"]==0
    assert topology["candidate_graph_edges"]>=2
    assert path["collision_counts"]=={"pads":0,"vias":0,"switches":0,"critical":0}
    assert path["switch_candidates_left"]==3
    assert path["switch_candidates_right"]==3
    assert iters["selected_strategy"]=="pad_only"
    assert iters["total_iterations"]==1
    assert verification["native_design_checks_passed"] is True
    assert verification["native_drc_errors"]==0
    assert verification["native_unconnected_items"]==0
    assert board["channel_count"]==topology["candidate_graph_edges"]
    assert board["connector_mpn"] is None
    assert not machine["physical_authority_granted"]
    assert machine["release_assessment"]["achieved_state"]=="design_ready"
