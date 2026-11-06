"""Dual touch proposal regression: existing HS CAD, system release and PTY reference.

Not a physical acceptance test. No ESP hardware is present or contacted.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_dual_touch import build_product_case
from keyboard_link_reference import (
    TYPE_KEY, TYPE_ACK, ReceiveOnce, crc16, decode_frame, encode_frame,
    key_to_pty, verify_pinned_hostkey,
)
from mecha_splicer.bundle import generate_bundle
from mecha_splicer.spec import ProjectSpec

HERE=Path(__file__).resolve().parents[1]
EVIDENCE=HERE/"evidence/native_mecha"

def read(p:Path)->dict:
    return json.loads(p.read_text(encoding="utf-8"))

def spec()->dict:
    return read(HERE/"dual_touch_spec.json")

def result()->dict:
    return read(EVIDENCE/"design_evidence.json")

def test_native_hs_generates_two_touch_board_bom_and_four_scad_outputs(tmp_path):
    b=generate_bundle(spec(),out_dir=tmp_path)
    assert not b["blockers"]
    assert set(b["outputs"])=={
        "base_shell.scad","lid_shell.scad",
        "clamshell_open_preview.scad","dual_touch_visual_preview.scad"}
    assert all((tmp_path/name).is_file() for name in b["outputs"])
    display=[x for x in b["bom"] if "Waveshare" in x["item"]]
    assert len(display)==1 and display[0]["qty"]==2
    assert all("CardKB" not in x["item"] and "level shifter" not in x["item"] for x in b["bom"])
    assert any("RS485" in x["spec"] for x in b["bom"])
    assert any("ELECTRICALLY VERIFIED" in x["message"] for x in b["dfm"])
    assert any("FUNCTIONALLY VERIFIED" in x["message"] for x in b["dfm"])

@pytest.mark.parametrize("bad",[
    {"lower_touch_board_w_mm":125},
    {"lower_touch_board_d_mm":95},
    {"case_w_mm":111},
    {"case_d_mm":73},
])
def test_small_tray_rejects_dual_touch_hardware_footprint(bad):
    s=spec();s["clamshell_terminal"].update(bad)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(s)

def test_real_cgal_mesh_audit_and_six_poses_still_pass_with_second_screen():
    r=result()
    assert r["closed_envelope"]["lower_input_type"]=="dual_touch"
    assert r["closed_envelope"]["lower_board_footprint_mm"]==[106.1,67.8]
    assert r["closed_envelope"]["width_mm"]==120
    assert r["closed_envelope"]["closed_thickness_mm"]==29.6
    assert r["native_hs_level_shift_result"]=="NOT_APPLICABLE_RS485_LINK"
    for x in r["mesh"].values():
        assert x["CAD_validated"] is True
        assert x["nonmanifold_edges"]==0
        assert x["physically_printed"] is False
    assert [x["angle_deg"] for x in r["cgal_interference_sweep"]]==[0,-30,-60,-90,-135,-165]
    assert all(x["interference_mesh"]=="EMPTY" for x in r["cgal_interference_sweep"])
    assert r["actual_unit_assembled"] is False
    assert r["firmware_ssh_connected_to_optiplex"] is False

def test_existing_machine_project_fail_closed_on_unverified_wiring_and_ssh():
    p=build_product_case(result())
    r=p.assess_release()
    assert p.project_id=="HS-DUAL-TOUCH-S1"
    assert r.allowed is False
    assert r.achieved_state.value!="operationally_authorized"
    assert {x.code for x in r.blockers}>={"unresolved_interface","safety_not_closed","release_state_not_reached"}
    assert len(p.components)>=2
    assert all(x.authority.value!="verified" for x in p.components)
    assert all(x.simulated for x in p.evidence)
    assert p.interfaces[0].contracts[0].values["onboard_transceiver"]=="SP3485 on both boards"

def test_frozen_repro_has_no_physical_release_and_no_observed_product():
    p=read(EVIDENCE/"machine_project.json")
    r=read(EVIDENCE/"hs_release_assessment.json")
    assert p["requested_release_state"]=="operationally_authorized"
    assert r["achieved_state"]=="design_ready"
    assert r["requested_state"]=="operationally_authorized"
    assert len(r["blockers"])>=3
    assert all(x["simulated"] for x in p["evidence"])
    assert all(x["authority"]!="measured" for x in p["components"])
    assert all(x["status"]!="passed" for x in p["verifications"] if x["method_type"]!="analysis")

def test_parts_cost_and_power_are_hypotheses_not_delivered_stock():
    data=read(HERE/"sources_20261106.json")
    power=data["workbench_power"]
    assert power["prototype_5V_board_count"]==2
    assert power["manufacturer_5V_draw_mA_each"]==450
    assert power["nominal_total_W"]==4.5
    assert data["board"]["rs485"]["transceiver"]=="SP3485 onboard"
    assert data["board"]["rs485"]["connector"]=="HY2.0 2P"
    b=read(EVIDENCE/"budget.json")
    assert b["budget_scenario_twd"]==2965
    assert b["screen_subtotal_twd"]==2500
    assert not b["parts_obtained"] and not b["quote_obtained"]
    assert not b["battery_included"] and not b["shipping_included"]

@pytest.mark.parametrize("key,mods,expected",[
    ("c",{"CTRL"},b"\x03"),("d",{"CTRL"},b"\x04"),
    ("b",{"CTRL"},b"\x02"),("ESC",set(),b"\x1b"),
    ("TAB",set(),b"\t"),("ENTER",set(),b"\r"),
    ("BACKSPACE",set(),b"\x7f"),("UP",set(),b"\x1b[A"),
    (":",set(),b":"),("/",set(),b"/"),("|",set(),b"|"),
    ("/",{"SHIFT"},b"?"),("x",{"ALT"},b"\x1bx"),
])
def test_terminal_keyboard_event_map(key,mods,expected):
    assert key_to_pty(key,mods)==expected

@pytest.mark.parametrize("key,mods",[
    ("DEL",set()),("ESC",{"CTRL"}),(";",{"CTRL"}),("a",{"META"}),("",set())])
def test_unsupported_keyboard_actions_are_blocked(key,mods):
    with pytest.raises(ValueError):
        key_to_pty(key,mods)

def test_rs485_packet_crc_and_duplicate_not_inserted_twice():
    receiver=ReceiveOnce()
    tx=encode_frame(0,key_to_pty("c",{"CTRL"}))
    kind,seq,payload=decode_frame(tx)
    assert (kind,seq,payload)==(TYPE_KEY,0,b"\x03")
    out,ack=receiver.accept(tx)
    assert out==b"\x03"
    assert decode_frame(ack)==(TYPE_ACK,0,b"")
    assert receiver.accept(tx)==(b"",ack)
    bad=bytearray(tx); bad[-1]^=1
    with pytest.raises(ValueError):
        decode_frame(bytes(bad))
    with pytest.raises(ValueError):
        receiver.accept(encode_frame(2,b"a"))
    frame=encode_frame(1,b"b")
    assert receiver.accept(frame)[0]==b"b"

@pytest.mark.parametrize("bad",[
    b"",b"\xa5",b"\xa5"+b"\0"*8, b"\x00"+b"\x01"*7])
def test_corrupt_frames_fail(bad):
    with pytest.raises(ValueError):
        decode_frame(bad)

def test_host_key_pinning_contract_rejects_mismatch_missing_or_wrong_digest_size():
    pin=b"Z"*32
    assert verify_pinned_hostkey(pin,b"Z"*32)
    assert not verify_pinned_hostkey(pin,b"X"*32)
    assert not verify_pinned_hostkey(pin,None)
    assert not verify_pinned_hostkey(pin,b"")
    assert not verify_pinned_hostkey(b"Z"*31,b"Z"*31)
    assert not verify_pinned_hostkey(b"",b"")
