"""Independent HS Thor keyboard geometry and KiCad evidence barriers.

Native KiCad exercise is optional on runners with no KiCad/pcbnew. Tests still
bind the recorded Optiplex original native KiCad result to each PCB hash.
No physical shell clearance or manufactured keyboard is claimed.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil

import pytest

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/"examples/cyberdeck/thor_split_qwerty"
GEN=HERE/"generated"
S=json.loads((GEN/"fit_report.json").read_text())
V=json.loads((HERE/"evidence/verification.json").read_text())

def _sha(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()

def test_all_two_keyboard_profiles_true_qwerty_50_keys():
    assert S["schema"]=="hs.thor_split_qwerty_external_scan_retrofit.v1"
    assert S["full_keyboard_key_count"]==50
    for name,expected_pitch,expected_size in (
        ("flush_7mm",7.0,36.0),("detachable_9mm",9.0,47.0)):
        p=S["variants"][name]
        assert p["computed_2D_screen_overlap_pass"]
        assert p["total_keys"]==50
        L,R=p["sides"]
        assert L["side"]=="left" and R["side"]=="right"
        assert all(len(row["keys"])==25 for row in (L,R))
        assert len({key["id"] for half in (L,R) for key in half["keys"]})==50
        assert L["keys"][0]["label"]=="Q"
        assert L["keys"][4]["label"]=="T"
        assert R["keys"][0]["label"]=="Y"
        assert R["keys"][4]["label"]=="P"
        assert L["keys"][5]["label"]=="A"
        assert R["keys"][5]["label"]=="H"
        for side in (L,R):
            assert side["pcb_width_mm"]==expected_size
            assert side["keycap_pitch_mm"][0]==expected_pitch
            assert side["pcb_height_mm"]<60


def test_verified_ext_scan_is_exact_but_internal_depth_absent():
    src=S["source"]
    assert src["sha256"]=="42800c73d5e0523961f243e482732fcd2ba119c6e3aeae55659d7adee32e8402"
    assert src["triangle_count"]==1012267
    assert src["mesh_exterior_not_internal_cavity"]
    assert src["maker_scan_no_mount_or_depth_certification"]
    assert 152<src["xyz_extent_mm"][0]<153
    assert S["tested_internal_cavities"] is False
    assert S["tested_closed_lid"] is False
    assert S["original_controller_removal_tested"] is False
    assert S["fabrication_approved"] is False


def test_wing_wins_nonintrusive_layout_but_not_closed_lid_or_original_controls():
    from sys import path
    path.insert(0,str(HERE))
    from verify import evaluate_fit
    fits=evaluate_fit(S)
    assert fits["flush_7mm"]["minimum_screen_gap_mm"]==1.0
    assert fits["flush_7mm"]["nominal_2mm_buffer_in_outline"] is False
    assert fits["detachable_9mm"]["minimum_screen_gap_mm"]==2.0
    assert fits["detachable_9mm"]["nominal_2mm_buffer_in_outline"] is True
    for side in S["variants"]["flush_7mm"]["sides"]:
        assert side["lateral_extension_outside_case_mm"]==0
    ex=[side["lateral_extension_outside_case_mm"]
        for side in S["variants"]["detachable_9mm"]["sides"]]
    assert ex==[9.84,10.25]
    for report in fits.values():
        assert report["closed_lid_fit_proven"] is False
        assert report["real_internal_geometry_proven"] is False


def test_all_native_board_receipts_are_sha_bound_not_fabrication_pass():
    assert V["schema"]=="hs.thor_split_qwerty_verification.v1"
    assert V["status"]=="FOUR_NATIVE_ROUTED_PCBS_DRC_PASS_PHYSICAL_RETROFIT_BLOCKED"
    assert V["native_drc_all_four"] is True
    assert len(V["board_results"])==4
    assert V["sum_footprints"]==240
    assert V["provenance"]["input_report_sha256"]==_sha(GEN/"fit_report.json")
    for board in V["board_results"]:
        path=HERE/board["source"]
        assert path.exists()
        assert _sha(path)==board["sha256"]
        assert board["native_kicad_cli_drc"]=="pass"
        assert board["violation_count"]==0
        assert board["unconnected_count"]==0
        assert board["switches"]==25
        assert board["diodes"]==25
        assert board["breakout_solderpads"]==10
        assert board["nets_per_key"]==25
        assert board["nets_col"]==board["nets_row"]==5
        assert board["copper_segments_and_vias"]>=280
        assert board["vias"]>=30,board
        # These are native KiCad 9 PCB files, not SVG illustrations.
        data=path.read_text()
        assert data.startswith("(kicad_pcb")
        assert data.count('(footprint "SW_Push_1P1T_NO_CK_KMR2"')==25
        assert data.count('(footprint "D_SOD-123"')==25
        assert data.count('(footprint "TestPoint_Pad_D1.0mm"')==10
        assert "(segment" in data and "(via" in data
        assert board["external_mcu_and_battery_present"] is False
    assert V["ZMK_firmware_compiled"] is False
    assert V["schematic_nets_parity_tested"] is False
    assert V["physical_Thor_assembly_tested"] is False
    assert V["fabrication_or_order_authorized"] is False


def test_native_drc_report_text_matches_receipt_for_every_board():
    for item in V["board_results"]:
        board=HERE/item["source"]
        report=board.with_suffix(".drc.txt")
        assert report.exists()
        text=report.read_text()
        assert "** Found 0 DRC violations **" in text
        assert "** Found 0 unconnected pads **" in text
        assert "** Found 0 Footprint errors **" in text
        # Files remain data, not authority to order:
        assert not V["fabrication_or_order_authorized"]


def test_printable_layout_and_actual_CAD_sources_exist():
    assert (GEN/"thor_two_keyboard_options.png").stat().st_size>25000
    for name in ("flush_7mm","detachable_9mm"):
        svg=(GEN/name/f"thor_{name}_1to1_A4.svg").read_text()
        assert 'width="210mm" height="297mm"' in svg
        assert "NOT A CUTTING OR DRILL TEMPLATE" in svg
        assert "50 mm scale check" in svg
        assert svg.count("<rect")>=52
        scad=(GEN/name/f"thor_{name}_concept.scad").read_text()
        assert "source_scan" in scad and "module_mounts_known = false" in scad
        for side in ("left","right"):
            path=GEN/name/f"{side}_25_key_locations.csv"
            assert len(path.read_text().splitlines())==26
            assert (GEN/name/f"thor_{name}_{side}_25keys.kicad_pcb").stat().st_size>30000


def test_no_false_electronic_or_mechanical_certification():
    for key in ("external_BLE_controller_designed","ZMK_firmware_compiled",
       "switch_keycap_actuation_tested","schematic_nets_parity_tested",
       "physical_Thor_assembly_tested","closed_lid_no_collision_proven",
       "harness_and_strain_relief_tested","battery_and_protection_tested",
       "original_Thor_motherboard_modified","fabrication_or_order_authorized",
       "human_typing_trial_tested"):
        assert V[key] is False,key
    assert V["suggested_first_prototype"]=="detachable_9mm"


@pytest.mark.skipif(not (shutil.which("kicad-cli") and importlib.util.find_spec("pcbnew")),
                    reason="native KiCad/pcbnew unavailable; source-bound receipt still checked")
def test_live_native_kicad_drc_and_connectivity_all_four_again(tmp_path):
    import sys
    sys.path.insert(0,str(HERE))
    from verify import run
    new=run(tmp_path/"live.json")
    assert new==V
    assert len(new["board_results"])==4


@pytest.mark.skipif(not importlib.util.find_spec("pcbnew"),
                    reason="native pcbnew unavailable")
def test_hacking_one_switch_net_must_fail_independent_matrix_checker(tmp_path):
    import sys,pcbnew as p
    sys.path.insert(0,str(HERE))
    from verify import inspect_board
    original=GEN/"detachable_9mm/thor_detachable_9mm_left_25keys.kicad_pcb"
    b=p.LoadBoard(str(original))
    sw=next(f for f in b.GetFootprints() if f.GetReference()=="SW1")
    pad=next(q for q in sw.Pads() if q.GetNumber()=="1")
    bad=b.GetNetsByName()["COL2"]
    pad.SetNet(bad)
    tampered=tmp_path/"mutated.kicad_pcb"
    p.SaveBoard(str(tampered),b)
    with pytest.raises(ValueError,match="column or intermediate"):
        inspect_board(tampered,{"pcb_mm":[47.0,58.0]},"left")
