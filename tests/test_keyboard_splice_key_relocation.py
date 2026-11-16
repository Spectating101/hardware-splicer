"""Native KiCad source-contact-to-relocated MX key board, with fail-closed tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=ROOT/"examples/arbitrage_lab/keyboard_splice/reference_1x6/one_row_six_key_source.kicad_pcb"
EXTRACT=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_extract.py"
REMOUNT=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_key_relocation.py"
NATIVE="/usr/bin/python3"


def _available():
    if not shutil.which("kicad-cli") or not REFERENCE.is_file():
        return False
    try:
        check=subprocess.run([NATIVE,"-c","import pcbnew"],capture_output=True,timeout=8)
        return check.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


pytestmark=pytest.mark.skipif(not _available(),reason="native KiCad 9 unavailable")


def construct(tmp_path, *, x_mm=82.0, loss_override=None):
    result=subprocess.run([NATIVE,str(EXTRACT),"--pcb",str(REFERENCE)],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    board=json.loads(result.stdout)
    sw=next(s for s in board["switch_positions"] if s["ref"]=="SW3")
    y=board["outline_bbox_mm"]
    route={
        "source_sha256":board["source_sha256"],
        "cut_points_mm":[[x_mm,y["y_min"]],[x_mm,y["y_max"]]],
        "kerf_mm":1.0,
        "release":"PROPOSED_CUT_ONLY_NOT_VERIFIED",
        "physical_cut_authorized":False,
    }
    route["payload_sha256"]=hashlib.sha256(json.dumps(
        route,sort_keys=True,ensure_ascii=False,separators=(",",":")
    ).encode()).hexdigest()
    casualty=[sw] if loss_override is None else loss_override
    status={
        "source_sha256":board["source_sha256"],
        "cut_path_sha256":route["payload_sha256"],
        "nominally_salvageable_except_sacrificed_switches":True,
        "sacrificed_switches":casualty,
        "remaining_switches":len(board["switch_positions"])-len(casualty),
        "remaining_left":2,"remaining_right":3,
    }
    settings={"selected_route":route,"selected_consequence":status}
    bp=tmp_path/"original.json";rp=tmp_path/"route.json"
    bp.write_text(json.dumps(board),encoding="utf-8")
    rp.write_text(json.dumps(settings),encoding="utf-8")
    return board,settings,bp,rp


def launch(tmp_path,bp,rp):
    out=tmp_path/"daughterboard"
    process=subprocess.run([
        NATIVE,str(REMOUNT),
        "--board-json",str(bp),"--route-search-json",str(rp),
        "--out",str(out),
    ],capture_output=True,text=True,timeout=30)
    return process,out


def test_reuse_real_original_pads_on_native_kicad_remount_board(tmp_path):
    board,route,bp,rp=construct(tmp_path)
    run,out=launch(tmp_path,bp,rp)
    assert run.returncode==0,run.stderr
    receipt=json.loads((out/"RELOCATION_MAP.json").read_text())
    assert receipt["source_sha256"]==board["source_sha256"]
    assert receipt["cut_path_sha256"]==route["selected_route"]["payload_sha256"]
    assert receipt["key_switches_relocated"]==1
    assert receipt["total_original_switch_positions_accounted"]==6
    assert receipt["independent_wire_endpoints"]==2
    source=receipt["source_wiring_map"][0]
    assert source["original_ref"]=="SW3"
    assert source["source_pads"]["1"]["original_net"]=="ROW_0"
    assert source["source_pads"]["2"]["original_net"]=="COL_2"
    assert source["wire_map"][0]["original_source_pad"]=="1"
    assert source["wire_map"][1]["original_source_pad"]=="2"
    assert receipt["fabrication_release"]=="BLOCKED_RELOCATION_PREVIEW_ONLY"
    assert receipt["physical_authority_granted"] is False

    pcb=out/"remount_keys.kicad_pcb"
    checked=subprocess.run([
        "kicad-cli","pcb","drc","--format","json",
        "--output",str(out/"native_drc.json"),str(pcb),
    ],capture_output=True,text=True,timeout=60)
    assert checked.returncode==0,checked.stdout+checked.stderr
    drc=json.loads((out/"native_drc.json").read_text())
    assert not drc["violations"] and not drc["unconnected_items"]
    scan=subprocess.run([NATIVE,"-c",(
        "import pcbnew as p,json,sys;"
        "b=p.LoadBoard(sys.argv[1]);"
        "print(json.dumps({'footprints':len(b.GetFootprints()),"
        "'tracks':len(b.GetTracks()),"
        "'pads':sum(len(list(f.Pads())) for f in b.GetFootprints() if f.GetReference().startswith(('SW','J')))}))"
    ),str(pcb)],capture_output=True,text=True,timeout=30)
    assert scan.returncode==0,scan.stderr
    loaded=json.loads(scan.stdout)
    assert loaded["footprints"]==2
    assert loaded["tracks"]==4


@pytest.mark.parametrize("tamper",[
    "source_hash","route_digest","missing_sacrificed_key",
    "misidentified_switch_position","live_pad_cut","untrusted_authority"
])
def test_no_relocation_from_stale_or_impossible_source(tamper,tmp_path):
    board,route,bp,rp=construct(tmp_path)
    if tamper=="source_hash":
        route["selected_route"]["source_sha256"]="f"*64
    elif tamper=="route_digest":
        route["selected_route"]["payload_sha256"]="e"*64
    elif tamper=="missing_sacrificed_key":
        route["selected_consequence"]["sacrificed_switches"]=[]
    elif tamper=="misidentified_switch_position":
        route["selected_consequence"]["sacrificed_switches"][0]["x"]+=15
    elif tamper=="live_pad_cut":
        original=route["selected_route"]
        original["cut_points_mm"]=[[75.0,board["outline_bbox_mm"]["y_min"]],
                                    [75.0,board["outline_bbox_mm"]["y_max"]]]
        original["payload_sha256"]=hashlib.sha256(json.dumps(
            {k:v for k,v in original.items() if k!="payload_sha256"},
            sort_keys=True,ensure_ascii=False,separators=(",",":")
        ).encode()).hexdigest()
        route["selected_consequence"]["cut_path_sha256"]=original["payload_sha256"]
    else:
        route["selected_route"]["physical_cut_authorized"]=True
        route["selected_route"]["payload_sha256"]=hashlib.sha256(json.dumps(
            {k:v for k,v in route["selected_route"].items() if k!="payload_sha256"},
            sort_keys=True,ensure_ascii=False,separators=(",",":")
        ).encode()).hexdigest()
        route["selected_consequence"]["cut_path_sha256"]=route["selected_route"]["payload_sha256"]
    rp.write_text(json.dumps(route),encoding="utf-8")
    process,_=launch(tmp_path,bp,rp)
    assert process.returncode != 0
