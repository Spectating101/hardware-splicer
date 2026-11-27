"""The general propulsion check reproduces the proving-ground drone and refuses or flags what it cannot support."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hardware_splicer.propulsion_check import PropulsionCheckError, check_propulsion, main, pick, tables

ROOT = Path(__file__).resolve().parents[1]
TABLE = json.loads((ROOT / "examples/drone_proving_ground/inputs/motor_f1404_3800kv_thrust.json").read_text())
SUNNYSKY = json.loads((ROOT / "examples/drone_proving_ground/inputs/motor_sunnysky_x2212_980kv_thrust.json").read_text())
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


def test_flags_a_table_that_is_not_bench_data():
    """A product trial agent, offline, typed a table from memory and cited a shop listing; that must not read as clean."""

    table = copy.deepcopy(TABLE)
    table.update(source="https://www.tokopedia.com/some-shop/motor", source_class="vendor chart transcribed by hand", accessed="not available offline")
    report = check_propulsion(HS3G, table)
    assert "table_unverified" in rules(report) and report["table"]["verified"] is False
    assert check_propulsion(HS3G, TABLE)["table"]["verified"] is True


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


# The product trial's F450 camera quad: 1283 g on four 2212-class motors with 10 x 4.7 props and a 3S 5000 mAh 30C pack.
F450 = {"rotors": 4, "prop": "APC1047 3S", "all_up_mass_g": 1283, "prop_diameter_mm": 254, "esc_continuous_a": 30,
        "battery": {"cells": 3, "capacity_mah": 5000, "c_continuous": 30}, "frame": {"wheelbase_mm": 450}}


def test_maker_table_without_a_throttle_column():
    """SunnySky steps its table by thrust; hover is interpolated between the 300 g and 400 g rows."""

    report = check_propulsion(F450, SUNNYSKY)
    got = report["results"]
    assert report["table"]["verified"] is True
    assert got["hover_power_method"] == "interpolated" and "throttle_pct" not in got
    assert 33.3 < got["hover_power_per_rotor_w"] < 51.06
    assert got["hover_power_per_rotor_w"] == 36.78 and got["hover_time_min"] == 17.6
    assert got["thrust_to_weight"] == 2.84


def test_motor_rating_comes_from_the_table_when_the_spec_has_none():
    """At full throttle the APC1047 on 3S draws 15.5 A; SunnySky rates the motor 15 A for 30 s."""

    assert "motor_over_rating" in rules(check_propulsion(F450, SUNNYSKY))
    assert "motor_over_rating" not in rules(check_propulsion(dict(F450, prop="APC1038 3S"), SUNNYSKY))
    # A higher rating typed into the spec does not loosen the maker's: the error stays and the disagreement is reported.
    raised = rules(check_propulsion(dict(F450, motor_max_current_a=18), SUNNYSKY))
    assert {"motor_over_rating", "motor_rating_above_maker"} <= raised
    assert "motor_over_rating" in rules(check_propulsion(dict(F450, prop="APC1038 3S", motor_max_current_a=14), SUNNYSKY))


def test_maker_table_rows_are_consistent():
    for prop, rows in SUNNYSKY["props"].items():
        for thrust, volts, amps, watts, eff in rows:
            assert abs(volts * amps - watts) < 0.02, prop
            assert abs(thrust / watts - eff) < 0.01, prop
            assert volts == (11.1 if prop.endswith("3S") else 14.8)


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


LIBRARY = tables()
CF2 = {"rotors": 4, "prop": "CF2 45mm", "all_up_mass_g": 27, "battery": {"cells": 1, "capacity_mah": 240, "c_continuous": 15},
       "esc_continuous_a": 2.0, "assumptions": {"avionics_power_w": 0.96, "min_tw_ratio": 1.0}}


def test_library_copies_are_the_proving_ground_tables():
    strip = lambda t: {k: v for k, v in t.items() if k not in {"motor_mass_g", "motor_mass_source", "prop_diameter_mm", "prop_diameter_source"}}
    assert strip(LIBRARY["tmotor-f1404-3800kv-4s"]) == TABLE
    assert strip(LIBRARY["sunnysky-x2212-980kv"]) == SUNNYSKY
    rev_b = json.loads((ROOT / "examples/drone_proving_ground/revision_b/inputs/thrust_table.json").read_text())
    assert strip(LIBRARY["tmotor-f1404-2900kv-4s"]) == rev_b
    for table in LIBRARY.values():
        assert set(table["prop_diameter_mm"]) == set(table["props"])


def test_a_table_can_be_named():
    assert check_propulsion(HS3G, "tmotor-f1404-3800kv-4s")["results"] == check_propulsion(HS3G, TABLE)["results"]
    with pytest.raises(PropulsionCheckError, match="no cited thrust table"):
        check_propulsion(HS3G, "made-up-motor")


def test_crazyflie_rows_come_from_bitcraze_whole_aircraft_table():
    cf = LIBRARY["crazyflie-2.0-coreless-1s"]
    raw = cf["raw_whole_aircraft"]["rows"]
    idle = raw[0][0]
    for (amps, thrust, volts, pwm, rpm), row in zip(raw[1:], cf["props"]["CF2 45mm"]):
        assert row == [pwm, round(thrust / 4, 3), volts, round((amps - idle) / 4, 4), rpm]


def test_hover_time_calibrates_against_crazyflies_published_flight_time():
    # Bitcraze: 27 g, 240 mAh, "flight time with stock battery: 7 minutes". HS's interpolation, with the whole pack used
    # as Crazyflie's firmware does, lands within 5%; HS's default 80% usable capacity reads about 20% short.
    published = LIBRARY["crazyflie-2.0-coreless-1s"]["reference_aircraft"]["published_flight_time_min"]
    full = check_propulsion(dict(CF2, assumptions=dict(CF2["assumptions"], usable_capacity_fraction=1.0)), "crazyflie-2.0-coreless-1s")
    assert full["results"]["hover_power_method"] == "interpolated"
    assert abs(full["results"]["hover_time_min"] - published) / published < 0.05
    default = check_propulsion(CF2, "crazyflie-2.0-coreless-1s")["results"]["hover_time_min"]
    assert 0.75 < default / published < 0.85


def test_extrapolation_holds_on_crazyflie_rows_cut_from_below():
    # The same table with its low rows removed forces HS-3G-style extrapolation (up to 1.7x below the lowest row); the
    # headline (pessimistic) hover power stays within 12% of the interpolated value from the full table.
    spec = dict(CF2, assumptions=dict(CF2["assumptions"], usable_capacity_fraction=1.0))
    truth = check_propulsion(spec, "crazyflie-2.0-coreless-1s")["results"]["hover_power_per_rotor_w"]
    for lowest in (8.0, 9.0, 10.0, 11.5):
        cut = copy.deepcopy(LIBRARY["crazyflie-2.0-coreless-1s"])
        cut["props"]["CF2 45mm"] = [r for r in cut["props"]["CF2 45mm"] if r[1] >= lowest]
        got = check_propulsion(spec, cut)["results"]
        assert got["hover_power_method"] == "extrapolated"
        assert abs(got["hover_power_per_rotor_w"] - truth) / truth < 0.12, lowest


def test_pick_counts_each_motors_own_mass_and_prop_fit():
    spec = {"rotors": 4, "mass_without_motors_g": 197.5, "battery": {"cells": 4, "capacity_mah": 850, "c_continuous": 70},
            "esc_continuous_a": 35}
    loose = pick(spec)
    sunny = [r for r in loose["passing"] if r["table"] == "sunnysky-x2212-980kv"]
    assert sunny and all(r["all_up_mass_g"] == round(197.5 + 4 * 58.5, 1) for r in sunny)
    framed = pick(dict(spec, frame={"wheelbase_mm": 137}))
    assert {r["table"] for r in framed["passing"]} == {"tmotor-f1404-3800kv-4s", "tmotor-f1404-2900kv-4s"}
    reasons = {(r["table"], r["prop"]): r["reasons"] for r in framed["failing"]}
    assert "props_overlap" in reasons[("sunnysky-x2212-980kv", "APC9047 4S")]
    assert reasons[("crazyflie-2.0-coreless-1s", "CF2 45mm")] == ["motor_mass_unknown"]
    rev_b = next(r for r in framed["passing"] if r["table"] == "tmotor-f1404-2900kv-4s")
    assert "bench_on_charged_pack" in rev_b["warnings"]
    capped = pick(dict(spec, max_prop_diameter_mm=100))
    assert all(r["prop_diameter_mm"] <= 100 for r in capped["passing"])


def test_pick_needs_the_mass_without_motors():
    with pytest.raises(PropulsionCheckError, match="mass_without_motors_g"):
        pick({"rotors": 4, "battery": {"cells": 4, "capacity_mah": 850, "c_continuous": 70}, "esc_continuous_a": 35})


REV_B = json.loads((ROOT / "examples/drone_proving_ground/revision_b/reference/results.json").read_text())


def test_reproduces_hs3g_b_from_its_full_pack_table():
    # The maker ran the F1404 2900KV on a charged 4S pack (16.8 V). Hover power carries over, so the general check matches
    # HS-3G-B's own design script; full-throttle thrust is scaled to nominal voltage, so thrust-to-weight reads lower.
    spec = {"rotors": 4, "prop": "GF3028-3", "all_up_mass_g": REV_B["mass"]["auw_g"], "prop_diameter_mm": 77.06,
            "battery": {"cells": 4, "capacity_mah": 850, "c_continuous": 70, "c_burst": 140}, "esc_continuous_a": 35}
    report = check_propulsion(spec, "tmotor-f1404-2900kv-4s")
    got, want = report["results"], REV_B["propulsion"]
    assert report["summary"]["errors"] == 0 and "bench_on_charged_pack" in rules(report)
    assert got["hover_time_min"] == want["hover_time_min"]
    assert got["hover_time_upper_bound_min"] == want["hover_time_upper_bound_min"]
    assert got["hover_current_a"] == want["hover_current_a"]
    assert got["full_throttle_current_a"] == want["max_current_a"]
    assert got["bench_max_thrust_total_g"] == want["max_thrust_total_g"]
    assert abs(got["max_thrust_total_g"] - want["max_thrust_total_g"] * (14.8 / got["bench_voltage_v"]) ** 2) < 1.0
    assert 3.8 < got["thrust_to_weight"] < 4.0


def test_a_table_from_a_smaller_pack_still_does_not_apply():
    spec = {"rotors": 4, "prop": "APC9047 3S", "all_up_mass_g": 900, "battery": {"cells": 4, "capacity_mah": 3000, "c_continuous": 25},
            "esc_continuous_a": 30}
    assert "bench_voltage_mismatch" in rules(check_propulsion(spec, SUNNYSKY))


CALIBRATION = json.loads((ROOT / "src/hardware_splicer/data/propulsion/calibration_aircraft_20261127.json").read_text())


def test_brushless_crazyflie_calibrates_the_same_way():
    # Crazyflie 2.1 Brushless: 34 g, 350 mAh, "10 minutes"; Bitcraze states at least 5 g/W at hover. Fed through the check
    # as a two-point table (hover point from that efficiency, peak point from the motor post), the whole pack gives 10 min
    # and HS's 80% default about 8, the same 20% as the brushed aircraft.
    cf = next(a for a in CALIBRATION["aircraft"] if a["id"] == "crazyflie-2.1-brushless")
    hover_g = cf["takeoff_g"] / cf["rotors"]
    hover_w = hover_g / cf["power"]["hover_efficiency_g_per_w"]
    peak = cf["power"]["peak"]
    table = {"schema": "hs.drone_proving_ground.thrust_table.v1", "motor": "Bitcraze 08028-10000KV", "source": cf["sources"][1].split()[0],
             "source_class": "maker_page", "accessed": "2026-11-27", "columns": ["thrust_g", "voltage_v", "current_a"],
             "props": {"55-35": [[hover_g, 3.7, hover_w / 3.7], [peak["thrust_g"], peak["voltage_v"], peak["current_a"]]]}}
    spec = {"rotors": 4, "prop": "55-35", "all_up_mass_g": cf["takeoff_g"], "esc_continuous_a": 5,
            "battery": {"cells": 1, "capacity_mah": cf["capacity_mah"], "c_continuous": 15},
            "assumptions": {"avionics_power_w": cf["avionics_power_w"], "min_tw_ratio": 1.0}}
    full = check_propulsion(dict(spec, assumptions=dict(spec["assumptions"], usable_capacity_fraction=1.0)), table)["results"]
    assert abs(full["hover_time_min"] - cf["published_flight_time_min"]) / cf["published_flight_time_min"] < 0.05
    default = check_propulsion(spec, table)["results"]["hover_time_min"]
    assert 0.75 < default / cf["published_flight_time_min"] < 0.85


def test_momentum_law_from_the_peak_alone_would_flatter_a_small_motor():
    # Why the check takes the more pessimistic of two extrapolations: the ideal 1.5-power law from the 08028's peak point
    # (30 g at 7.2 W) predicts far better hover efficiency than Bitcraze measured (5 g/W).
    cf = next(a for a in CALIBRATION["aircraft"] if a["id"] == "crazyflie-2.1-brushless")
    peak, hover_g = cf["power"]["peak"], cf["takeoff_g"] / cf["rotors"]
    law_w = peak["power_w"] * (hover_g / peak["thrust_g"]) ** 1.5
    assert hover_g / law_w > 1.5 * cf["power"]["hover_efficiency_g_per_w"]


def test_a_five_inch_frame_picks_a_five_inch_motor_and_a_three_inch_frame_does_not():
    five = pick({"rotors": 4, "mass_without_motors_g": 520, "battery": {"cells": 6, "capacity_mah": 1300, "c_continuous": 100},
                 "esc_continuous_a": 55, "frame": {"wheelbase_mm": 225}})
    assert five["passing"] and five["passing"][0]["table"].startswith("tmotor-v2207")
    assert all(r["full_throttle_current_a"] is not None for r in five["passing"])
    three = pick({"rotors": 4, "mass_without_motors_g": 197.5, "battery": {"cells": 4, "capacity_mah": 850, "c_continuous": 70},
                  "esc_continuous_a": 35, "frame": {"wheelbase_mm": 137}})
    reasons = {(r["table"], r["prop"]): r["reasons"] for r in three["failing"]}
    assert all("props_overlap" in v or "prop_gap_small" in v for (t, _), v in reasons.items() if t.startswith("tmotor-v2207") and "-4s" in t)
    assert {r["table"] for r in three["passing"]} <= {"tmotor-f1404-2900kv-4s", "tmotor-f1404-3800kv-4s"}
