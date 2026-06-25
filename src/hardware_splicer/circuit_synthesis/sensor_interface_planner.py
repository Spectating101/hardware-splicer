"""Bounded sensor/interface hookup planner."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ..pcb.module_registry import find_module
from .common import (
    available_module_ids,
    blocked,
    build_path,
    dedupe,
    first_controller,
    first_power_source,
    has_blocker,
    module_has_role,
    module_input_range,
    module_logic_voltage,
    passed,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


SENSOR_MODULES = {
    "soil_moisture",
    "bme280",
    "dht22",
    "hc-sr04",
    "mpu6050",
    "vl53l0x_tof",
    "mq-2_gas_sensor",
    "ds18b20",
}
DISPLAY_MODULES = {"ssd1306-128x64"}
PULLUP_EVIDENCE = {"i2c_pullups", "pullups_present", "breakout_pullups", "onewire_pullup"}
ANALOG_DIVIDER_EVIDENCE = {"adc_divider", "analog_divider", "voltage_divider", "adc_scaling_verified"}


def plan_sensor_interface(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    evidence = set(circuit_intent.required_evidence)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []

    controller = first_controller(available)
    peripheral = _select_peripheral(available)
    power_source = first_power_source(available)
    level_shifter = "level-shifter-4ch" if "level-shifter-4ch" in available else ""

    selected_modules: List[str] = []
    for module_id in (power_source, controller, peripheral, level_shifter):
        if module_id:
            selected_modules.append(module_id)

    if not controller:
        missing.append("controller_module")
        constraints.append(blocked("controller_module", "evidence_required", "controller", "Provide a known controller/MCU module."))
    if not peripheral:
        missing.append("sensor_or_interface_module")
        constraints.append(blocked("sensor_or_interface_module", "evidence_required", "sensor", "Provide a known sensor/display/interface module."))

    controller_logic_v = module_logic_voltage(controller) if controller else None
    peripheral_logic_v = module_logic_voltage(peripheral) if peripheral else None
    bus = _bus_type(peripheral)
    input_min_v, input_max_v = module_input_range(peripheral) if peripheral else (None, None)
    supply_v = _best_supply_voltage(circuit_intent, controller_logic_v, input_min_v, input_max_v)

    if peripheral:
        if supply_v is None:
            missing.append("sensor_supply_voltage")
            constraints.append(blocked("sensor_supply_voltage", "voltage", peripheral, "Declare or infer sensor supply voltage."))
        elif input_min_v is not None and input_max_v is not None and not (input_min_v <= supply_v <= input_max_v):
            missing.append("sensor_supply_range")
            constraints.append(
                blocked(
                    "sensor_supply_range",
                    "voltage",
                    peripheral,
                    "Sensor supply voltage is outside module input range.",
                    value={"supply_v": supply_v, "min_v": input_min_v, "max_v": input_max_v},
                )
            )
        else:
            constraints.append(
                passed(
                    "sensor_supply_range",
                    "voltage",
                    peripheral,
                    "Sensor supply voltage is inside module input range.",
                    value={"supply_v": supply_v, "min_v": input_min_v, "max_v": input_max_v},
                )
            )

    if bus in {"i2c", "onewire"}:
        if evidence & PULLUP_EVIDENCE:
            constraints.append(passed(f"{bus}_pullups", "evidence_required", peripheral or "sensor", "Required pull-up evidence is present."))
            topology.append(
                TopologyOperator(
                    operator_id=f"{bus}_pullup_network",
                    operator_type="pull_up",
                    inputs=["signal_bus", "logic_rail"],
                    outputs=["defined_idle_level"],
                    required_part_types=["pullup_resistor_or_breakout"],
                    required_ports=["signal", "vcc"],
                    notes="Pull-up may be discrete or part of a breakout; evidence must identify which.",
                )
            )
        else:
            missing.append(f"{bus}_pullups")
            constraints.append(blocked(f"{bus}_pullups", "evidence_required", peripheral or "sensor", f"Provide {bus.upper()} pull-up evidence."))

    if controller_logic_v is not None and peripheral_logic_v is not None and peripheral_logic_v > controller_logic_v + 0.35:
        if level_shifter:
            constraints.append(
                passed(
                    "sensor_logic_level_shift",
                    "logic_level",
                    peripheral,
                    "Level shifter is present for higher-voltage peripheral signals.",
                    value={"controller_logic_v": controller_logic_v, "peripheral_logic_v": peripheral_logic_v},
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="sensor_level_translation",
                    operator_type="level_shifter",
                    inputs=["controller_logic", "sensor_logic", "shared_ground"],
                    outputs=["translated_sensor_bus"],
                    required_part_types=["level_shifter", "sensor", "controller"],
                    required_ports=["LV", "HV", "GND", "LVx", "HVx"],
                    notes="Verify direction and rail references before attaching sensor output.",
                    metadata={"module_id": level_shifter},
                )
            )
        else:
            missing.append("sensor_logic_level_shift")
            constraints.append(
                blocked(
                    "sensor_logic_level_shift",
                    "logic_level",
                    peripheral,
                    "Peripheral logic voltage can exceed controller logic voltage; add level shifting or divider evidence.",
                    value={"controller_logic_v": controller_logic_v, "peripheral_logic_v": peripheral_logic_v},
                )
            )

    if peripheral and module_has_role(peripheral, {"analog_in"}) and supply_v is not None and controller_logic_v is not None and supply_v > controller_logic_v + 0.35:
        if evidence & ANALOG_DIVIDER_EVIDENCE:
            constraints.append(
                passed(
                    "analog_adc_scaling",
                    "voltage",
                    peripheral,
                    "Analog divider/scaling evidence protects the controller ADC input.",
                    value={"sensor_supply_v": supply_v, "controller_logic_v": controller_logic_v},
                )
            )
            topology.append(
                TopologyOperator(
                    operator_id="analog_sensor_divider",
                    operator_type="voltage_divider",
                    inputs=["sensor_analog_output", "ground"],
                    outputs=["adc_safe_signal"],
                    required_part_types=["resistor_divider"],
                    required_ports=["A0", "ADC"],
                    notes="Divider values must be measured or reviewed before power-on.",
                )
            )
        else:
            missing.append("analog_adc_scaling")
            constraints.append(
                blocked(
                    "analog_adc_scaling",
                    "voltage",
                    peripheral,
                    "Analog output may exceed controller ADC range; provide divider/scaling evidence.",
                    value={"sensor_supply_v": supply_v, "controller_logic_v": controller_logic_v},
                )
            )

    if peripheral and controller:
        topology.insert(
            0,
            TopologyOperator(
                operator_id=f"{controller}_{peripheral}_interface",
                operator_type="sensor_interface",
                inputs=["controller_power", "sensor_power", "shared_ground", "signal_bus"],
                outputs=["sensor_reading"],
                required_part_types=["controller", "sensor_or_interface"],
                required_ports=_required_ports_for_bus(bus),
                notes="Sensor interface candidate; bench gates and bus evidence control readiness.",
                metadata={
                    "controller_module": controller,
                    "peripheral_module": peripheral,
                    "bus": bus,
                    "controller_logic_v": controller_logic_v,
                    "peripheral_logic_v": peripheral_logic_v,
                    "supply_v": supply_v,
                },
            ),
        )

    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    return SynthesisCandidate(
        candidate_id="sensor_interface_candidate",
        selected_parts=[
            {
                "id": peripheral or "sensor",
                "type": "sensor_interface",
                "bus": bus,
                "supply_v": supply_v,
                "controller_logic_v": controller_logic_v,
                "peripheral_logic_v": peripheral_logic_v,
            }
        ],
        selected_modules=dedupe(selected_modules),
        generated_topology=topology,
        assumptions=[
            "Candidate is ready for human review only; bus pull-ups, rail references, and first readout must be checked."
            if result == "ready_for_review"
            else "Planner stopped before compile/readiness approval because sensor interface evidence is missing or unsafe."
        ],
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(peripheral=peripheral, bus=bus, supply_v=supply_v),
        recommended_build_path=build_path(available=available, selected=selected_modules),
        result=result,
        notes="Bounded sensor/interface hookup topology plan.",
        metadata={"goal": circuit_intent.goal, "controller": controller, "peripheral": peripheral, "bus": bus},
    )


def _select_peripheral(available: set[str]) -> str:
    for module_id in sorted(available):
        if module_id in SENSOR_MODULES or module_id in DISPLAY_MODULES:
            return module_id
    for module_id in sorted(available):
        spec = find_module(module_id) or {}
        if str(spec.get("category") or "") in {"sensor", "display"}:
            return module_id
    return ""


def _bus_type(module_id: str) -> str:
    if not module_id:
        return "unknown"
    spec = find_module(module_id) or {}
    roles = {str(pin.get("role") or "") for pin in spec.get("pins") or []}
    if {"i2c_sda", "i2c_scl"} <= roles:
        return "i2c"
    if "analog_in" in roles:
        return "analog"
    if "digital_io" in roles:
        if module_id in {"dht22", "ds18b20"}:
            return "onewire"
        return "digital"
    if "digital_out" in roles or "digital_in" in roles:
        return "digital"
    return "unknown"


def _best_supply_voltage(
    intent: CircuitIntent,
    controller_logic_v: float | None,
    input_min_v: float | None,
    input_max_v: float | None,
) -> float | None:
    for row in intent.supply_rails:
        role = str(row.get("name") or row.get("role") or "").lower()
        if any(token in role for token in ("sensor", "peripheral", "vcc", "3v3", "5v")):
            value = _float(row.get("voltage_v") or row.get("sensor_voltage_v") or row.get("peripheral_voltage_v"))
            if value is not None:
                return value
    if controller_logic_v is not None and input_min_v is not None and input_max_v is not None and input_min_v <= controller_logic_v <= input_max_v:
        return controller_logic_v
    if input_min_v is not None and input_max_v is not None:
        if input_min_v <= 3.3 <= input_max_v:
            return 3.3
        if input_min_v <= 5.0 <= input_max_v:
            return 5.0
    return controller_logic_v


def _required_ports_for_bus(bus: str) -> List[str]:
    if bus == "i2c":
        return ["VCC", "GND", "SDA", "SCL"]
    if bus == "onewire":
        return ["VCC", "GND", "DATA"]
    if bus == "analog":
        return ["VCC", "GND", "A0"]
    if bus == "digital":
        return ["VCC", "GND", "SIGNAL"]
    return ["VCC", "GND", "SIGNAL"]


def _verification_gates(*, peripheral: str, bus: str, supply_v: float | None) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "sensor_supply_voltage",
            "gate_type": "dmm_voltage",
            "critical": True,
            "prompt": "Measure sensor VCC and GND before connecting signal pins.",
            "peripheral_module": peripheral,
            "expected_supply_v": supply_v,
            "status": "open",
        },
        {
            "gate_id": "sensor_bus_idle",
            "gate_type": "logic_probe",
            "critical": True,
            "prompt": "Verify bus idle level and no over-voltage at the controller pin.",
            "bus": bus,
            "status": "open",
        },
        {
            "gate_id": "sensor_first_readout",
            "gate_type": "functional_readout",
            "critical": True,
            "prompt": "Capture first plausible sensor reading with timestamp and firmware/log reference.",
            "status": "open",
        },
    ]


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
