"""The energy budget sizes a battery and inverter system and catches undersized fuses, inverters and batteries."""

from __future__ import annotations

import copy

import pytest

from hardware_splicer.energy_budget import EnergyBudgetError, check_energy

# A night-market stall: 5 h of lights and phone charging, and a 350 W blender run 1 min 15 times an hour (1.25 h).
STALL = {"session_hours": 5,
         "loads": [{"name": "LED lights", "watts": 60, "hours": 5},
                   {"name": "phone charging", "watts": 20, "hours": 5},
                   {"name": "blender", "watts": 350, "hours": 1.25, "surge_watts": 1050}],
         "battery": {"chemistry": "lifepo4", "nominal_v": 12.8, "capacity_ah": 100, "max_continuous_a": 100},
         "inverter": {"continuous_w": 1000, "surge_w": 2000, "efficiency": 0.88, "certified": True},
         "fuse_a": 125}


def rules(report):
    return {f["rule"] for f in report["findings"] if f["severity"] != "info"}


def test_sound_stall_sizing():
    report = check_energy(STALL)
    got = report["results"]
    assert got["average_load_w"] == 167.5
    assert got["ac_energy_wh"] == 837.5
    assert got["ac_peak_w"] == 430 and got["ac_surge_w"] == 1130
    # 1000 W out of an 88 % inverter at the LiFePO4 pack's 12.03 V low point.
    assert got["max_dc_current_a"] == pytest.approx(1000 / (12.8 * 0.94 * 0.88), abs=0.1)
    assert got["battery_energy_needed_wh"] == pytest.approx(837.5 / 0.88 + 10 * 5, abs=0.1)
    assert got["battery_usable_wh"] == 1152
    assert report["summary"]["errors"] == 0
    assert rules(report) == {"mains_safety"}
    assert report["build_ready"] is False


def test_undersized_fuse_and_dc_path():
    """The fault an agent made in the product trials: a 40 A DC path and an 80 A fuse behind a 1000 W inverter."""

    spec = copy.deepcopy(STALL)
    spec["fuse_a"] = 80
    spec["battery"]["max_continuous_a"] = 40
    assert {"fuse_too_small", "bms_current_low"} <= rules(check_energy(spec))


def test_small_inverter_and_battery():
    spec = copy.deepcopy(STALL)
    spec["inverter"].update(continuous_w=300, surge_w=600)
    spec["battery"]["capacity_ah"] = 50
    assert {"inverter_continuous_low", "inverter_surge_low", "battery_too_small"} <= rules(check_energy(spec))


def test_uncertified_inverter_blocks():
    spec = copy.deepcopy(STALL)
    spec["inverter"].pop("certified")
    report = check_energy(spec)
    assert any(f["rule"] == "mains_safety" and f["severity"] == "error" for f in report["findings"])


def test_dc_only_system_needs_no_inverter():
    spec = {"session_hours": 10, "loads": [{"name": "12 V fan", "watts": 24, "hours": 10, "ac": False}],
            "battery": {"chemistry": "lead_acid", "nominal_v": 12, "capacity_ah": 60}}
    report = check_energy(spec)
    assert report["results"]["battery_energy_needed_wh"] == 240
    assert report["results"]["battery_usable_wh"] == 360
    assert report["summary"]["errors"] == 0 and "mains_safety" not in rules(report)


def test_bad_inputs_are_refused():
    with pytest.raises(EnergyBudgetError, match="longer than"):
        check_energy(dict(STALL, loads=[{"name": "lights", "watts": 60, "hours": 6}]))
    with pytest.raises(EnergyBudgetError, match="chemistry"):
        check_energy(dict(STALL, battery={"chemistry": "unobtainium", "nominal_v": 12, "capacity_ah": 1}))
    with pytest.raises(EnergyBudgetError, match="inverter"):
        check_energy({k: v for k, v in STALL.items() if k != "inverter"})
