"""Native copper island simulator: actual geometry, no authority escalation.

The isolated system Python must have Shapely. CI environments without it skip
the native capability instead of inventing successful topology checks.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

HELPER = Path(__file__).resolve().parents[1] / "src/hardware_splicer/_pcbnew_helpers/keyboard_splice_islands.py"
def _topology_python() -> str:
    # On CI, Shapely belongs to the isolated pytest environment. On the
    # Optiplex, the KiCad-capable system Python already has it installed.
    for candidate in (sys.executable, "/usr/bin/python3"):
        try:
            check = subprocess.run([candidate, "-c", "import shapely"],
                                   capture_output=True, timeout=8)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            continue
        if check.returncode == 0:
            return candidate
    return ""


PYTHON = _topology_python()
pytestmark = pytest.mark.skipif(not PYTHON, reason="Shapely unavailable; native copper tests cannot run")


def board(tracks=None, pads=None, vias=None):
    if tracks is None:
        tracks = [
            {"x1":10,"y1":10,"x2":90,"y2":10,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
            {"x1":10,"y1":20,"x2":90,"y2":20,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
            {"x1":10,"y1":30,"x2":90,"y2":30,"width_mm":0.4,"net":"col1","layer":"B.Cu"},
        ]
    if pads is None:
        pads = [
            {"x":x,"y":y,"size_x_mm":2,"size_y_mm":2,
             "orientation_degrees":0,"pad_shape":0,"pad_attribute":1,
             "net":net,"layer":layer,"ref":f"S{i}","pad":"1"}
            for i,(x,y,net,layer) in enumerate([
                (10,10,"row1","F.Cu"),(90,10,"row1","F.Cu"),
                (10,20,"row1","F.Cu"),(90,20,"row1","F.Cu"),
                (10,30,"col1","B.Cu"),(90,30,"col1","B.Cu"),
            ])
        ]
    return {
        "source_sha256":"a"*64,
        "outline_bbox_mm":{"x_min":0,"x_max":100,"y_min":0,"y_max":40},
        "zone_count":0,"source_warnings":[],
        "tracks":tracks,"pads":pads,"vias":vias or [],
    }


def run_model(tmp_path, b, target, cut=50):
    source=tmp_path/"board.json"
    nets=tmp_path/"nets.json"
    output=tmp_path/"topology.json"
    source.write_text(json.dumps(b),encoding="utf-8")
    nets.write_text(json.dumps(target),encoding="utf-8")
    cmd=[PYTHON,str(HELPER),"--board-json",str(source),"--net-inventory-json",str(nets),
         "--cut-x-mm",str(cut),"--output",str(output)]
    done=subprocess.run(cmd,capture_output=True,text=True,timeout=35)
    assert done.returncode==0,done.stderr
    return json.loads(output.read_text())


def test_precut_disconnected_samenet_groups_do_not_become_one_fake_bridge(tmp_path):
    r=run_model(tmp_path,board(),["row1","col1"])
    assert r["model_pre_cut_island_count"]==3
    assert r["model_post_cut_island_count"]==6
    assert r["split_pre_cut_components"]==3
    assert r["candidate_graph_edges"]==3
    assert r["model_replay_remaining_split_components"]==0
    assert r["model_replay_achieved_full_restoration"] is True
    assert r["qualified_for_build"] is False
    assert r["release"]=="BLOCKED_REFERENCE_TOPOLOGY_ONLY"
    row=[i for i in r["sections"] if i["net"]=="row1"]
    assert len(row)==2 and all(i["postcut_track_only_island_count"]==2 for i in row)


def test_missing_pad_does_not_fabricate_bridge_and_replay_fails(tmp_path):
    b=board()
    b["pads"]=[p for p in b["pads"] if not (p["ref"]=="S1")]
    r=run_model(tmp_path,b,["row1","col1"])
    assert r["unanchored_split_components"]==1
    assert r["candidate_graph_edges"]==2
    assert r["model_replay_remaining_split_components"]==1
    assert not r["model_replay_achieved_full_restoration"]


def test_unbroken_same_named_separate_islands_remain_separate(tmp_path):
    b=board(tracks=[
        {"x1":5,"y1":10,"x2":25,"y2":10,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
        {"x1":75,"y1":10,"x2":95,"y2":10,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
    ], pads=[
        {"x":10,"y":10,"size_x_mm":2,"size_y_mm":2,"orientation_degrees":0,
         "pad_shape":0,"pad_attribute":1,"net":"row1","layer":"F.Cu","ref":"S1","pad":"1"},
        {"x":90,"y":10,"size_x_mm":2,"size_y_mm":2,"orientation_degrees":0,
         "pad_shape":0,"pad_attribute":1,"net":"row1","layer":"F.Cu","ref":"S2","pad":"1"},
    ])
    r=run_model(tmp_path,b,["row1"])
    assert r["model_pre_cut_island_count"]==2
    assert r["model_post_cut_island_count"]==2
    assert r["split_pre_cut_components"]==0
    assert r["candidate_graph_edges"]==0


def test_smd_overlapping_xy_on_opposite_layers_does_not_connect(tmp_path):
    a=board()
    a["tracks"]=[{"x1":10,"y1":10,"x2":30,"y2":10,"width_mm":0.4,"net":"n","layer":"F.Cu"},
                 {"x1":10,"y1":10,"x2":30,"y2":10,"width_mm":0.4,"net":"n","layer":"B.Cu"}]
    a["pads"]=[{"x":10,"y":10,"size_x_mm":2,"size_y_mm":2,"orientation_degrees":0,"pad_shape":0,
                "pad_attribute":1,"net":"n","layer":layer,"ref":f"P{i}","pad":"1"} for i,layer in enumerate(["F.Cu","B.Cu"])]
    r=run_model(tmp_path,a,["n"],cut=20)
    assert r["model_pre_cut_island_count"]==2


def test_plated_through_pad_connects_layers_but_zones_remain_unverified(tmp_path):
    a=board()
    a["tracks"]=[{"x1":10,"y1":10,"x2":30,"y2":10,"width_mm":0.4,"net":"n","layer":"F.Cu"},
                 {"x1":10,"y1":10,"x2":30,"y2":10,"width_mm":0.4,"net":"n","layer":"B.Cu"}]
    a["pads"]=[{"x":10,"y":10,"size_x_mm":2,"size_y_mm":2,"orientation_degrees":0,"pad_shape":0,
                "pad_attribute":0,"net":"n","layer":"F.Cu","ref":"P1","pad":"1"}]
    a["zone_count"]=3
    r=run_model(tmp_path,a,["n"],cut=20)
    assert r["model_pre_cut_island_count"]==1
    assert "UNMODELED_COPPER_ZONES" in r["issues"]
    assert not r["qualified_for_build"]


def test_unsupported_pad_shape_fail_closed_with_issue(tmp_path):
    a=board()
    a["pads"][0]["pad_shape"]=99
    r=run_model(tmp_path,a,["row1"])
    assert "PAD_SHAPE_UNSUPPORTED:99" in r["issues"]
    assert r["release"]=="BLOCKED_REFERENCE_TOPOLOGY_ONLY"


def test_real_filled_zone_connects_gap_that_unfilled_tracks_cannot(tmp_path):
    a=board()
    a["tracks"]=[
        {"x1":10,"y1":10,"x2":35,"y2":10,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
        {"x1":65,"y1":10,"x2":90,"y2":10,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
    ]
    a["pads"]=[p for p in a["pads"] if p["net"]=="row1" and p["y"]==10]
    without=run_model(tmp_path,a,["row1"])
    assert without["model_pre_cut_island_count"]==2
    assert without["candidate_graph_edges"]==0
    a["filled_zones"]=[{
        "net":"row1","layer":"F.Cu","is_filled":True,
        "polygons":[{"shell":[[0,8],[100,8],[100,12],[0,12]],"holes":[]}],
    }]
    a["zone_count"]=1
    with_zone=run_model(tmp_path,a,["row1"])
    assert with_zone["model_pre_cut_island_count"]==1
    assert with_zone["model_post_cut_island_count"]==2
    assert with_zone["candidate_graph_edges"]==1
    assert with_zone["model_replay_remaining_split_components"]==0
    assert "UNMODELED_COPPER_ZONES" not in with_zone["issues"]
    assert with_zone["qualified_for_build"] is False


def test_unfilled_zone_does_not_imply_conduction(tmp_path):
    a=board()
    a["tracks"]=[
        {"x1":10,"y1":10,"x2":35,"y2":10,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
        {"x1":65,"y1":10,"x2":90,"y2":10,"width_mm":0.4,"net":"row1","layer":"F.Cu"},
    ]
    a["pads"]=[p for p in a["pads"] if p["net"]=="row1" and p["y"]==10]
    a["filled_zones"]=[{"net":"row1","layer":"F.Cu","is_filled":False,"polygons":[]}]
    a["zone_count"]=1
    r=run_model(tmp_path,a,["row1"])
    assert r["model_pre_cut_island_count"]==2
    assert "RELEVANT_COPPER_ZONE_UNFILLED" in r["issues"]
    assert not r["qualified_for_build"]


def test_invalid_zone_is_marked_reconstructed_not_source_exact(tmp_path):
    a=board()
    a["filled_zones"]=[{
        "net":"row1","layer":"F.Cu","is_filled":True,
        "polygons":[{"shell":[[0,0],[100,30],[100,0],[0,30]],"holes":[]}],
    }]
    r=run_model(tmp_path,a,["row1"])
    assert "ZONE_BOUNDARY_RECONSTRUCTED_WITH_GEOMETRY_REPAIR" in r["issues"]
    assert r["release"]=="BLOCKED_REFERENCE_TOPOLOGY_ONLY"


def test_stepped_cut_receipt_and_affected_net_inventory_fail_closed(tmp_path):
    import hashlib
    a=board()
    plan={
        "source_sha256":a["source_sha256"],"release":"PROPOSED_CUT_ONLY_NOT_VERIFIED",
        "kerf_mm":1.0,"cut_points_mm":[[50,0],[53,20],[50,40]],
    }
    plan["payload_sha256"]=hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False,
                                                   separators=(",",":")).encode()).hexdigest()
    bfile=tmp_path/"board_path.json"
    nfile=tmp_path/"nets.json"
    pfile=tmp_path/"cut_path.json"
    outfile=tmp_path/"island_path.json"
    bfile.write_text(json.dumps(a),encoding="utf-8")
    nfile.write_text(json.dumps(["row1","col1"]),encoding="utf-8")
    pfile.write_text(json.dumps(plan),encoding="utf-8")
    base=[PYTHON,str(HELPER),"--board-json",str(bfile),
          "--net-inventory-json",str(nfile),"--cut-x-mm","50",
          "--cut-path-json",str(pfile),"--output",str(outfile)]
    success=subprocess.run(base,capture_output=True,text=True,timeout=35)
    assert success.returncode==0,success.stderr
    data=json.loads(outfile.read_text())
    assert data["cut_path_sha256"]==plan["payload_sha256"]
    assert data["cut_path_kind"]=="stepped_polyline"
    assert data["qualified_for_build"] is False
    # No path can silently substitute a different revision or exclude a net
    plan["cut_points_mm"]=[[50,0],[55,20],[50,40]]
    pfile.write_text(json.dumps(plan),encoding="utf-8")
    bad=subprocess.run(base,capture_output=True,text=True,timeout=35)
    assert bad.returncode!=0
    assert "digest invalid" in bad.stderr
    pfile.write_text(json.dumps({**plan,"payload_sha256":hashlib.sha256(
        json.dumps({k:v for k,v in plan.items() if k!="payload_sha256"},
                   sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    ).hexdigest()}),encoding="utf-8")
    nfile.write_text(json.dumps(["row1"]),encoding="utf-8")
    omitted=subprocess.run(base,capture_output=True,text=True,timeout=35)
    assert omitted.returncode!=0
    assert "net inventory mismatch" in omitted.stderr
