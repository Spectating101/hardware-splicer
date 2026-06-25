"""Bounded relay/load-switch topology planner."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping

from .common import (
    available_module_ids,
    blocked,
    build_path,
    dedupe,
    first_available,
    first_controller,
    first_float,
    first_power_source,
    has_blocker,
    module_logic_voltage,
    passed,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


RELAY_MODULES = ("relay-1ch-5v", "relay_module_1ch_5v", "relay_module_4ch_5v")
LOW_VOLTAGE_LOAD_MODULES = ("solenoid_valve_12v", "water_pump_5v", "cooling_fan_5v", "mini-pump-5v")
LOAD_SUPPRESSION_EVIDENCE = {
    "load_suppression",
    "flyback_or_tvs",
    "flyback_diode",
    "rc_snubber",
    "relay_contact_suppression",
}


def plan_relay_switch(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    """Plan a relay-controlled load path with explicit safety boundaries."""

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    evidence = set(circuit_intent.required_evidence)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []

    controller = first_controller(available)
    power_source = first_power_source(available)
    relay = first_available(available, RELAY_MODULES)
    load_module = first_available(available, LOW_VOLTAGE_LOAD_MODULES)
    load = _first_load(circuit_intent)
    load_voltage_v = _load_voltage(circuit_intent, load)
    load_current_a = _load_current(circuit_intent, load)
    controller_logic_v = _control_voltage(circuit_intent, controller)
    hazardous = _hazardous_load(circuit_intent, load_voltage_v)
    inductive = _is_inductive(circuit_intent, load)

    if not controller:
        missing.append("controller_module")
        constraints.append(blocked("controller_module", "evidence_required", "controller", "Provide a known MCU/controller module."))
    if not relay:
        missing.append("relay_module")
        constraints.append(blocked("relay_module", "evidence_required", "relay", "Provide a known relay module."))
    if load_current_a is None:
        missing.append("load_current_estimate")
        constraints.append(blocked("load_current_estimate", "measurement_required", "load", "Declare load current or contact current."))
    if load_voltage_v is None:
        missing.append("load_voltage")
        constraints.append(blocked("load_voltage", "voltage", "load", "Declare switched load voltage."))
    if hazardous:
        missing.append("mains_or_hazardous_load_review")
        constraints.append(
            blocked(
                "mains_or_hazardous_load_review",
                "isolation",
                "load_side",
                "Mains/high-voltage switching is outside this bounded planner; use isolated professional review.",
                value={"load_voltage_v": load_voltage_v},
            )
        )
    elif load_voltage_v is not None:
        constraints.append(
            passed(
                "low_voltage_load_boundary",
                "isolation",
                "load_side",
                "Switched load is inside the low-voltage review boundary.",
                value={"load_voltage_v": load_voltage_v},
            )
        )

    if relay:
        constraints.append(
            passed(
                "relay_contact_current_review",
                "current",
                relay,
                "Relay module selected; contact current still requires datasheet/human review before power-on.",
                value={"load_current_a": load_current_a},
            )
        )
        if controller_logic_v is not None and controller_logic_v >= 3.0:
            constraints.append(
                passed(
                    "relay_logic_drive",
                    "logic_level",
                    relay,
                    "Controller logic level is plausible for common opto-isolated relay input modules.",
                    value={"controller_logic_v": controller_logic_v},
                )
            )
        else:
            missing.append("relay_logic_drive_voltage")
            constraints.append(
                blocked(
                    "relay_logic_drive",
                    "logic_level",
                    relay,
                    "Declare controller logic voltage for relay input compatibility.",
                    value={"controller_logic_v": controller_logic_v},
                )
            )
        topology.append(
            TopologyOperator(
                operator_id=f"{relay}_load_switch",
                operator_type="relay_driver",
                inputs=["logic_control", "relay_coil_supply", "load_supply", "load_common"],
                outputs=["switched_load_no_or_nc"],
                required_part_types=["relay_module", "controller", "load"],
                required_ports=["VCC", "GND", "IN", "COM", "NO/NC"],
                notes="Relay candidate; contact/load side remains physically isolated from controller side.",
                metadata={"module_id": relay, "load_voltage_v": load_voltage_v, "load_current_a": load_current_a},
            )
        )

    if inductive:
        if evidence & LOAD_SUPPRESSION_EVIDENCE:
            constraints.append(
                passed(
                    "relay_inductive_suppression",
                    "protection",
                    "load",
                    "Inductive load suppression evidence is present.",
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="relay_load_suppression",
                    operator_type="protection_diode",
                    inputs=["load_positive", "load_return"],
                    outputs=["clamped_load_transient"],
                    required_part_types=["flyback_diode_or_tvs_or_snubber"],
                    required_ports=["load+", "load-"],
                    notes="Suppression placement depends on DC/AC load type and must be reviewed.",
                )
            )
        else:
            missing.append("load_suppression")
            constraints.append(
                blocked(
                    "relay_inductive_suppression",
                    "protection",
                    "load",
                    "Relay switching of inductive loads needs flyback/TVS/snubber evidence.",
                )
            )

    selected_modules = dedupe([power_source, controller, relay, load_module])
    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    return SynthesisCandidate(
        candidate_id="relay_switch_candidate",
        selected_parts=[
            {
                "id": str(load.get("name") or load.get("id") or load_module or "switched_load"),
                "type": str(load.get("type") or "relay_switched_load"),
                "voltage_v": load_voltage_v,
                "current_a": load_current_a,
                "inductive": inductive,
                "hazardous_load": hazardous,
            }
        ],
        selected_modules=dedupe([relay] if relay else []),
        generated_topology=topology,
        assumptions=[
            "Relay candidate is ready for human review only; contact wiring, isolation, suppression, and first-power gates must close."
            if result == "ready_for_review"
            else "Planner stopped before compile/readiness approval because relay/load evidence is missing or unsafe."
        ],
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(load_voltage_v=load_voltage_v, load_current_a=load_current_a, inductive=inductive),
        recommended_build_path=build_path(
            available=available,
            selected=selected_modules,
            build_id="generic_low_voltage_build",
            notes=[
                "Relay contacts and external load wiring require human review; this compile path only captures low-voltage control wiring.",
                "Mains/high-voltage switching remains blocked by this bounded planner.",
            ],
        ),
        result=result,
        notes="Bounded relay/load-switch topology plan.",
        metadata={
            "goal": circuit_intent.goal,
            "controller": controller,
            "power_source": power_source,
            "relay": relay,
            "load_module": load_module,
            "hazardous_load": hazardous,
        },
    )


def _first_load(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.load_requirements:
        kind = str(row.get("type") or row.get("kind") or row.get("name") or "").lower()
        if any(token in kind for token in ("relay", "solenoid", "valve", "lamp", "load", "fan", "pump")):
            return dict(row)
    return dict(intent.load_requirements[0]) if intent.load_requirements else {}


def _load_voltage(intent: CircuitIntent, load: Mapping[str, Any]) -> float | None:
    for row in [load] + list(intent.voltage_constraints) + list(intent.supply_rails):
        value = first_float(row, ("load_voltage_v", "switched_voltage_v", "voltage_v", "supply_voltage_v"))
        if value is not None:
            return value
    text = f"{intent.goal} {intent.notes}".lower()
    match = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*v(?:ac|dc)?\b", text)
    return float(match.group(1)) if match else None


def _load_current(intent: CircuitIntent, load: Mapping[str, Any]) -> float | None:
    for row in [load] + list(intent.current_constraints) + list(intent.load_requirements):
        value = first_float(row, ("load_current_a", "current_a", "contact_current_a", "run_current_a"))
        if value is not None:
            return value
    return None


def _control_voltage(intent: CircuitIntent, controller: str) -> float | None:
    for row in intent.signal_requirements:
        value = first_float(row, ("control_voltage_v", "logic_voltage_v", "voltage_v", "controller_voltage_v"))
        if value is not None:
            return value
    return module_logic_voltage(controller) if controller else None


def _hazardous_load(intent: CircuitIntent, load_voltage_v: float | None) -> bool:
    text = f"{intent.goal} {intent.notes} {' '.join(str(row) for row in intent.load_requirements)}".lower()
    if any(token in text for token in ("mains", "110vac", "120vac", "220vac", "230vac", "240vac", "ac line", "wall power")):
        return True
    return load_voltage_v is not None and load_voltage_v > 60.0


def _is_inductive(intent: CircuitIntent, load: Mapping[str, Any]) -> bool:
    text = f"{intent.goal} {intent.notes} {load}".lower()
    return any(token in text for token in ("solenoid", "valve", "motor", "pump", "fan", "inductive", "coil", "relay coil"))


def _verification_gates(*, load_voltage_v: float | None, load_current_a: float | None, inductive: bool) -> List[Dict[str, Any]]:
    gates = [
        {
            "gate_id": "relay_coil_current_check",
            "gate_type": "dmm_current",
            "critical": True,
            "prompt": "Measure relay coil/input current and verify controller-side supply does not sag.",
            "status": "open",
        },
        {
            "gate_id": "relay_contact_continuity_check",
            "gate_type": "continuity",
            "critical": True,
            "prompt": "Verify COM/NO/NC behavior with load supply disconnected.",
            "status": "open",
        },
        {
            "gate_id": "relay_low_voltage_first_power",
            "gate_type": "psu_ramp",
            "critical": True,
            "prompt": "First-power switched load with current limit and low-voltage supply before any field wiring.",
            "expected_load_voltage_v": load_voltage_v,
            "expected_load_current_a": load_current_a,
            "status": "open",
        },
    ]
    if inductive:
        gates.append(
            {
                "gate_id": "relay_inductive_suppression_inspection",
                "gate_type": "bench_check",
                "critical": True,
                "prompt": "Confirm flyback/TVS/snubber installation and polarity before switching the inductive load.",
                "status": "open",
            }
        )
    return gates
