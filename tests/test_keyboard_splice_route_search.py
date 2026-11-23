"""Bounded cut alternatives must account for real key losses and source pads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
SEARCH=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_route_search.py"


def native_shapely_python():
    for candidate in (sys.executable,"/usr/bin/python3"):
        try:
            result=subprocess.run([candidate,"-c","import shapely,numpy"],
                                  capture_output=True,timeout=8)
            if result.returncode==0:
                return candidate
        except (OSError,subprocess.TimeoutExpired):
            pass
    return ""


ENGINE=native_shapely_python()
pytestmark=pytest.mark.skipif(not ENGINE,reason="native Shapely/NumPy unavailable")


def example():
    keys=[
        {"ref":f"SW{i}","x":x,"y":y,"value":f"Key{i}","footprint":"Switch:MX"}
        for i,(x,y) in enumerate(((20,15),(20,45),(80,15),(80,45)),1)
    ]
    pads=[
        {"ref":key["ref"],"pad":"1","x":key["x"],
         "y":key["y"],"net":"ROW",
         "size_x_mm":1.4,"size_y_mm":1.4,"pad_attribute":1,
         "pad_shape":0,"orientation_degrees":0,"layer":"F.Cu"}
        for key in keys
    ]
    return {
        "source_sha256":"a"*64,
        "outline_bbox_mm":{"x_min":0,"x_max":100,"y_min":0,"y_max":60},
        "tracks":[{"net":"ROW","width_mm":0.4,"layer":"F.Cu",
                   "x1":20,"y1":15,"x2":80,"y2":15}],
        "pads":pads,"vias":[],"filled_zones":[],
        "footprints":[{"ref":"U1","value":"MCU","x":50,"y":30}],
        "switch_positions":keys,
    }


def run_search(tmp_path,board):
    raw=tmp_path/"board.json"
    out=tmp_path/"routes.json"
    selected=tmp_path/"selected.json"
    raw.write_text(json.dumps(board),encoding="utf-8")
    proc=subprocess.run([
        ENGINE,str(SEARCH),"--board-json",str(raw),
        "--output",str(out),"--selected-cut-json",str(selected),
    ],capture_output=True,text=True,timeout=45)
    assert proc.returncode==0,proc.stderr
    return json.loads(out.read_text()),json.loads(selected.read_text())


def test_search_multiple_cuts_and_source_bound_research_only(tmp_path):
    result,selected=run_search(tmp_path,example())
    assert result["attempted_strategies"]==12
    assert result["unique_proposed_paths"]>=1
    assert result["source_sha256"]=="a"*64
    assert not result["fabrication_authorized"]
    assert not result["physically_tested"]
    assert selected==result["selected_route"]
    assert result["selected_consequence"]["cut_path_sha256"]==selected["payload_sha256"]
    assert result["selected_consequence"]["reference_layout_assembly_verified"] is False
    assert result["selected_consequence"]["source_donor_physical_identity_verified"] is False
    body={k:v for k,v in selected.items() if k!="payload_sha256"}
    assert hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False,
                                     separators=(",",":")).encode()).hexdigest()==selected["payload_sha256"]


def test_key_and_electrical_pad_collision_is_separately_reported(tmp_path):
    b=example()
    raw=tmp_path/"board.json"
    route=tmp_path/"route.json"
    raw.write_text(json.dumps(b),encoding="utf-8")
    p={"source_sha256":"a"*64,"release":"PROPOSED_CUT_ONLY_NOT_VERIFIED",
       "kerf_mm":1.0,"cut_points_mm":[[20,0],[20,60]]}
    p["payload_sha256"]=hashlib.sha256(json.dumps(p,sort_keys=True,
                                        ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    route.write_text(json.dumps(p),encoding="utf-8")
    cmd=[ENGINE,"-c",(
        "import sys,json;"
        "sys.path.insert(0,sys.argv[3]);"
        "from keyboard_splice_route_search import audit_route;"
        "b=json.load(open(sys.argv[1]));p=json.load(open(sys.argv[2]));"
        "print(json.dumps(audit_route(b,p)))"
    ),str(raw),str(route),str(SEARCH.parent)]
    checked=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    assert checked.returncode==0,checked.stderr
    result=json.loads(checked.stdout)
    assert result["sacrificed_key_count"]==2
    assert len(result["live_electrical_pad_hits"])==2
    assert result["nominally_salvageable_except_sacrificed_switches"] is False
