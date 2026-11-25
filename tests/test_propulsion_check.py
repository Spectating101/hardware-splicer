"""The general propulsion check reproduces the proving-ground drone and refuses or flags what it cannot support."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.propulsion_check import PropulsionCheckError, check_propulsion, main

ROOT = Path(__file__).resolve().parents[1]
TABLE = json.loads((ROOT / "examples/drone_proving_ground/inputs/motor_f1404_3800kv_thrust.json").read_text())
RESULTS = json.loads((ROOT / "examples/drone_proving_ground/generated/results.json").read_text())

# The HS-3G inputs: four F1404 motors with HQ 3x3x3 props on a 4S 650 mAh 70C/140C pack and a 35 A ESC stack.
HS3G = {"rotors": 4, "prop": "HQ 3x3x3", "all_up_mass_g": RESULTS["mass"]["auw_g"], "prop_diameter_mm": 76.2,
        "battery": {"cells": 4, "capacity_mah": 650, "c_continuous": 70, "c_burst": 140},
        "esc_continuous_a": 35, "assumptions": {"min_tw_ratio": 3.0}}


def rules(report):
    return {f["rule"] for f in report["findings"]}


def test_matches_the_proving_ground_calculation():
    report = check_propulsion(HS3G, TABLE)
    want = RESULTS["propulsion"]
    got = report["results"]
    assert got["hover_power_method"] == "extrapolated"
    assert got["hover_time_min"] == want["hover_time_min"]
    assert got["hover_time_upper_bound_min"] == want["hover_time_upper_bound_min"]
    assert got["hover_current_a"] == want["hover_current_a"]
    assert got["thrust_to_weight"] == want["tw_ratio_full"]
    assert got["battery_limited_throttle_pct"] == want["throttle_limit_pct"]
    assert got["battery_limited_thrust_to_weight"] == want["tw_ratio_limited"]
    assert got["full_throttle_current_a"] == want["max_current_a"]
    assert got["esc_margin"] == want["esc_margin_full"]
    assert {"hover_extrapolated", "battery_current_limited"} <= rules(report)
    assert report["summary"]["errors"] == 0
    assert report["flight_tested"] is False and report["flight_authorized"] is False


def test_interpolates_inside_the_table():
    heavy = dict(HS3G, all_up_mass_g=4 * 214.5)  # exactly the 55 % row
    got = check_propulsion(heavy, TABLE)["results"]
    assert got["hover_power_method"] == "interpolated"
    assert got["throttle_pct"] == 55.0
    assert got["hover_power_per_rotor_w"] == 118.65


def test_too_heavy_cannot_hover():
    report = check_propulsion(dict(HS3G, all_up_mass_g=1400), TABLE)
    assert "cannot_hover" in rules(report) and "thrust_to_weight_low" in rules(report)


def test_refuses_a_table_without_a_source():
    table = copy.deepcopy(TABLE)
    table.pop("source")
    with pytest.raises(PropulsionCheckError, match="source"):
        check_propulsion(HS3G, table)


def test_flags_a_table_from_another_voltage():
    assert "bench_voltage_mismatch" in rules(check_propulsion(dict(HS3G, battery=dict(HS3G["battery"], cells=3)), TABLE))


def test_flags_a_physically_impossible_table():
    table = copy.deepcopy(TABLE)
    for row in table["props"]["HQ 3x3x3"]:
        row[3] /= 10  # a tenth of the current, so a tenth of the power for the same thrust
        row[5] /= 10
    assert "implausible_table" in rules(check_propulsion(HS3G, table))


def test_small_esc_motor_rating_and_overlapping_props():
    spec = dict(HS3G, esc_continuous_a=20, motor_max_current_a=19, frame={"wheelbase_mm": 100})
    found = rules(check_propulsion(spec, TABLE))
    assert {"esc_undersized", "motor_over_rating", "props_overlap"} <= found


def test_parts_must_sum_to_the_stated_mass():
    spec = dict(HS3G, parts=[{"name": "frame", "mass_g": 100}, {"name": "motor", "mass_g": 20, "qty": 4}])
    with pytest.raises(PropulsionCheckError, match="sum to 180"):
        check_propulsion(spec, TABLE)


def test_cli_exit_codes(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    table = tmp_path / "table.json"
    table.write_text(json.dumps(TABLE))
    spec.write_text(json.dumps(HS3G))
    assert main([str(spec), "--table", str(table)]) == 0
    spec.write_text(json.dumps(dict(HS3G, all_up_mass_g=1400)))
    assert main([str(spec), "--table", str(table)]) == 1
    spec.write_text(json.dumps(dict(HS3G, rotors=2)))
    assert main([str(spec), "--table", str(table)]) == 2
    capsys.readouterr()
