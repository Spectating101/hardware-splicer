from __future__ import annotations

import pytest

import hardware_splicer.circuit_synthesis.motor_driver_planner as motor_planner
from hardware_splicer.api import create_app
from hardware_splicer.circuit_synthesis import plan_motor_driver
from hardware_splicer.electrical_contract_truth import (
    exact_output_voltage_v,
    logic_input_min_v,
    max_output_current_a,
)
from hardware_splicer.sdk import plan_motor_driver_circuit, sdk_info


def _intent(**extra):
    payload = {
        "goal": "drive a small DC pump from a microcontroller GPIO",
        "supply_rails": [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}],
        "load_requirements": [
            {"name": "pump", "type": "dc_motor", "voltage_v": 5.0, "current_a": 0.45}
        ],
        "signal_requirements": [{"name": "control", "type": "pwm", "voltage_v": 3.3}],
        "allowed_modules": [
            "usb-power-5v",
            "esp32-devkit",
            "mosfet-irlz44n",
            "water_pump_5v",
        ],
        "required_evidence": ["flyback_or_driver_protection"],
    }
    payload.update(extra)
    return payload


def _constraint(candidate, constraint_id: str):
    rows = [row for row in candidate["constraints"] if row["constraint_id"] == constraint_id]
    assert rows, candidate["constraints"]
    return rows[0]


def test_structured_catalog_current_truth_replaces_local_rating_table() -> None:
    assert max_output_current_a("buck-lm2596") == pytest.approx(2.0)
    assert max_output_current_a("buck-mp1584") == pytest.approx(3.0)
    assert max_output_current_a("usb-power-5v") is None
    assert max_output_current_a("dc-barrel-12v") is None
    assert max_output_current_a("l298n") is None
    assert max_output_current_a("mosfet-irlz44n") is None
    assert max_output_current_a("mosfet-irf520") is None


def test_exact_catalog_output_voltage_does_not_invent_adjustable_or_current_contracts() -> None:
    assert exact_output_voltage_v("usb-power-5v") == pytest.approx(5.0)
    assert exact_output_voltage_v("dc-barrel-12v") == pytest.approx(12.0)
    assert exact_output_voltage_v("buck-lm2596") is None
    assert exact_output_voltage_v("buck-mp1584") is None
    assert logic_input_min_v("l298n") is None
    assert logic_input_min_v("mosfet-irlz44n") is None
    assert logic_input_min_v("mosfet-irf520") is None


def test_motor_driver_planner_blocks_unstructured_switch_ratings_instead_of_guessing() -> None:
    candidate = plan_motor_driver(_intent()).to_dict()

    assert candidate["result"] == "blocked"
    assert candidate["selected_modules"] == ["mosfet-irlz44n"]
    assert candidate["generated_topology"][0]["operator_type"] == "low_side_switch"
    assert "mosfet-irlz44n_output_current_rating" in candidate["missing_evidence"]
    assert "mosfet-irlz44n_logic_input_threshold" in candidate["missing_evidence"]
    assert _constraint(candidate, "switch_current_rating")["status"] == "blocked"
    assert _constraint(candidate, "mosfet-irlz44n_logic_level")["status"] == "blocked"
    assert _constraint(candidate, "inductive_load_protection")["status"] == "pass"
    assert candidate["metadata"]["electrical_truth"]["summary_text_used_as_rating"] is False
    assert candidate["metadata"]["electrical_truth"]["magic_module_rating_table_used"] is False


def test_motor_driver_planner_becomes_reviewable_with_explicit_structured_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        motor_planner,
        "max_output_current_a",
        lambda module_id: 5.0 if module_id == "mosfet-irlz44n" else None,
    )
    monkeypatch.setattr(
        motor_planner,
        "logic_input_min_v",
        lambda module_id: 3.0 if module_id == "mosfet-irlz44n" else None,
    )
    monkeypatch.setattr(
        motor_planner,
        "integrated_inductive_protection",
        lambda module_id: False,
    )

    candidate = plan_motor_driver(_intent()).to_dict()

    assert candidate["result"] == "ready_for_review"
    assert _constraint(candidate, "switch_current_rating")["status"] == "pass"
    assert _constraint(candidate, "mosfet-irlz44n_logic_level")["status"] == "pass"
    assert _constraint(candidate, "inductive_load_protection")["status"] == "pass"
    rating = candidate["generated_topology"][0]["metadata"]["current_rating_a"]
    assert rating == pytest.approx(5.0)


def test_motor_driver_planner_blocks_missing_inductive_protection() -> None:
    candidate = plan_motor_driver(_intent(required_evidence=[])).to_dict()

    assert candidate["result"] == "blocked"
    assert "flyback_or_driver_protection" in candidate["missing_evidence"]
    assert _constraint(candidate, "inductive_load_protection")["status"] == "blocked"


def test_motor_driver_planner_blocks_missing_load_current() -> None:
    candidate = plan_motor_driver(
        _intent(load_requirements=[{"name": "pump", "type": "dc_motor", "voltage_v": 5.0}])
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "load_current_estimate" in candidate["missing_evidence"]


def test_motor_driver_planner_blocks_undersized_supply() -> None:
    candidate = plan_motor_driver(
        _intent(supply_rails=[{"name": "+5V", "voltage_v": 5.0, "max_current_a": 0.2}])
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "supply_current_margin" in candidate["missing_evidence"]
    assert _constraint(candidate, "supply_current_margin")["status"] == "blocked"


def test_catalog_power_source_without_current_contract_stays_unresolved() -> None:
    candidate = plan_motor_driver(
        _intent(supply_rails=[], allowed_modules=["usb-power-5v", "mosfet-irlz44n"])
    ).to_dict()

    assert candidate["metadata"]["supply"]["source"] == "structured_catalog_contract"
    assert candidate["metadata"]["supply"]["voltage_v"] == pytest.approx(5.0)
    assert candidate["metadata"]["supply"]["max_current_a"] is None
    assert "supply_current_limit" in candidate["missing_evidence"]


def test_adjustable_buck_does_not_become_an_undeclared_output_voltage() -> None:
    candidate = plan_motor_driver(
        _intent(supply_rails=[], allowed_modules=["buck-lm2596", "mosfet-irlz44n"])
    ).to_dict()

    assert candidate["metadata"]["supply"]["max_current_a"] == pytest.approx(2.0)
    assert candidate["metadata"]["supply"]["voltage_v"] is None
    assert "supply_voltage" in candidate["missing_evidence"]


def test_motor_driver_planner_does_not_resolve_l298n_threshold_from_nominal_pin_label() -> None:
    candidate = plan_motor_driver(
        _intent(
            allowed_modules=["usb-power-5v", "esp32-devkit", "l298n", "water_pump_5v"],
            required_evidence=[],
        )
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert candidate["selected_modules"] == ["l298n"]
    assert "l298n_output_current_rating" in candidate["missing_evidence"]
    assert "l298n_logic_input_threshold" in candidate["missing_evidence"]
    assert _constraint(candidate, "driver_current_rating")["status"] == "blocked"
    assert _constraint(candidate, "l298n_logic_level")["status"] == "blocked"


def test_level_shifter_cannot_resolve_an_unknown_driver_threshold() -> None:
    candidate = plan_motor_driver(
        _intent(
            allowed_modules=[
                "usb-power-5v",
                "esp32-devkit",
                "l298n",
                "level-shifter-4ch",
                "water_pump_5v",
            ],
            required_evidence=[],
        )
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert "l298n_logic_input_threshold" in candidate["missing_evidence"]
    assert _constraint(candidate, "l298n_logic_level")["status"] == "blocked"


def test_multiple_driver_families_require_explicit_topology_choice() -> None:
    candidate = plan_motor_driver(
        _intent(allowed_modules=["l298n", "mosfet-irlz44n", "usb-power-5v"])
    ).to_dict()

    assert candidate["result"] == "blocked"
    assert candidate["selected_modules"] == []
    assert "driver_topology_choice" in candidate["missing_evidence"]
    row = _constraint(candidate, "driver_topology_choice")
    assert row["status"] == "blocked"
    assert row["value"] == {
        "h_bridge_candidates": ["l298n"],
        "low_side_switch_candidates": ["mosfet-irlz44n"],
    }


def test_motor_driver_planner_sdk_and_api_surface_remains_available() -> None:
    sdk_candidate = plan_motor_driver_circuit(_intent())
    assert sdk_candidate["result"] == "blocked"
    assert "hs_plan_motor_driver_circuit" in sdk_info()["agent_handoff"]["primary_tools"]

    pytest.importorskip("fastapi")
    routes = {getattr(route, "path", "") for route in create_app().routes}
    assert "/v1/circuit-synthesis/motor-driver" in routes
