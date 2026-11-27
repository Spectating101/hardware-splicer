"""Rocker-bogie statics: the load split follows the moments, the step model behaves, and OSR's own motor comes first."""
from __future__ import annotations

import math

import pytest

from hardware_splicer import engineering_toolbelt as tb
from hardware_splicer.rocker_bogie import G, RockerBogieError, analyse, max_step, step_push, wheel_loads

EVEN = {"rear_wheel_x": -300, "rocker_pivot_x": -50, "bogie_pivot_x": 75, "middle_wheel_x": 0, "front_wheel_x": 150}


def test_equal_arms_give_each_wheel_a_third_of_its_side():
    loads = wheel_loads(EVEN, 10.0)
    side = 10.0 * G / 2
    assert all(abs(v - side / 3) < 1e-9 for v in loads.values())
    assert abs(sum(loads.values()) - side) < 1e-9


def test_moving_the_rocker_pivot_back_loads_the_rear_wheel():
    back = dict(EVEN, rocker_pivot_x=-150)
    loads = wheel_loads(back, 10.0)
    assert loads["rear_n"] > loads["front_n"] and loads["front_n"] == pytest.approx(loads["middle_n"])


def test_step_model_limits():
    r, n_f, w = 72.0, 10.0, 60.0
    assert step_push(0.0, r, n_f, 0.5) < 0  # a flat edge needs no push
    assert step_push(r, r, n_f, 0.5) == pytest.approx(n_f / 0.5)  # at one radius the edge is beside the axle
    assert max_step(r, n_f, w, 0.1) < max_step(r, n_f, w, 0.3) <= r  # more grip, higher step
    assert max_step(r, n_f, w, 0.8) == r  # capped: above one radius the bogie must lift the wheel


def test_bad_geometry_is_refused():
    with pytest.raises(RockerBogieError):
        wheel_loads(dict(EVEN, bogie_pivot_x=-100), 10.0)


def test_osr_speed_on_osr_wheels_ranks_osr_motor_first():
    # The Open Source Rover: 144 mm Wasteland wheels, ~1.6 m/s, goBILDA 5203 26.9:1 (its README and parts list).
    res = analyse({"geometry": EVEN, "mass_kg": 10.0, "wheel_mm": 144, "drive": {"speed_m_s": 1.6, "slope_deg": 15}})
    best = res["drive"]["options"][0]
    assert (best["family"], best["ratio"]) == ("gobilda-5203-12v", 26.9)
    assert best["speed_at_cruise_m_s"] >= 1.6 and best["step_torque_share_of_stall"] < 0.5
    env = tb.call("hs_rocker_bogie", {"spec": {"geometry": EVEN, "mass_kg": 10.0, "wheel_mm": 144, "drive": {"speed_m_s": 1.6}}})
    assert env["ok"] and "26.9" in env["summary"]


def test_above_one_radius_the_front_wheel_climbs_a_wall_if_friction_allows():
    # OSR's README: the rocker-bogie "can traverse obstacles over 2 times the height of the wheel". With equal arms the front wheel
    # carries 1/6 of the weight, so wall friction needs mu >= sqrt(1/5) = 0.447; the height is the bogie's lever times sin(rotation).
    res = analyse({"geometry": EVEN, "mass_kg": 10.0, "wheel_mm": 144, "friction": [0.4, 0.8]})
    low, high = res["step_climb"]["0.4"], res["step_climb"]["0.8"]
    assert not low["limited_by_model"] and "wall" not in low and low["max_step_mm"] < 72  # too little grip even below one radius
    assert high["wall"]["possible"] and high["wall"]["friction_needed"] == pytest.approx(math.sqrt(1 / 5), abs=1e-3)
    assert high["wall"]["max_step_mm"] is None
    bounded = analyse({"geometry": EVEN, "mass_kg": 10.0, "wheel_mm": 144, "friction": [0.8], "bogie_max_rotation_deg": 45})
    assert bounded["step_climb"]["0.8"]["wall"]["max_step_mm"] == pytest.approx(150 * math.sin(math.radians(45)), abs=0.1)
