from __future__ import annotations

import pytest

from hardware_splicer.arm_actuator_sizing import G, assess, cited_servo_rows, pick, static_loads


def test_static_loads_count_payload_and_the_actuators_beyond_each_joint() -> None:
    loads = static_loads([100, 100], 1.0, [0.5, 0.2])
    # joint 0: payload 1 kg at 0.2 m, the second actuator 0.2 kg at 0.1 m; its own actuator does not load it
    assert loads[0]["torque_nm"] == pytest.approx(G * (0.2 + 0.02))
    assert loads[1]["torque_nm"] == pytest.approx(G * 0.1)


def test_cited_rows_respect_supply_voltage() -> None:
    ids = {r["component_id"] for r in cited_servo_rows(12.0)}
    assert {"dynamixel-xm430-w350", "dynamixel-xm540-w270", "dynamixel-xl430-w250-t"} <= ids
    assert "dynamixel-xl330-m288-t" not in ids and "towerpro-mg996r" not in ids  # 6 V parts
    xm430 = next(r for r in cited_servo_rows(12.0) if r["component_id"] == "dynamixel-xm430-w350")
    assert (xm430["stall_torque_nm"], xm430["mass_kg"]) == (4.1, 0.082)


def test_pick_reports_where_no_cited_actuator_holds_the_load() -> None:
    result = pick([80, 150, 150, 60, 40, 20], 0.5, 1.5, cited_servo_rows(12.0), 0.5)
    assert not result["feasible"]
    assert result["joints"][0]["status"] == "no_cited_actuator_holds_it"
    assert result["joints"][1]["actuator"] == "dynamixel-xm540-w270"
    lighter = pick([80, 150, 150, 60, 40, 20], 0.2, 1.5, cited_servo_rows(12.0), 0.5)
    assert lighter["feasible"] and all(j["stall_share"] <= 0.5 for j in lighter["joints"])


def test_assess_openmanipulator_x_at_its_rated_payload() -> None:
    # ROBOTIS OpenMANIPULATOR-X: XM430-W350 joints, 500 g payload, 380 mm reach (shoulder 130, elbow 124, wrist 126 mm).
    result = assess([130, 124, 126], 0.5, ["dynamixel-xm430-w350"] * 3, cited_servo_rows(12.0))
    assert result["joints"][0]["stall_share"] == pytest.approx(0.53, abs=0.01)
