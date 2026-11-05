"""HS clamshell SSH terminal — CAD, authority, electrical and budget checks.

These tests do not claim hardware fit, successful SSH or a manufactured device.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from mecha_splicer.bundle import generate_bundle
from mecha_splicer.spec import ProjectSpec


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "native_mecha"


def spec() -> dict:
    return json.loads((ROOT / "clamshell_ssh_terminal.json").read_text())


def sources() -> dict:
    return json.loads((ROOT / "components_20261106.json").read_text())


def evidence() -> dict:
    return json.loads((EVIDENCE / "design_evidence.json").read_text())


def test_native_mecha_generates_two_shells_and_open_preview(tmp_path):
    out = generate_bundle(spec(), out_dir=tmp_path)
    assert not out["blockers"]
    assert set(out["outputs"]) == {
        "base_shell.scad", "lid_shell.scad", "clamshell_open_preview.scad",
    }
    assert all((tmp_path / name).is_file() for name in out["outputs"])
    assert "hinge" in (tmp_path / "base_shell.scad").read_text().lower() or "hy=" in (tmp_path / "base_shell.scad").read_text()
    assert len(out["bom"]) == 9
    assert any("5V" in row["spec"] or "5V" in row["notes"] for row in out["bom"] if "CardKB" in row["item"])
    assert any("level shift" in row["item"].lower() for row in out["bom"])
    assert any("FIT-VERIFIED" in row["message"] for row in out["dfm"])
    assert any("ELECTRICALLY VERIFIED" in row["message"] for row in out["dfm"])
    assert any("FUNCTIONALLY VERIFIED" in row["message"] for row in out["dfm"])


@pytest.mark.parametrize("change", [
    {"case_w_mm": 110},
    {"case_d_mm": 73},
    {"display_board_w_mm": 145},
    {"keyboard_module_nominal_t_mm": 20},
    {"cable_slot_w_mm": 7.1, "knuckle_axial_gap_mm": 7},
    {"hinge_outer_d_mm": 5.5, "hinge_pin_d_mm": 4},
])
def test_incompatible_hardware_envelope_blocks(change):
    s = spec()
    s["clamshell_terminal"].update(change)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(s)


def test_cgal_meshes_watertight_and_six_pose_sweep():
    r = evidence()
    for part in ("base_shell", "lid_shell"):
        mesh = r["mesh"][part]
        assert mesh["nonmanifold_edges"] == 0
        assert mesh["triangle_count"] > 100
        assert mesh["bbox_mm"][0] == 120.0
        assert mesh["CAD_validated"]
        assert not mesh["physically_printed"]
        assert not mesh["physical_fit_verified"]
        assert (EVIDENCE / (part + ".stl")).is_file()
    sweep = r["cgal_interference_sweep"]
    assert [x["angle_deg"] for x in sweep] == [0, -30, -60, -90, -135, -165]
    assert all(x["interference_mesh"] == "EMPTY" and x["cad_clearance_pass"] for x in sweep)
    assert r["closed_envelope"]["closed_thickness_mm"] == 29.6
    assert r["closed_envelope"]["width_mm"] == 120


def test_existing_hs_electrical_planner_is_ready_for_review_only():
    r = json.loads((EVIDENCE / "hs_level_shift_review.json").read_text())
    assert r["result"] == "ready_for_review"
    assert any(x["operator_type"] == "level_shifter" for x in r["generated_topology"])
    gates = r["verification_gates"]
    assert len(gates) == 2
    assert all(g["critical"] and g["status"] == "open" for g in gates)
    assert {g["gate_id"] for g in gates} == {
        "level_shifter_rail_reference", "level_shifter_channel_mapping"
    }


def test_no_claims_of_real_hardware_or_ssh():
    r = evidence()
    assert r["actual_unit_assembled"] is False
    assert r["physical_fit_tested"] is False
    assert r["physical_hinge_sweep_tested"] is False
    assert r["firmware_ssh_connected_to_optiplex"] is False
    assert r["electrical_wiring_not_ready"] is True
    assert r["native_hs_level_shift_result"] == "ready_for_review"
    assert r["native_hs_level_shift_measurement_gates_open"] == 2


def test_exact_source_details_and_security_blockers():
    s = sources()
    display, keyboard = s["display"], s["keyboard"]
    assert display["known_screen_px"] == [800, 480]
    assert display["i2c_gpio"] == {"sda": 8, "scl": 9}
    assert keyboard["power_V"] == 5
    assert keyboard["i2c_address_hex"] == "0x5F"
    assert keyboard["dimensions_mm"] == [88, 54, 5]
    assert s["physical_proof"]["parts_purchased"] is False
    assert s["physical_proof"]["ssh_authenticated"] is False
    assert "host-key verification" in s["firmware_reuse"]["critical_security_defect"]
    assert s["firmware_reuse"]["pocketssh_flashed"] is False
    assert display["seller_stock"] == "sold_out_when_checked"
    assert keyboard["seller_stock"] == "sold_out_when_checked"


def test_parts_budget_is_stated_assumption_not_quote():
    s = sources()
    base = s["display"]["local_ask_twd"] + s["keyboard"]["local_ask_twd"]
    other = sum(x["assumed_twd"] for x in s["other_budget_assumptions"])
    assert base == 1589
    assert other == 405
    assert base + other == 1994
    assert all(x["verified_sku"] is False for x in s["other_budget_assumptions"])


def test_stl_parser_rejects_bad_geometry(tmp_path):
    path = ROOT / "produce_terminal.py"
    loaded = importlib.util.spec_from_file_location("hs_clamshell", path)
    assert loaded and loaded.loader
    mod = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(mod)
    malformed = tmp_path / "bad.stl"
    malformed.write_bytes(b"not an STL")
    with pytest.raises(ValueError):
        mod.audit_stl(malformed)
