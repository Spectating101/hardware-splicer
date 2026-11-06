from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "mapping_robot_sizing", ROOT / "hardware" / "reference_designs" / "mapping_robot_v0" / "sizing.py")
sz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sz)


def _f(value):
    return {"value": value, "unit": "x", "basis": "published", "source": "https://example.com/"}


PARTS = {
    "drive_motor": {"id": "m", "kind": "drive_motor", "facts": {
        "rated_voltage": _f(12), "output_free_speed_rpm": _f(200), "rated_current": _f(0.3), "stall_current": _f(1.5),
        "stall_torque": _f(0.4), "mass": _f(95)}, "unconfirmed": []},
    "wheel": {"id": "w", "kind": "wheel", "facts": {"outer_diameter": _f(65), "mass": _f(30)}, "unconfirmed": []},
    "lidar": {"id": "l", "kind": "lidar", "facts": {"supply_voltage": _f(5), "supply_current": _f(0.3), "mass": _f(50)},
              "unconfirmed": []},
    "battery_pack": {"id": "b", "kind": "battery_pack", "facts": {"nominal_voltage": _f(11.1), "capacity": _f(3000),
                                                                  "mass": _f(150)}, "unconfirmed": []},
    "dc_dc_converter": {"id": "d", "kind": "dc_dc_converter", "facts": {"output_voltage": _f(5)}, "unconfirmed": []},
    "compute_board": {"id": "c", "kind": "compute_board", "facts": {"supply_voltage": _f(5), "typical_current": _f(0.8),
                                                                    "mass": _f(50)}, "unconfirmed": []},
}
ASSUMPTIONS = {
    "usable_fraction": {"value": 0.8, "basis": "typical", "note": "Li-ion usable share; measure on the bench"},
    "converter_efficiency": {"value": 0.85, "basis": "typical", "note": "buck efficiency; measure on the bench"},
    "mcu_power_w": {"value": 0.5, "basis": "typical", "note": "ESP32-class average; measure on the bench"},
    "chassis_mass_kg": {"value": 0.6, "basis": "typical", "note": "printed chassis and fasteners; weigh it"},
}


def parts(**changes):
    p = copy.deepcopy(PARTS)
    for path, value in changes.items():
        role, fact = path.split("__")
        p[role]["facts"][fact] = value
    return p


def test_hs_wheel_rpm_for_65mm_wheel():
    r = sz.run_sizing(parts(), ASSUMPTIONS)
    assert r["required_wheel_rpm"] == pytest.approx(58.76, abs=0.01)
    assert r["hs_packet"]["drive_kinematics"]["drive_motor_ids"] == ["left_drive", "right_drive"]


def test_refuses_motor_missing_voltage_or_current():
    p = parts()
    del p["drive_motor"]["facts"]["rated_voltage"]
    p["drive_motor"]["unconfirmed"] = [{"fact": "rated_voltage", "reason": "not published"}]
    with pytest.raises(sz.SizingError, match="rated_voltage"):
        sz.run_sizing(p, ASSUMPTIONS)
    p = parts()
    del p["drive_motor"]["facts"]["rated_current"]
    with pytest.raises(sz.SizingError, match="rated_current"):
        sz.run_sizing(p, ASSUMPTIONS)


def test_mass_and_baseline_are_explicit_not_hs_defaults():
    r = sz.run_sizing(parts(), ASSUMPTIONS)
    # 2 motors 95 g, 2 wheels 30 g, lidar 50, pack 150, compute 50, chassis 600
    assert r["mass_kg"] == pytest.approx(1.1, abs=1e-6)
    assert r["hs_packet"]["drive_kinematics"]["mass_kg"] == pytest.approx(1.1, abs=1e-6)
    # (0.3*5 + 0.8*5 + 0.5) W / 11.1 V / 0.85
    assert r["baseline_current_a"] == pytest.approx(6.0 / 11.1 / 0.85, abs=1e-4)


def test_runtime_below_60_fails():
    r = sz.run_sizing(parts(battery_pack__capacity=_f(1000)), ASSUMPTIONS)
    assert r["passed"] is False
    assert any("runtime" in reason for reason in r["reasons"])


def test_runtime_passes_with_enough_pack():
    r = sz.run_sizing(parts(), ASSUMPTIONS)
    assert r["runtime_min"] >= 60 and r["passed"] is True, r["reasons"]


def test_speed_margin_below_1_5_fails():
    r = sz.run_sizing(parts(drive_motor__output_free_speed_rpm=_f(80)), ASSUMPTIONS)
    assert r["passed"] is False
    assert any("speed" in reason for reason in r["reasons"])


def test_conflicting_fact_uses_worst_case():
    alts = {"alternatives": [{"value": 100, "source": "a"}, {"value": 130, "source": "b"}], "unit": "rpm",
            "basis": "published", "confidence": "conflicting"}
    r = sz.run_sizing(parts(drive_motor__output_free_speed_rpm=alts), ASSUMPTIONS)
    assert r["effective"]["motor_free_speed_rpm"] == pytest.approx(100 * min(1.0, 11.1 / 12))
    cur = {"alternatives": [{"value": 0.3, "source": "a"}, {"value": 0.5, "source": "b"}], "unit": "A",
           "basis": "published", "confidence": "conflicting"}
    r = sz.run_sizing(parts(drive_motor__rated_current=cur), ASSUMPTIONS)
    assert r["effective"]["motor_run_current_a"] == 0.5


def test_motor_speed_and_torque_scaled_to_pack_voltage():
    r = sz.run_sizing(parts(battery_pack__nominal_voltage=_f(7.4)), ASSUMPTIONS)
    assert r["effective"]["motor_free_speed_rpm"] == pytest.approx(200 * 7.4 / 12)
    assert r["effective"]["motor_stall_torque_nm"] == pytest.approx(0.4 * 7.4 / 12)


def test_pack_above_motor_rating_fails():
    r = sz.run_sizing(parts(battery_pack__nominal_voltage=_f(14.8)), ASSUMPTIONS)
    assert r["passed"] is False and any("exceeds" in reason for reason in r["reasons"])


def test_load_selection_resolves_ids(tmp_path, monkeypatch):
    lib = [{"id": "m", "kind": "drive_motor"}, {"id": "w", "kind": "wheel"}]
    monkeypatch.setattr(sz, "load_parts", lambda: lib)
    sel = tmp_path / "selection.json"
    sel.write_text(json.dumps({"drive_motor": "m", "wheel": "w"}))
    assert sz.load_selection(sel) == {"drive_motor": lib[0], "wheel": lib[1]}
    sel.write_text(json.dumps({"drive_motor": "nope"}))
    with pytest.raises(sz.SizingError, match="nope"):
        sz.load_selection(sel)


def test_minimum_requirements_follow_from_hs_result():
    r = sz.run_sizing(parts(), ASSUMPTIONS)
    req = sz.minimum_requirements(r)
    assert req["min_motor_free_speed_rpm_at_pack_voltage"] == pytest.approx(58.76 * 1.5, abs=0.02)
    assert req["min_stall_torque_nm_per_motor"] == pytest.approx(r["required_force_n"] * 0.0325 / 2)
    assert req["min_pack_energy_wh"] == pytest.approx(r["average_power_w"] / 0.8)


def test_run_current_at_load_preferred_over_rated_current():
    p = parts()
    del p["drive_motor"]["facts"]["rated_current"]
    p["drive_motor"]["unconfirmed"] = [{"fact": "rated_current", "reason": "not published"}]
    p["drive_motor"]["facts"]["run_current"] = _f(0.12)
    r = sz.run_sizing(p, ASSUMPTIONS)
    assert r["effective"]["motor_run_current_a"] == 0.12


# --- Build 1 test 1 report -----------------------------------------------------------------------------------------------

_rspec = importlib.util.spec_from_file_location(
    "mapping_robot_report", ROOT / "hardware" / "reference_designs" / "mapping_robot_v0" / "report.py")
rep = importlib.util.module_from_spec(_rspec)
_rspec.loader.exec_module(rep)


def _report_parts():
    motor = copy.deepcopy(PARTS["drive_motor"])
    motor.update(name="Test motor", status="SOURCED_NOT_MEASURED",
                 listing={"url": "https://www.ruten.com.tw/item/1/", "marketplace": "ruten", "variant": "12V110RPM",
                          "price_twd": 550, "captured": "2026-11-06"},
                 unconfirmed=[{"fact": "gear_ratio", "reason": "seller lists speeds only"}])
    motor["facts"]["encoder_cpr"] = {"alternatives": [{"value": 11, "source": "a"}, {"value": 12, "source": "b"}],
                                     "unit": "count/rev_motor", "basis": "published", "confidence": "conflicting"}
    motor["facts"]["stall_torque"] = {"value": 0.412, "unit": "N·m", "basis": "typical", "source": "s",
                                      "note": "bracketed; measure on the bench"}
    return [motor]


QUOTES_OK = {"pass": True, "quotes_checked": 49, "failed": [], "checked_on": "2026-11-06"}


def test_report_lists_every_part_with_listing_and_confidence():
    text = rep.render_report(_report_parts(), sz.run_sizing(parts(), ASSUMPTIONS), QUOTES_OK)
    assert "Test motor" in text and "https://www.ruten.com.tw/item/1/" in text and "NT$550" in text
    assert "12V110RPM" in text


def test_report_lists_unconfirmed_facts_and_assumptions():
    text = rep.render_report(_report_parts(), sz.run_sizing(parts(), ASSUMPTIONS), QUOTES_OK)
    assert "gear_ratio" in text and "seller lists speeds only" in text
    assert "converter_efficiency" in text and "chassis_mass_kg" in text
    assert "stall_torque" in text and "bracketed" in text  # typical figures are listed with their notes


def test_report_lists_conflicting_facts():
    text = rep.render_report(_report_parts(), sz.run_sizing(parts(), ASSUMPTIONS), QUOTES_OK)
    assert "encoder_cpr" in text and "11" in text and "12" in text and "conflicting" in text


def test_report_says_designed_not_built():
    text = rep.render_report(_report_parts(), sz.run_sizing(parts(), ASSUMPTIONS), QUOTES_OK).lower()
    assert "sourced, not measured" in text
    assert "verified" not in text and "approved" not in text


def test_report_shows_sizing_fail_reasons():
    failing = sz.run_sizing(parts(battery_pack__capacity=_f(1000)), ASSUMPTIONS)
    text = rep.render_report(_report_parts(), failing, QUOTES_OK)
    assert "does not meet" in text.lower() and any(reason in text for reason in failing["reasons"])


def test_report_shows_failed_quote_check():
    bad = {"pass": False, "quotes_checked": 3, "failed": [{"part": "m", "claim": "mass", "source": "x",
                                                           "reason": "quote not found in the captured source"}]}
    text = rep.render_report(_report_parts(), sz.run_sizing(parts(), ASSUMPTIONS), bad)
    assert "quote not found" in text and "mass" in text
