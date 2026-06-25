from __future__ import annotations

import pytest

from hardware_splicer.circuit_synthesis import (
    CircuitIntent,
    Constraint,
    FunctionalPart,
    Port,
    SynthesisCandidate,
    TopologyOperator,
)


def test_circuit_synthesis_ir_roundtrip() -> None:
    intent = CircuitIntent.from_dict(
        {
            "goal": "drive a small DC pump from an ESP32 GPIO",
            "supply_rails": [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}],
            "load_requirements": [{"name": "pump", "type": "dc_motor", "current_a": 0.45}],
            "signal_requirements": [{"name": "control", "type": "pwm", "voltage_v": 3.3}],
            "allowed_modules": ["esp32-devkit", "mosfet-irlz44n", "water_pump_5v"],
            "required_evidence": ["flyback_or_driver_protection"],
        }
    )

    assert intent.to_dict()["schema_version"] == "hardware_splicer.circuit_synthesis.v1"
    assert CircuitIntent.from_dict(intent.to_dict()).allowed_modules[0] == "esp32-devkit"

    part = FunctionalPart(
        id="pump",
        type="dc_motor",
        module_id="water_pump_5v",
        ports=[
            Port(name="V+", direction="power", signal_type="power", voltage_range={"min_v": 3.0, "max_v": 6.0}),
            Port(name="GND", direction="ground", signal_type="ground"),
        ],
        function_tags=["motor_or_load"],
        behavior_class="inductive_load",
    )
    constraint = Constraint(
        constraint_id="load_current_estimate",
        type="measurement_required",
        target="pump",
        requirement="Measure run/stall current before power-on.",
        status="open",
    )
    topology = TopologyOperator(
        operator_id="pump_low_side_switch",
        operator_type="low_side_switch",
        inputs=["motor_supply", "control_signal", "ground"],
        outputs=["switched_load_return"],
        constraints=[constraint],
    )
    candidate = SynthesisCandidate(
        candidate_id="pump_driver",
        selected_parts=[part.to_dict()],
        selected_modules=["esp32-devkit", "mosfet-irlz44n", "water_pump_5v"],
        generated_topology=[topology],
        constraints=[constraint],
        result="candidate",
    )
    roundtrip = SynthesisCandidate.from_dict(candidate.to_dict())

    assert roundtrip.result == "candidate"
    assert roundtrip.generated_topology[0].operator_type == "low_side_switch"
    assert roundtrip.selected_parts[0]["behavior_class"] == "inductive_load"


def test_circuit_synthesis_ir_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        Port(name="SIG", direction="sideways", signal_type="digital")
    with pytest.raises(ValueError):
        TopologyOperator(operator_id="bad", operator_type="magic")
    with pytest.raises(ValueError):
        SynthesisCandidate(candidate_id="bad", result="production_ready")
