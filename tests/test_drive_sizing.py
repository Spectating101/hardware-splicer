from __future__ import annotations

import math

import pytest

from hardware_splicer.drive_sizing import G, KGCM_TO_NM, families, size


def test_required_torque_and_speed_follow_the_force_balance() -> None:
    r = size(2.5, 80, 2, 0.6, 15, crr=0.03, accel_m_s2=0.3)
    slope = 2.5 * (G * (math.sin(math.radians(15)) + 0.03 * math.cos(math.radians(15))) + 0.3) * 0.04 / 2
    assert r["required"]["torque_per_motor_nm"]["slope"] == pytest.approx(slope, abs=1e-4)
    assert r["required"]["wheel_rpm"] == pytest.approx(0.6 / (math.pi * 0.08) * 60, abs=0.1)
    assert r["inputs"]["crr"]["basis"] == "assumed"


def test_every_passing_option_meets_the_maker_limits() -> None:
    r = size(2.5, 80, 2, 0.6, 15)
    assert r["passing"]
    limits = {f["id"]: f for f in families()["families"]}
    for option in r["passing"]:
        fam = limits[option["family"]]
        assert option["speed_at_cruise_m_s"] >= 0.6 - 1e-3
        assert option["current_a"]["cruise_per_motor"] <= 0.25 * fam["stall_current_a"] + 1e-9
        peak = fam["limits"].get("intermittent_torque_kg_cm") or fam["limits"]["instantaneous_torque_kg_cm"]
        assert r["required"]["torque_per_motor_nm"]["slope"] <= peak * KGCM_TO_NM


def test_a_steep_heavy_case_rules_out_the_micro_motors() -> None:
    r = size(6.0, 100, 2, 0.5, 20)
    assert not any(o["family"].startswith("pololu-micro") for o in r["passing"])


def test_hobby_tt_motor_uses_the_sellers_measured_stall_and_leaves_limits_unknown():
    """OpenBot's TT gearmotor (Adafruit 3777): the seller's one-motor stall measurement (1.5 A at 6 V) drives the current
    checks; its torque limits are unpublished and stay unknown."""
    from hardware_splicer import drive_sizing as ds
    res = ds.size(0.9, 65, 4, 0.3, 10)
    tt = [o for o in res["passing"] if o["family"].startswith("adafruit-tt")]
    assert tt, "a 0.9 kg four-wheel rover at 0.3 m/s is within a TT motor's cited stall torque and speed"
    checks = tt[0]["checks"]
    assert checks["reaches_speed"] is True and checks["slope_torque_below_stall"] is True
    assert checks["flat_current_within_25pct_stall"] is True and checks["flat_torque_within_continuous_limit"] is None
    assert tt[0]["current_a"]["stall"] == 1.5 and 0.15 < tt[0]["current_a"]["cruise_per_motor"] < 0.375
    family = next(f for f in ds.families()["families"] if f["id"].startswith("adafruit-tt"))
    assert "one motor" in family["stall_current_basis"]

    # a family with no stall current still sorts after every known one
    data = ds.families()
    data["families"] = [dict(f, stall_current_a=None) if f["id"].startswith("adafruit-tt") else f for f in data["families"]]
    res = ds.size(0.9, 65, 4, 0.3, 10, data=data)
    assert res["passing"][-1]["current_a"]["cruise_per_motor"] is None
