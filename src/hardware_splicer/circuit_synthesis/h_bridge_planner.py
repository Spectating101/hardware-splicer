"""Bounded bidirectional DC motor H-bridge topology planner."""

from __future__ import annotations

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
    module_input_range,
    module_logic_voltage,
    passed,
    warned,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


H_BRIDGE_RATINGS_A = {
    "bts7960-motor": 10.0,
    "drv8833-motor": 1.5,
    "tb6612fng-motor": 1.2,
    "l298n": 1.2,
    "l9110-motor": 0.8,
}
H_BRIDGE_LOGIC_MIN_V = {
    "bts7960-motor": 4.5,
    "drv8833-motor": 2.5,
    "tb6612fng-motor": 2.7,
    "l298n": 4.5,
    "l9110-motor": 2.5,
}
H_BRIDGE_MODULES = tuple(H_BRIDGE_RATINGS_A)
MOTOR_LOAD_MODULES = ("dc_motor_3v_6v", "dc_geared_motor_12v", "water_pump_5v", "mini-pump-5v", "cooling_fan_5v")


def plan_h_bridge(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    """Plan a bounded reversible DC motor drive path.

    This handles a common robotics/mechatronics pattern: MCU control plus a
    bidirectional H-bridge module plus a separately powered brushed DC load.
    It intentionally returns review candidates and bench gates, not certified
    motor-control schematics.
    """

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []

    controller = first_controller(available)
    power_source = first_power_source(available)
    load_module = first_available(available, MOTOR_LOAD_MODULES)
    load = _first_load(circuit_intent)
    signal = _first_signal(circuit_intent)
    load_current_a = _load_current(circuit_intent, load)
    load_voltage_v = _load_voltage(circuit_intent, load)
    control_voltage_v = _control_voltage(circuit_intent, signal, controller)
    driver = _choose_driver(available, load_current_a=load_current_a, load_voltage_v=load_voltage_v)

    if not controller:
        missing.append("controller_module")
        constraints.append(blocked("controller_module", "evidence_required", "controller", "Provide a known MCU/controller module."))
    if not load and not load_module:
        missing.append("motor_load")
        constraints.append(blocked("motor_load", "measurement_required", "load", "Declare the reversible DC motor/load."))
    if load_current_a is None:
        missing.append("motor_stall_or_run_current")
        constraints.append(
            blocked(
                "motor_stall_or_run_current",
                "measurement_required",
                "load_current",
                "Provide measured or estimated run/stall current for driver selection.",
            )
        )
    if load_voltage_v is None:
        missing.append("motor_supply_voltage")
        constraints.append(blocked("motor_supply_voltage", "voltage", "motor_supply", "Declare motor supply voltage."))
    if control_voltage_v is None:
        missing.append("control_logic_voltage")
        constraints.append(blocked("control_logic_voltage", "logic_level", "control", "Declare or infer controller logic voltage."))

    if not driver:
        missing.append("h_bridge_driver_module")
        constraints.append(
            blocked(
                "h_bridge_driver_module",
                "current",
                "driver",
                "Provide a known H-bridge module rated for the load current and motor voltage.",
            )
        )
    else:
        _check_driver(driver, load_current_a, load_voltage_v, control_voltage_v, available, constraints, missing)
        topology.append(
            TopologyOperator(
                operator_id=f"{driver}_bidirectional_drive",
                operator_type="h_bridge",
                inputs=["motor_supply", "logic_supply", "direction_pwm_signals", "ground"],
                outputs=["motor_terminal_a", "motor_terminal_b"],
                required_part_types=["h_bridge_driver", "brushed_dc_motor", "controller"],
                required_ports=["VM/VCC", "GND", "IN/PWM", "OUT_A", "OUT_B"],
                notes=f"{driver} selected as bounded H-bridge driver.",
                metadata={
                    "module_id": driver,
                    "current_rating_a": H_BRIDGE_RATINGS_A[driver],
                    "load_current_a": load_current_a,
                    "load_voltage_v": load_voltage_v,
                    "control_voltage_v": control_voltage_v,
                },
            )
        )

    selected_modules = dedupe([power_source, controller, driver, load_module])
    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    return SynthesisCandidate(
        candidate_id="h_bridge_motor_candidate",
        selected_parts=[
            {
                "id": str(load.get("name") or load.get("id") or load_module or "dc_motor"),
                "type": str(load.get("type") or "bidirectional_dc_motor"),
                "voltage_v": load_voltage_v,
                "current_a": load_current_a,
                "requires_direction_control": True,
            }
        ],
        selected_modules=dedupe([driver] if driver else []),
        generated_topology=topology,
        assumptions=[
            "H-bridge candidate is ready for human review only; direction, braking mode, current limiting, and thermal gates must close."
            if result == "ready_for_review"
            else "Planner stopped before compile/readiness approval because motor-drive evidence is missing or incompatible."
        ],
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(load_current_a=load_current_a, load_voltage_v=load_voltage_v),
        recommended_build_path=build_path(
            available=available,
            selected=selected_modules,
            build_id="generic_low_voltage_build",
            notes=[
                "Compile path uses topology terminal semantics so H-bridge motor terminals remain floating, not common-ground pins.",
                "This is bounded topology planning, not certified motor-control design.",
            ],
        ),
        result=result,
        notes="Bounded reversible DC motor H-bridge topology plan.",
        metadata={
            "goal": circuit_intent.goal,
            "controller": controller,
            "power_source": power_source,
            "driver": driver,
            "load_module": load_module,
        },
    )


def _first_load(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.load_requirements:
        kind = str(row.get("type") or row.get("kind") or row.get("name") or "").lower()
        if any(token in kind for token in ("motor", "pump", "fan", "wheel", "drive", "actuator", "load")):
            return dict(row)
    return dict(intent.load_requirements[0]) if intent.load_requirements else {}


def _first_signal(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.signal_requirements:
        kind = str(row.get("type") or row.get("signal_type") or row.get("name") or "").lower()
        if any(token in kind for token in ("pwm", "direction", "gpio", "logic", "control")):
            return dict(row)
    return dict(intent.signal_requirements[0]) if intent.signal_requirements else {}


def _load_current(intent: CircuitIntent, load: Mapping[str, Any]) -> float | None:
    values: List[float] = []
    for row in [load] + list(intent.current_constraints) + list(intent.load_requirements):
        for key in ("stall_current_a", "peak_current_a", "run_current_a", "current_a", "load_current_a"):
            value = first_float(row, (key,))
            if value is not None:
                values.append(value)
    return max(values) if values else None


def _load_voltage(intent: CircuitIntent, load: Mapping[str, Any]) -> float | None:
    for row in [load] + list(intent.supply_rails) + list(intent.voltage_constraints):
        value = first_float(row, ("motor_voltage_v", "load_voltage_v", "voltage_v", "supply_voltage_v"))
        if value is not None:
            return value
    return None


def _control_voltage(intent: CircuitIntent, signal: Mapping[str, Any], controller: str) -> float | None:
    for row in [signal] + list(intent.signal_requirements):
        value = first_float(row, ("control_voltage_v", "logic_voltage_v", "voltage_v", "controller_voltage_v"))
        if value is not None:
            return value
    return module_logic_voltage(controller) if controller else None


def _choose_driver(available: set[str], *, load_current_a: float | None, load_voltage_v: float | None) -> str:
    for module_id in H_BRIDGE_MODULES:
        if module_id not in available:
            continue
        rating = H_BRIDGE_RATINGS_A[module_id]
        min_v, max_v = module_input_range(module_id)
        current_ok = load_current_a is None or rating >= load_current_a * 1.25
        voltage_ok = load_voltage_v is None or min_v is None or max_v is None or min_v <= load_voltage_v <= max_v
        if current_ok and voltage_ok:
            return module_id
    return ""


def _check_driver(
    module_id: str,
    load_current_a: float | None,
    load_voltage_v: float | None,
    control_voltage_v: float | None,
    available: set[str],
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    rating = H_BRIDGE_RATINGS_A[module_id]
    if load_current_a is not None:
        if rating >= load_current_a * 1.25:
            constraints.append(
                passed(
                    "h_bridge_current_margin",
                    "current",
                    module_id,
                    "H-bridge current rating covers estimated run/stall current with margin.",
                    value={"driver_rating_a": rating, "load_current_a": load_current_a},
                )
            )
        else:
            missing.append("h_bridge_current_margin")
            constraints.append(
                blocked(
                    "h_bridge_current_margin",
                    "current",
                    module_id,
                    "H-bridge current rating is below the estimated motor current margin.",
                    value={"driver_rating_a": rating, "load_current_a": load_current_a},
                )
            )
    if module_id == "bts7960-motor" and load_current_a is not None and load_current_a > 5.0:
        constraints.append(
            warned(
                "bts7960_thermal_review",
                "thermal",
                module_id,
                "High-current BTS7960 use needs heatsink/wiring thermal review and short-duty bench validation.",
                value={"load_current_a": load_current_a},
            )
        )
    min_v, max_v = module_input_range(module_id)
    if load_voltage_v is not None and min_v is not None and max_v is not None:
        if min_v <= load_voltage_v <= max_v:
            constraints.append(
                passed(
                    "h_bridge_voltage_range",
                    "voltage",
                    module_id,
                    "Motor supply voltage is inside selected driver range.",
                    value={"load_voltage_v": load_voltage_v, "min_v": min_v, "max_v": max_v},
                )
            )
        else:
            missing.append("h_bridge_voltage_range")
            constraints.append(
                blocked(
                    "h_bridge_voltage_range",
                    "voltage",
                    module_id,
                    "Motor supply voltage is outside selected driver range.",
                    value={"load_voltage_v": load_voltage_v, "min_v": min_v, "max_v": max_v},
                )
            )
    min_logic_v = H_BRIDGE_LOGIC_MIN_V.get(module_id)
    if control_voltage_v is not None and min_logic_v is not None:
        if control_voltage_v >= min_logic_v:
            constraints.append(
                passed(
                    "h_bridge_logic_level",
                    "logic_level",
                    module_id,
                    "Controller logic level can drive selected H-bridge inputs.",
                    value={"control_voltage_v": control_voltage_v, "required_min_v": min_logic_v},
                )
            )
        elif "level-shifter-4ch" in available:
            constraints.append(
                passed(
                    "h_bridge_logic_level_shifted",
                    "logic_level",
                    module_id,
                    "Level-shifter module is available for H-bridge control compatibility.",
                    value={"control_voltage_v": control_voltage_v, "required_min_v": min_logic_v},
                )
            )
        else:
            missing.append("h_bridge_logic_level")
            constraints.append(
                blocked(
                    "h_bridge_logic_level",
                    "logic_level",
                    module_id,
                    "Controller logic level is below selected H-bridge input requirement.",
                    value={"control_voltage_v": control_voltage_v, "required_min_v": min_logic_v},
                )
            )


def _verification_gates(*, load_current_a: float | None, load_voltage_v: float | None) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "h_bridge_no_load_direction_test",
            "gate_type": "bench_check",
            "critical": True,
            "prompt": "With motor disconnected or current-limited, verify forward/reverse control states and brake/coast behavior.",
            "status": "open",
        },
        {
            "gate_id": "h_bridge_current_limit_ramp",
            "gate_type": "psu_ramp",
            "critical": True,
            "prompt": "Ramp motor supply with current limit; record startup and loaded current before sustained operation.",
            "expected_load_current_a": load_current_a,
            "expected_motor_voltage_v": load_voltage_v,
            "status": "open",
        },
        {
            "gate_id": "h_bridge_driver_thermal_scan",
            "gate_type": "thermal",
            "critical": True,
            "prompt": "Capture driver temperature after short forward/reverse runs.",
            "status": "open",
        },
    ]
