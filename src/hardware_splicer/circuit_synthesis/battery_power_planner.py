"""Bounded single-cell battery/charger power-path planner."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from .common import (
    available_module_ids,
    blocked,
    build_path,
    dedupe,
    first_available,
    first_float,
    has_blocker,
    module_current_limit_a,
    module_input_range,
    passed,
    warned,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


CHARGER_MODULES = ("tp4056",)
BOOST_MODULES = ("boost-mt3608",)
LDO_MODULES = ("ldo-ams1117-3v3", "ldo-ams1117-5v")
BUCK_MODULES = ("buck-mp1584", "buck-lm2596")
USB_INPUT_MODULES = ("usb-power-5v",)
FUEL_GAUGE_MODULES = ("lc709203f-fuel-gauge",)
PROTECTION_EVIDENCE = {
    "protected_cell",
    "protected_lipo",
    "protected_liion",
    "battery_protection_board",
    "tp4056_protected_version",
    "dw01_protection_present",
}


def plan_battery_power(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    """Plan a bounded single-cell Li-ion/LiPo charger and output rail."""

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    evidence = set(circuit_intent.required_evidence)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []

    usb_input = first_available(available, USB_INPUT_MODULES)
    charger = first_available(available, CHARGER_MODULES)
    fuel_gauge = first_available(available, FUEL_GAUGE_MODULES)
    target_output_v = _target_output_voltage(circuit_intent)
    load_current_a = _load_current(circuit_intent)
    cell_capacity_mah = _cell_capacity(circuit_intent)
    regulator = _choose_output_regulator(available, target_output_v=target_output_v, load_current_a=load_current_a)

    if not usb_input:
        missing.append("usb_charge_input")
        constraints.append(blocked("usb_charge_input", "evidence_required", "charger_input", "Provide a known 5V charge input module."))
    if not charger:
        missing.append("single_cell_charger_module")
        constraints.append(blocked("single_cell_charger_module", "evidence_required", "charger", "Provide a known single-cell charger/protection module."))
    if not (evidence & PROTECTION_EVIDENCE):
        missing.append("battery_protection_evidence")
        constraints.append(
            blocked(
                "battery_protection_evidence",
                "protection",
                "li_ion_cell",
                "Li-ion/LiPo use requires protected cell or protection-board evidence before planning power-on.",
            )
        )
    else:
        constraints.append(
            passed(
                "battery_protection_evidence",
                "protection",
                "li_ion_cell",
                "Battery protection evidence is present.",
            )
        )
    if load_current_a is None:
        missing.append("battery_load_current")
        constraints.append(blocked("battery_load_current", "measurement_required", "load", "Declare expected output/load current."))
    if target_output_v is None:
        missing.append("target_output_voltage")
        constraints.append(blocked("target_output_voltage", "voltage", "output_rail", "Declare target output voltage."))
    if cell_capacity_mah is None:
        constraints.append(
            warned(
                "cell_capacity_runtime_unknown",
                "current",
                "cell",
                "Runtime and charge-rate review need cell capacity; planner can continue but cannot estimate runtime.",
            )
        )
    elif cell_capacity_mah < 500:
        constraints.append(
            warned(
                "cell_capacity_low",
                "current",
                "cell",
                "Small cell capacity may be unsuitable for high-current loads; bench/runtime review required.",
                value={"cell_capacity_mah": cell_capacity_mah},
            )
        )

    if charger:
        topology.append(
            TopologyOperator(
                operator_id=f"{charger}_single_cell_charge_path",
                operator_type="battery_charger",
                inputs=["usb_5v", "ground", "single_cell_battery"],
                outputs=["battery_voltage_rail"],
                required_part_types=["charger_module", "protected_single_cell_battery"],
                required_ports=["IN+", "IN-", "BAT+", "BAT-", "OUT+", "OUT-"],
                notes="TP4056 charge path candidate; protected version or external protection evidence is mandatory.",
                metadata={"module_id": charger, "nominal_cell_v": 3.7, "full_cell_v": 4.2},
            )
        )

    if target_output_v is not None:
        if target_output_v > 4.3:
            if regulator and regulator in BOOST_MODULES:
                _check_regulator(regulator, target_output_v, load_current_a, constraints, missing)
                topology.append(_regulator_operator(regulator, "boost_regulator", target_output_v, load_current_a))
            else:
                missing.append("boost_regulator_module")
                constraints.append(
                    blocked(
                        "boost_regulator_module",
                        "voltage",
                        "output_rail",
                        "Single-cell battery needs a boost regulator for target output above 4.2V.",
                        value={"target_output_v": target_output_v},
                    )
                )
        elif target_output_v <= 3.4:
            if regulator:
                _check_regulator(regulator, target_output_v, load_current_a, constraints, missing)
                op_type = "ldo_regulator" if regulator in LDO_MODULES else "buck_regulator"
                topology.append(_regulator_operator(regulator, op_type, target_output_v, load_current_a))
            else:
                missing.append("3v3_regulator_module")
                constraints.append(
                    blocked(
                        "3v3_regulator_module",
                        "voltage",
                        "output_rail",
                        "Provide a 3.3V regulator for stable logic from a single-cell battery.",
                        value={"target_output_v": target_output_v},
                    )
                )
        else:
            constraints.append(
                passed(
                    "raw_battery_voltage_range",
                    "voltage",
                    "output_rail",
                    "Target can be reviewed as raw single-cell battery rail.",
                    value={"target_output_v": target_output_v, "cell_range_v": [3.0, 4.2]},
                )
            )

    if fuel_gauge:
        topology.append(
            TopologyOperator(
                operator_id=f"{fuel_gauge}_battery_monitor",
                operator_type="sensor_interface",
                inputs=["battery_voltage", "i2c_bus", "ground"],
                outputs=["state_of_charge_estimate"],
                required_part_types=["fuel_gauge", "controller"],
                required_ports=["VCC", "GND", "SDA", "SCL"],
                notes="Fuel gauge is optional instrumentation; it does not replace protection evidence.",
                metadata={"module_id": fuel_gauge},
            )
        )

    selected_modules = dedupe([usb_input, charger, regulator, fuel_gauge])
    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    return SynthesisCandidate(
        candidate_id="battery_power_candidate",
        selected_parts=[
            {
                "id": "single_cell_battery_power_path",
                "type": "battery_power",
                "chemistry": "single_cell_li_ion_or_lipo",
                "target_output_v": target_output_v,
                "load_current_a": load_current_a,
                "cell_capacity_mah": cell_capacity_mah,
            }
        ],
        selected_modules=dedupe([module_id for module_id in (charger, regulator, fuel_gauge) if module_id]),
        generated_topology=topology,
        assumptions=[
            "Battery power candidate is ready for human review only; charge/protection and loaded-rail gates must close before use."
            if result == "ready_for_review"
            else "Planner stopped before compile/readiness approval because battery safety or rail evidence is missing."
        ],
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(target_output_v=target_output_v, load_current_a=load_current_a),
        recommended_build_path=build_path(
            available=available,
            selected=selected_modules,
            build_id="generic_low_voltage_build",
            notes=[
                "Compile path captures known charger/regulator modules only; battery cell and protection are evidence gates.",
                "Never close this candidate from model output alone.",
            ],
        ),
        result=result,
        notes="Bounded single-cell battery/charger power topology plan.",
        metadata={"goal": circuit_intent.goal, "charger": charger, "regulator": regulator, "fuel_gauge": fuel_gauge},
    )


def _target_output_voltage(intent: CircuitIntent) -> float | None:
    for row in intent.voltage_constraints + intent.supply_rails + intent.load_requirements:
        value = first_float(row, ("target_output_v", "output_voltage_v", "required_voltage_v", "voltage_v"))
        if value is not None:
            return value
    text = f"{intent.goal} {intent.notes}".lower()
    if "3v3" in text or "3.3v" in text or "3.3 v" in text:
        return 3.3
    if "5v" in text or "5 v" in text:
        return 5.0
    return None


def _load_current(intent: CircuitIntent) -> float | None:
    for row in intent.current_constraints + intent.load_requirements + intent.voltage_constraints:
        value = first_float(row, ("load_current_a", "current_a", "max_current_a", "required_current_a"))
        if value is not None:
            return value
    return None


def _cell_capacity(intent: CircuitIntent) -> float | None:
    for row in intent.supply_rails + intent.allowed_parts:
        value = first_float(row, ("capacity_mah", "cell_capacity_mah", "battery_capacity_mah"))
        if value is not None:
            return value
    return None


def _choose_output_regulator(available: set[str], *, target_output_v: float | None, load_current_a: float | None) -> str:
    if target_output_v is None:
        return ""
    if target_output_v > 4.3:
        return first_available(available, BOOST_MODULES)
    if target_output_v <= 3.4:
        if load_current_a is not None and load_current_a <= 0.25:
            ldo = first_available(available, ("ldo-ams1117-3v3",))
            if ldo:
                return ldo
        return first_available(available, ("buck-mp1584", "buck-lm2596", "ldo-ams1117-3v3"))
    return ""


def _check_regulator(
    module_id: str,
    target_output_v: float | None,
    load_current_a: float | None,
    constraints: List[Constraint],
    missing: List[str],
) -> None:
    min_in, max_in = module_input_range(module_id)
    if min_in is not None and max_in is not None:
        constraints.append(
            passed(
                f"{module_id}_battery_input_range",
                "voltage",
                module_id,
                "Single-cell battery voltage can feed selected regulator input range for review.",
                value={"battery_range_v": [3.0, 4.2], "min_in_v": min_in, "max_in_v": max_in},
            )
        )
    current_limit_a = module_current_limit_a(module_id, default_a=2.0 if module_id in BOOST_MODULES else 1.0)
    if load_current_a is not None and current_limit_a is not None:
        if current_limit_a >= load_current_a * 1.25:
            constraints.append(
                passed(
                    f"{module_id}_current_margin",
                    "current",
                    module_id,
                    "Regulator output current rating covers expected load with margin.",
                    value={"current_limit_a": current_limit_a, "load_current_a": load_current_a},
                )
            )
        else:
            missing.append("battery_regulator_current_margin")
            constraints.append(
                blocked(
                    f"{module_id}_current_margin",
                    "current",
                    module_id,
                    "Regulator output current rating is too close to or below expected load.",
                    value={"current_limit_a": current_limit_a, "load_current_a": load_current_a},
                )
            )
    if target_output_v is not None:
        constraints.append(
            passed(
                f"{module_id}_target_output_review",
                "voltage",
                module_id,
                "Selected regulator can be reviewed/set for target output rail.",
                value={"target_output_v": target_output_v},
            )
        )


def _regulator_operator(module_id: str, op_type: str, target_output_v: float | None, load_current_a: float | None) -> TopologyOperator:
    return TopologyOperator(
        operator_id=f"{module_id}_battery_output_rail",
        operator_type=op_type,
        inputs=["battery_voltage_rail", "ground"],
        outputs=["regulated_output_rail"],
        required_part_types=["regulator_module", "battery_power_path"],
        required_ports=["IN+", "IN-", "OUT+", "OUT-"],
        notes=f"{module_id} selected for battery output rail conversion.",
        metadata={"module_id": module_id, "target_output_v": target_output_v, "load_current_a": load_current_a},
    )


def _verification_gates(*, target_output_v: float | None, load_current_a: float | None) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "battery_protection_inspection",
            "gate_type": "bench_check",
            "critical": True,
            "prompt": "Confirm protected cell/protection-board presence, polarity, and charger variant before connecting the cell.",
            "status": "open",
        },
        {
            "gate_id": "charger_input_current_check",
            "gate_type": "dmm_current",
            "critical": True,
            "prompt": "Measure charge input current and verify USB source/cable rating.",
            "status": "open",
        },
        {
            "gate_id": "battery_output_loaded_rail",
            "gate_type": "dmm_voltage_current",
            "critical": True,
            "prompt": "Measure output rail under expected load before attaching downstream electronics.",
            "expected_output_v": target_output_v,
            "expected_load_current_a": load_current_a,
            "status": "open",
        },
    ]
