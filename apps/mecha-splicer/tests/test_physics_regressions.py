"""Mechanical load accounting: do not double-charge reflected inertia."""

from __future__ import annotations

import math

import pytest


def test_linear_axis_acceleration_torque_counted_exactly_once():
    from src.mecha_splicer.engines.sim import _run_high_fidelity
    from src.mecha_splicer.spec import ProjectSpec

    project = ProjectSpec.model_validate({
        "project_name": "force_accounting",
        "linear_axis": {
            "travel_mm": 200,
            "rod_d_mm": 8,
            "rod_spacing_mm": 40,
            "rod_length_mm": 320,
            "belt_width_mm": 6,
            "pulley_teeth": 20,
            "payload_n": 10,
            "target_accel_mm_s2": 2000,
            "target_speed_mm_s": 80,
        },
    })
    report = _run_high_fidelity(project)
    torque = next(item for item in report if "torque_total_nm" in item.get("metrics", {}))
    metric = torque["metrics"]
    radius = (20 * 2.0 / 1000) / (2 * math.pi)
    load = 10.0 * radius
    accel = (10.0 / 9.81) * 2.0 * radius
    expected = load + accel
    assert metric["torque_total_nm"] == pytest.approx(round(expected, 4))
    assert metric["torque_load_nm"] == pytest.approx(round(load, 4))
    assert metric["torque_acceleration_nm"] == pytest.approx(round(accel, 4))
    assert metric["assumed_continuous_motor_torque_nm"] == 0.28
    # Prior formula added the acceleration term twice.
    assert metric["torque_total_nm"] != pytest.approx(round(load + 2*accel, 4))
