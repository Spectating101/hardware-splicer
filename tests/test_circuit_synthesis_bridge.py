from __future__ import annotations

from pathlib import Path

import pytest

import hardware_splicer.circuit_synthesis.motor_driver_planner as motor_planner
from hardware_splicer.api import create_app
from hardware_splicer.circuit_synthesis import compile_synthesis_candidate, plan_circuit
from hardware_splicer.sdk import plan_circuit_synthesis, sdk_info, synthesize_circuit


def _motor_intent(**extra):
    payload = {
        "goal": "build an ESP32 controlled 5V pump driver",
        "supply_rails": [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}],
        "load_requirements": [{"name": "pump", "type": "dc_motor", "voltage_v": 5.0, "current_a": 0.45}],
        "signal_requirements": [{"name": "pump_enable", "type": "pwm", "voltage_v": 3.3}],
        "allowed_modules": ["usb-power-5v", "esp32-devkit", "mosfet-irlz44n", "water_pump_5v"],
        "required_evidence": ["flyback_or_driver_protection"],
    }
    payload.update(extra)
    return payload


def _unsupported_intent():
    return {
        "goal": "design a low noise analog audio preamplifier from discrete transistors",
        "supply_rails": [{"name": "+12V", "voltage_v": 12.0, "max_current_a": 0.25}],
        "signal_requirements": [{"name": "audio_in", "type": "analog", "voltage_v": 1.0}],
        "allowed_modules": ["usb-power-5v", "esp32-devkit"],
    }


def test_arbitrary_dispatch_routes_supported_motor_intent_without_inventing_ratings() -> None:
    candidate = plan_circuit(_motor_intent()).to_dict()

    assert candidate["result"] == "blocked"
    assert candidate["metadata"]["dispatch"]["selected_planner"] == "motor_driver"
    assert candidate["generated_topology"][0]["operator_type"] == "low_side_switch"
    assert "mosfet-irlz44n_output_current_rating" in candidate["missing_evidence"]
    assert "level_shifter_or_compatible_driver" in candidate["missing_evidence"]
    assert "mosfet-irlz44n_logic_input_threshold" not in candidate["missing_evidence"]


def test_arbitrary_dispatch_blocks_unsupported_intent() -> None:
    candidate = plan_circuit_synthesis(_unsupported_intent())

    assert candidate["result"] == "blocked"
    assert candidate["candidate_id"] == "unsupported_circuit_intent"
    assert candidate["constraints"][0]["constraint_id"] == "unsupported_goal"
    assert candidate["recommended_build_path"]["can_compile_with_existing_auto_wire"] is False


def test_compile_bridge_refuses_blocked_candidate(tmp_path: Path) -> None:
    candidate = plan_circuit(_unsupported_intent())
    result = compile_synthesis_candidate(candidate, out_dir=tmp_path)

    assert result["ok"] is False
    assert result["error"] == "candidate_blocked"
    assert result["candidate"]["result"] == "blocked"


def test_synthesize_circuit_compiles_when_structured_driver_contract_is_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    result = synthesize_circuit(_motor_intent(), out_dir=tmp_path, export_gerber=False)

    assert result["schema_version"] == "hardware_splicer.circuit_synthesis_bridge.v1"
    assert result["candidate"]["result"] == "ready_for_review"
    # The declared load remains a functional selected_part/topology endpoint rather than
    # being laundered into a concrete catalog module identity. Only validated catalog
    # modules are handed to the compile bridge.
    assert result["module_ids"] == ["usb-power-5v", "esp32-devkit", "mosfet-irlz44n"]
    assert result["candidate"]["selected_parts"][0]["id"] == "pump"
    assert result["compose_result"]["mode"] == "strict_synthesis_netlist"
    assert result["compose_result"]["compile_result"]["ok"] is True
    assert result["design_quality_gate"]["build_ready"] is True


def test_synthesis_sdk_info_and_api_plan() -> None:
    info = sdk_info()
    assert "hs_plan_circuit_synthesis" in info["agent_handoff"]["primary_tools"]
    assert "hs_synthesize_circuit" in info["agent_handoff"]["primary_tools"]

    pytest.importorskip("fastapi")

    routes = {getattr(route, "path", "") for route in create_app().routes}

    assert "/v1/circuit-synthesis/plan" in routes
    assert "/v1/circuit-synthesis/compile" in routes
