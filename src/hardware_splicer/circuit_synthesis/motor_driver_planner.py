"""Bounded motor/pump driver topology planner."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from ..pcb.module_registry import find_module
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


MOTOR_DRIVER_RATINGS_A = {
    "l298n": 1.2,
}
MOTOR_DRIVER_LOGIC_MIN_V = {
    "l298n": 4.5,
}
MOTOR_DRIVER_HAS_PROTECTION = {
    "l298n": True,
}
MOSFET_RATINGS_A = {
    "mosfet-irlz44n": 5.0,
    "mosfet-irf520": 1.0,
}
MOSFET_LOGIC_MIN_V = {
    "mosfet-irlz44n": 3.0,
    "mosfet-irf520": 4.5,
}
POWER_SOURCE_CURRENT_A = {
    "usb-power-5v": 0.9,
    "dc-barrel-12v": 2.0,
    "buck-mp1584": 3.0,
    "buck-lm2596": 3.0,
}
MCU_MODULE_IDS = {"esp32-devkit", "arduino-nano", "rpi-pico"}
LOAD_MODULE_IDS = {"water_pump_5v", "mini-pump-5v", "cooling_fan_5v"}
PROTECTION_EVIDENCE = {
    "flyback_or_driver_protection",
    "flyback_or_tvs",
    "protection_diode",
    "driver_integrated_clamp",
}
PROTECTION_MODULE_IDS = {"flyback-diode", "protection-diode", "diode-1n5819", "tvs-diode"}
LEVEL_SHIFTER_MODULE_IDS = {"level-shifter-4ch"}


def plan_motor_driver(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    """Plan one bounded DC motor/pump driver topology.

    The planner never emits a production-ready claim. It produces a candidate,
    blocked candidate, or ready-for-review candidate with explicit constraints
    and bench gates for the existing Hardware-Splicer authority path.
    """

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = _available_module_ids(circuit_intent)
    evidence = set(circuit_intent.required_evidence)
    evidence.update(str(row.get("id") or row.get("type") or "") for row in circuit_intent.allowed_parts if row.get("evidence"))

    load = _first_load(circuit_intent)
    signal = _first_signal(circuit_intent)
    supply = _first_supply(circuit_intent, available)
    constraints: List[Constraint] = []
    assumptions: List[str] = []
    missing: List[str] = []
    selected_modules: List[str] = []
    selected_parts: List[Dict[str, Any]] = []
    topology: List[TopologyOperator] = []

    load_current_a = _float_or_none(load.get("current_a") or load.get("run_current_a") or load.get("stall_current_a"))
    load_voltage_v = _float_or_none(load.get("voltage_v")) or _float_or_none(supply.get("voltage_v"))
    control_voltage_v = _float_or_none(signal.get("voltage_v"))
    supply_current_a = _float_or_none(supply.get("max_current_a") or supply.get("current_limit_a"))

    if not load:
        missing.append("load_requirement")
        constraints.append(_blocked("load_requirement", "measurement_required", "load", "Declare the motor/pump load."))
    if load and load_current_a is None:
        missing.append("load_current_estimate")
        constraints.append(_blocked("load_current_estimate", "measurement_required", "load_current", "Measure or estimate motor run/stall current."))
    if not supply:
        missing.append("supply_rail")
        constraints.append(_blocked("supply_rail", "voltage", "supply", "Declare the motor supply rail."))
    if supply and supply_current_a is None:
        missing.append("supply_current_limit")
        constraints.append(_blocked("supply_current_limit", "current", "supply", "Declare supply current limit."))
    if not signal:
        missing.append("control_signal")
        constraints.append(_blocked("control_signal", "logic_level", "control", "Declare MCU control voltage."))
    if signal and control_voltage_v is None:
        missing.append("control_signal_voltage")
        constraints.append(_blocked("control_signal_voltage", "logic_level", "control", "Declare MCU control voltage."))

    if load_current_a is not None and supply_current_a is not None:
        if supply_current_a < load_current_a:
            missing.append("supply_current_margin")
            constraints.append(
                _blocked(
                    "supply_current_margin",
                    "current",
                    "supply",
                    "Supply current limit must exceed estimated load current.",
                    value={"supply_current_a": supply_current_a, "load_current_a": load_current_a},
                )
            )
        else:
            constraints.append(
                _passed(
                    "supply_current_margin",
                    "current",
                    "supply",
                    "Supply current limit covers estimated load current.",
                    value={"supply_current_a": supply_current_a, "load_current_a": load_current_a},
                )
            )

    driver_id = _choose_driver(available, load_current_a)
    mosfet_id = "" if driver_id else _choose_mosfet(available, load_current_a)

    if driver_id:
        selected_modules.append(driver_id)
        rating = MOTOR_DRIVER_RATINGS_A[driver_id]
        topology.append(
            TopologyOperator(
                operator_id=f"{driver_id}_motor_driver",
                operator_type="motor_driver",
                inputs=["motor_supply", "control_signal", "ground"],
                outputs=["motor_out_a", "motor_out_b"],
                required_part_types=["motor_driver", "dc_motor_or_pump"],
                required_ports=["VCC", "GND", "IN1", "IN2", "OUT1", "OUT2"],
                notes=f"{driver_id} selected as bounded motor-driver module.",
                metadata={"current_rating_a": rating, "module_id": driver_id},
            )
        )
        constraints.append(
            _passed(
                "driver_current_rating",
                "current",
                driver_id,
                "Driver current rating covers estimated load current.",
                value={"driver_current_rating_a": rating, "load_current_a": load_current_a},
            )
        )
        _check_logic_level(driver_id, MOTOR_DRIVER_LOGIC_MIN_V.get(driver_id), control_voltage_v, available, constraints, missing)
    elif mosfet_id:
        selected_modules.append(mosfet_id)
        rating = MOSFET_RATINGS_A[mosfet_id]
        topology.append(
            TopologyOperator(
                operator_id=f"{mosfet_id}_low_side_switch",
                operator_type="low_side_switch",
                inputs=["motor_supply", "control_signal", "ground"],
                outputs=["switched_load_return"],
                required_part_types=["logic_level_mosfet", "dc_motor_or_pump"],
                required_ports=["VIN", "VIN-", "SIG", "GND", "VOUT+", "VOUT-"],
                missing_evidence_conditions=["flyback_or_driver_protection"],
                notes=f"{mosfet_id} selected as bounded low-side switch module.",
                metadata={"current_rating_a": rating, "module_id": mosfet_id},
            )
        )
        constraints.append(
            _passed(
                "switch_current_rating",
                "current",
                mosfet_id,
                "Switch current rating covers estimated load current.",
                value={"switch_current_rating_a": rating, "load_current_a": load_current_a},
            )
        )
        _check_logic_level(mosfet_id, MOSFET_LOGIC_MIN_V.get(mosfet_id), control_voltage_v, available, constraints, missing)
    else:
        missing.append("driver_topology")
        constraints.append(_blocked("driver_topology", "current", "driver", "Provide a rated motor driver or logic-level MOSFET switch."))

    if load:
        selected_parts.append(
            {
                "id": str(load.get("name") or load.get("id") or "load"),
                "type": str(load.get("type") or "dc_motor"),
                "voltage_v": load_voltage_v,
                "current_a": load_current_a,
                "inductive": _load_is_inductive(load),
            }
        )
    if signal:
        selected_parts.append(
            {
                "id": str(signal.get("name") or signal.get("id") or "control"),
                "type": str(signal.get("type") or "pwm"),
                "voltage_v": control_voltage_v,
            }
        )

    if _load_is_inductive(load) and not (driver_id and MOTOR_DRIVER_HAS_PROTECTION.get(driver_id)):
        has_protection = bool(PROTECTION_MODULE_IDS & available or PROTECTION_EVIDENCE & evidence)
        if has_protection:
            constraints.append(
                _passed(
                    "inductive_load_protection",
                    "protection",
                    "load",
                    "Inductive load protection evidence/module is present.",
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="flyback_or_tvs_protection",
                    operator_type="protection_diode",
                    inputs=["load_positive", "switched_load_return"],
                    outputs=["clamped_inductive_spike"],
                    required_part_types=["diode_or_tvs"],
                    required_ports=["anode", "cathode"],
                    notes="Protection must be physically confirmed before power-on.",
                )
            )
        else:
            missing.append("flyback_or_driver_protection")
            constraints.append(
                _blocked(
                    "inductive_load_protection",
                    "protection",
                    "load",
                    "Inductive motor/pump load needs flyback, TVS, or integrated driver protection evidence.",
                )
            )

    gates = _verification_gates(load_current_a=load_current_a, supply_current_a=supply_current_a)
    result = "blocked" if missing or any(c.status == "blocked" for c in constraints) else "ready_for_review"
    if result == "ready_for_review":
        assumptions.append("Candidate is ready for human review only; bench gates must close before first power-on.")
    else:
        assumptions.append("Planner stopped before compile/readiness approval because required evidence is missing.")

    modules_for_build = _recommended_module_ids(available, selected_modules)
    return SynthesisCandidate(
        candidate_id="motor_pump_driver_candidate",
        selected_parts=selected_parts,
        selected_modules=_dedupe(selected_modules),
        generated_topology=topology,
        assumptions=assumptions,
        missing_evidence=_dedupe(missing),
        constraints=constraints,
        verification_gates=gates,
        recommended_build_path={
            "build_id": "generic_low_voltage_build",
            "compose_mode": "module_graph_candidate",
            "module_ids": modules_for_build,
            "can_compile_with_existing_auto_wire": len([m for m in modules_for_build if find_module(m)]) >= 2,
            "notes": [
                "Use compose_dispatch only after blocked constraints are resolved.",
                "This candidate is topology planning, not certified schematic synthesis.",
            ],
        },
        result=result,
        notes="Bounded DC motor/pump driver topology plan.",
        metadata={
            "goal": circuit_intent.goal,
            "supply": supply,
            "load": load,
            "signal": signal,
        },
    )


def _available_module_ids(intent: CircuitIntent) -> set[str]:
    ids = set(intent.allowed_modules)
    for row in intent.allowed_parts:
        for key in ("module_id", "id"):
            mid = str(row.get(key) or "").strip()
            if mid and find_module(mid):
                ids.add(mid)
    return ids


def _first_load(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.load_requirements:
        kind = str(row.get("type") or row.get("kind") or "").lower()
        if any(token in kind for token in ("motor", "pump", "fan", "solenoid", "load")):
            return dict(row)
    return dict(intent.load_requirements[0]) if intent.load_requirements else {}


def _first_signal(intent: CircuitIntent) -> Dict[str, Any]:
    for row in intent.signal_requirements:
        kind = str(row.get("type") or row.get("signal_type") or "").lower()
        if kind in {"pwm", "digital", "gpio", "logic"}:
            return dict(row)
    return dict(intent.signal_requirements[0]) if intent.signal_requirements else {}


def _first_supply(intent: CircuitIntent, available: set[str]) -> Dict[str, Any]:
    if intent.supply_rails:
        return dict(intent.supply_rails[0])
    for module_id in available:
        if module_id in POWER_SOURCE_CURRENT_A:
            spec = find_module(module_id) or {}
            voltage_v = None
            input_range = spec.get("inputVoltageRange")
            if isinstance(input_range, list) and input_range:
                voltage_v = input_range[-1]
            if module_id == "usb-power-5v":
                voltage_v = 5.0
            if module_id == "dc-barrel-12v":
                voltage_v = 12.0
            return {
                "name": module_id,
                "voltage_v": voltage_v,
                "max_current_a": POWER_SOURCE_CURRENT_A[module_id],
                "source": "module_default",
            }
    return {}


def _choose_driver(available: set[str], load_current_a: float | None) -> str:
    for module_id, rating in MOTOR_DRIVER_RATINGS_A.items():
        if module_id in available and (load_current_a is None or rating >= load_current_a * 1.25):
            return module_id
    return ""


def _choose_mosfet(available: set[str], load_current_a: float | None) -> str:
    for module_id in ("mosfet-irlz44n", "mosfet-irf520"):
        rating = MOSFET_RATINGS_A[module_id]
        if module_id in available and (load_current_a is None or rating >= load_current_a * 1.25):
            return module_id
    return ""


def _check_logic_level(
    module_id: str,
    min_voltage_v: float | None,
    control_voltage_v: float | None,
    available: set[str],
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    if min_voltage_v is None or control_voltage_v is None:
        return
    if control_voltage_v + 1e-9 >= min_voltage_v:
        constraints.append(
            _passed(
                f"{module_id}_logic_level",
                "logic_level",
                module_id,
                "Control signal voltage meets selected driver/switch input requirement.",
                value={"control_voltage_v": control_voltage_v, "required_min_v": min_voltage_v},
            )
        )
        return
    if LEVEL_SHIFTER_MODULE_IDS & available:
        constraints.append(
            _passed(
                f"{module_id}_logic_level_shifted",
                "logic_level",
                module_id,
                "Level shifter module is available for control-signal compatibility.",
                value={"control_voltage_v": control_voltage_v, "required_min_v": min_voltage_v},
            )
        )
        return
    missing.append("level_shifter_or_compatible_driver")
    constraints.append(
        _blocked(
            f"{module_id}_logic_level",
            "logic_level",
            module_id,
            "Control signal voltage is below selected driver/switch input requirement.",
            value={"control_voltage_v": control_voltage_v, "required_min_v": min_voltage_v},
        )
    )


def _load_is_inductive(load: Mapping[str, Any]) -> bool:
    kind = str(load.get("type") or load.get("kind") or "").lower()
    if not kind:
        return True
    return any(token in kind for token in ("motor", "pump", "fan", "solenoid", "inductive"))


def _verification_gates(*, load_current_a: float | None, supply_current_a: float | None) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "psu_current_limit_ramp",
            "gate_type": "psu_ramp",
            "critical": True,
            "prompt": "Ramp motor supply with current limit set below expected fault current; record voltage/current at each step.",
            "expected_load_current_a": load_current_a,
            "supply_current_limit_a": supply_current_a,
            "status": "open",
        },
        {
            "gate_id": "thermal_baseline_scan",
            "gate_type": "thermal",
            "critical": True,
            "prompt": "Capture thermal baseline at idle and under brief load before enclosing or sustained operation.",
            "status": "open",
        },
        {
            "gate_id": "inductive_protection_inspection",
            "gate_type": "bench_check",
            "critical": True,
            "prompt": "Confirm flyback/TVS/integrated driver protection path for motor or pump load.",
            "status": "open",
        },
    ]


def _recommended_module_ids(available: set[str], selected: Sequence[str]) -> List[str]:
    out: List[str] = []
    for group in (POWER_SOURCE_CURRENT_A.keys(), MCU_MODULE_IDS, selected, LOAD_MODULE_IDS, LEVEL_SHIFTER_MODULE_IDS):
        for module_id in group:
            if module_id in available:
                out.append(module_id)
                break
    for module_id in selected:
        out.append(module_id)
    return _dedupe(out)


def _passed(
    constraint_id: str,
    type: str,
    target: str,
    requirement: str,
    *,
    value: Any = None,
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        type=type,
        target=target,
        requirement=requirement,
        status="pass",
        value=value,
    )


def _blocked(
    constraint_id: str,
    type: str,
    target: str,
    requirement: str,
    *,
    value: Any = None,
) -> Constraint:
    return Constraint(
        constraint_id=constraint_id,
        type=type,
        target=target,
        requirement=requirement,
        status="blocked",
        value=value,
    )


def _dedupe(rows: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for row in rows:
        text = str(row or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
