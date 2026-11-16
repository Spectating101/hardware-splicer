"""Source-bound true Edge.Cuts switch plates, including the previous missed V key."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_mechanical_round10"
PREVIOUS=ROOT/"examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5"
GENERATOR=ROOT/"src/hardware_splicer/keyboard_splice_plate.py"
EXTRACTOR=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_board_outline.py"
NATIVE="/usr/bin/python3"


def select_engine():
    for candidate in (sys.executable,NATIVE):
        try:
            proc=subprocess.run([candidate,"-c","import shapely"],
                                capture_output=True,timeout=8)
            if proc.returncode==0:
                return candidate
        except (OSError,subprocess.TimeoutExpired):
            pass
    return ""


ENGINE=select_engine()
pytestmark=pytest.mark.skipif(not ENGINE,reason="actual Shapely source geometry required")


def replay(tmp_path, *, route=None, multi=None, outline=None, source=None):
    src=tmp_path/"keys.json"; cut=tmp_path/"route.json"
    consequence=tmp_path/"audit.json"; source_edge=tmp_path/"outline.json"
    src.write_text(json.dumps(source or json.loads((FROZEN/"SOURCE_SWITCH_POSITIONS.json").read_text())))
    cut.write_text(json.dumps(route or json.loads((FROZEN/"STEPPED_CUT.json").read_text())))
    consequence.write_text(json.dumps(multi or json.loads((FROZEN/"MULTI_ROUTE.json").read_text())))
    source_edge.write_text(json.dumps(outline or json.loads((FROZEN/"mechanical_plate/SOURCE_BOARD_OUTLINE.json").read_text())))
    folder=tmp_path/"new_preview"
    proc=subprocess.run([
        ENGINE,str(GENERATOR),
        "--source-json",str(src),"--route-json",str(cut),
        "--multi-route-json",str(consequence),"--outline-json",str(source_edge),
        "--out",str(folder),
    ],capture_output=True,text=True,timeout=40)
    return proc,folder


def test_source_kicad_arc_board_two_key_plates_are_stable_and_not_fabrication_ready(tmp_path):
    proc,dest=replay(tmp_path)
    assert proc.returncode==0,proc.stderr
    receipt=json.loads((dest/"PLATE_GEOMETRY_CHECK.json").read_text())
    frozen=json.loads((FROZEN/"mechanical_plate/PLATE_GEOMETRY_CHECK.json").read_text())
    assert receipt==frozen
    assert receipt["original_board_outline_vertices"]==56
    assert receipt["retained_switch_positions_left_right"]==[35,23]
    assert receipt["source_switches_relocated"]==["K18","K27","K37","K[0]9"]
    assert receipt["accounted_original_switch_count"]==62
    assert receipt["switch_cutout_to_cut_web_pass"] is True
    assert receipt["minimum_modeled_aperture_to_source_outline_or_cut_mm"]==1.7784
    assert receipt["fabrication_release"]=="BLOCKED_MECHANICAL_REFERENCE_ONLY"
    assert receipt["native_scad_render_or_print_verified"] is False
    assert receipt["actual_case_mounting_design_verified"] is False
    assert receipt["original_switch_population_physically_confirmed"] is False
    for name in ("left.scad","right.scad","board_half_switch_plate.svg"):
        assert (dest/name).read_bytes()==(FROZEN/"mechanical_plate"/name).read_bytes()
    svg=ET.parse(dest/"board_half_switch_plate.svg").getroot()
    assert len(svg.findall(".//{http://www.w3.org/2000/svg}rect"))==58
    for side in ("left","right"):
        text=(dest/(side+".scad")).read_text()
        assert "linear_extrude(height=plate_thickness)" in text
        assert "plate_thickness=1.6" in text
        assert "NOT a finished" in text
    source=json.loads((FROZEN/"SOURCE_SWITCH_POSITIONS.json").read_text())
    sha="e0c605a421dec0e88264beb50f5c3ad58b37a0c20294703e6d8637c0f8613cd6"
    assert source["source_sha256"]==receipt["source_sha256"]==sha
    assert receipt["cut_path_sha256"]==json.loads((FROZEN/"STEPPED_CUT.json").read_text())["payload_sha256"]


def test_previous_5_key_cut_would_have_damaged_retained_v_key_aperture(tmp_path):
    old_path=json.loads((PREVIOUS/"STEPPED_CUT.json").read_text())
    old_audit=json.loads((PREVIOUS/"MULTI_ROUTE.json").read_text())
    proc,_=replay(tmp_path,route=old_path,multi=old_audit)
    assert proc.returncode!=0
    assert ("aperture clipped" in proc.stderr or
            "plate wall smaller than 1 mm" in proc.stderr)
    assert ("K35" in proc.stderr or "K46" in proc.stderr)


@pytest.mark.parametrize("issue",[
    "source_changed","route_digest_changed","outline_changed",
    "key_casualty_missing","key_wrong_x_coordinate",
])
def test_no_approved_halfplates_from_stale_or_invalid_kicad_source(tmp_path,issue):
    source=json.loads((FROZEN/"SOURCE_SWITCH_POSITIONS.json").read_text())
    route=json.loads((FROZEN/"STEPPED_CUT.json").read_text())
    outline=json.loads((FROZEN/"mechanical_plate/SOURCE_BOARD_OUTLINE.json").read_text())
    multi=json.loads((FROZEN/"MULTI_ROUTE.json").read_text())
    if issue=="source_changed":
        source["source_sha256"]="a"*64
    elif issue=="route_digest_changed":
        route["payload_sha256"]="a"*64
    elif issue=="outline_changed":
        outline["source_file_sha256"]="a"*64
    elif issue=="key_casualty_missing":
        multi["selected_consequence"]["sacrificed_switches"].pop()
    elif issue=="key_wrong_x_coordinate":
        source["switch_positions"][0]["x"]+=250
    proc,_=replay(tmp_path,source=source,route=route,outline=outline,multi=multi)
    assert proc.returncode!=0


def test_native_outline_extractor_uses_real_edgecuts_not_rectangle_proxy(tmp_path):
    try:
        check=subprocess.run([NATIVE,"-c","import pcbnew"],
                             capture_output=True,timeout=8)
    except (OSError,subprocess.TimeoutExpired):
        pytest.skip("KiCad native pcbnew unavailable")
    if check.returncode:
        pytest.skip("KiCad native pcbnew unavailable")
    source=ROOT/"examples/arbitrage_lab/keyboard_splice/reference_1x6/one_row_six_key_source.kicad_pcb"
    if not source.exists():
        pytest.skip("native 1x6 controlled original board missing")
    target=tmp_path/"outlines.json"
    proc=subprocess.run([
        NATIVE,str(EXTRACTOR),"--pcb",str(source),"--output",str(target)
    ],capture_output=True,text=True,timeout=45)
    assert proc.returncode==0,proc.stderr
    extracted=json.loads(target.read_text())
    assert extracted["source_file_sha256"]==hashlib.sha256(source.read_bytes()).hexdigest()
    assert extracted["source_edge_geometry_measured"] is True
    assert not extracted["actual_discarded_donor_measured"]
    assert extracted["fabrication_release"]=="REFERENCE_OUTLINE_ONLY"
    assert len(extracted["tessellated_edge_cuts_points_mm"])>=4
