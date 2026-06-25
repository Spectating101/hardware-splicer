from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.api import create_app
from hardware_splicer.circuit_synthesis import plan_analog_conditioning, topology_library_card
from hardware_splicer.circuit_synthesis.topology_library import evaluate_topology_authority
from hardware_splicer.sdk import circuit_synthesis_capability, plan_circuit_synthesis, sdk_info, synthesize_circuit


def _analog_intent() -> dict:
    return {
        "goal": "condition a noisy 5V analog sensor output into an ESP32 ADC with an RC filter",
        "signal_requirements": [
            {"type": "analog", "sensor_output_max_v": 5.0, "adc_max_v": 3.3, "noise_filter": True}
        ],
        "frequency_constraints": [{"sample_rate_hz": 50}],
        "allowed_modules": ["usb-power-5v", "esp32-devkit", "soil_moisture"],
    }


def test_topology_library_declares_trusted_low_voltage_ceiling() -> None:
    card = topology_library_card()

    assert card["domain"] == "low_voltage_mechatronics"
    assert "voltage_divider" in card["trusted_operator_types"]
    assert "rc_filter" in card["trusted_operator_types"]
    assert "h_bridge" in card["trusted_operator_types"]
    assert "high_side_switch" in card["planned_or_review_limited_operator_types"]
    assert "universal electronics" in card["claim"]


def test_candidate_authority_identifies_review_limited_protection() -> None:
    candidate = plan_analog_conditioning(_analog_intent())
    authority = evaluate_topology_authority(candidate)

    assert authority["inside_trusted_ceiling"] is True
    assert authority["authority_tier"] == "bounded_plan_review"
    assert authority["review_limited_operator_types"] == ["protection_diode"]
    assert authority["next_authority_gap"] == "Close compile/fabrication/bench gates before stronger readiness claims."


def test_compiled_synthesis_reports_physical_support_authority(tmp_path: Path) -> None:
    result = synthesize_circuit(_analog_intent(), out_dir=tmp_path, export_gerber=False)
    authority = result["topology_authority"]

    assert result["ok"] is True
    assert authority["inside_trusted_ceiling"] is True
    assert authority["authority_tier"] == "bounded_compile_ready_for_review"
    assert authority["physical_support_component_count"] == 4
    assert authority["physical_support_node_count"] == 4
    assert authority["virtual_review_support_component_count"] == 1
    assert authority["authority_score"] == 85
    assert "transient_or_reverse_energy_protection" in authority["next_authority_gap"]
    assert result["compose_result"]["topology_authority"] == authority


def test_unsupported_synthesis_reports_blocked_authority() -> None:
    result = plan_circuit_synthesis(
        {
            "goal": "design a low noise analog audio preamplifier from discrete transistors",
            "supply_rails": [{"name": "+12V", "voltage_v": 12.0}],
            "signal_requirements": [{"type": "analog", "voltage_v": 1.0}],
            "allowed_modules": ["usb-power-5v", "esp32-devkit"],
        }
    )

    authority = result["metadata"]["topology_authority"]
    assert result["result"] == "blocked"
    assert authority["authority_tier"] == "blocked"
    assert authority["inside_trusted_ceiling"] is False
    assert authority["authority_score"] <= 45
    assert "bounded_planner" in authority["next_authority_gap"]


def test_topology_capability_exposed_in_sdk_and_api() -> None:
    assert circuit_synthesis_capability()["schema_version"] == "hardware_splicer.topology_library.v1"
    assert "hs_circuit_synthesis_capability" in sdk_info()["agent_handoff"]["primary_tools"]

    pytest.importorskip("fastapi")
    routes = {getattr(route, "path", "") for route in create_app().routes}
    assert "/v1/circuit-synthesis/capability" in routes
