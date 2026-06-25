"""Bounded logic-level translation planner."""

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
    float_or_none,
    has_blocker,
    module_logic_voltage,
    passed,
    warned,
)
from .ir import CircuitIntent, Constraint, SynthesisCandidate, TopologyOperator


LEVEL_SHIFTER_MODULES = ("level-shifter-4ch",)


def plan_level_shift(intent: CircuitIntent | Mapping[str, Any]) -> SynthesisCandidate:
    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    available = available_module_ids(circuit_intent)
    constraints: List[Constraint] = []
    missing: List[str] = []
    topology: List[TopologyOperator] = []

    controller = first_controller(available)
    peer = _peer_module(available, controller)
    low_v, high_v = _logic_pair(circuit_intent, controller, peer)
    channel_count = _channel_count(circuit_intent)
    shifter = _available_shifter(available)

    selected_modules: List[str] = []
    power_source = first_power_source(available)
    if power_source:
        selected_modules.append(power_source)
    if controller:
        selected_modules.append(controller)
    if shifter:
        selected_modules.append(shifter)
    if peer:
        selected_modules.append(peer)

    if low_v is None or high_v is None:
        missing.append("logic_voltage_pair")
        constraints.append(blocked("logic_voltage_pair", "logic_level", "interface", "Declare both low-side and high-side logic voltages."))
    elif abs(high_v - low_v) <= 0.35:
        constraints.append(
            warned(
                "logic_voltage_match",
                "logic_level",
                "interface",
                "Logic voltages appear compatible; level shifter may not be required.",
                value={"low_v": low_v, "high_v": high_v},
            )
        )
    else:
        constraints.append(
            passed(
                "logic_voltage_mismatch_detected",
                "logic_level",
                "interface",
                "Logic-voltage mismatch is explicit and needs translation.",
                value={"low_v": low_v, "high_v": high_v},
            )
        )

    if not shifter:
        missing.append("level_shifter_module")
        constraints.append(blocked("level_shifter_module", "logic_level", "interface", "Provide a known level-shifter module."))
    else:
        constraints.append(passed("level_shifter_module", "logic_level", shifter, "Known level-shifter module is available."))

    if channel_count is None:
        missing.append("channel_count")
        constraints.append(blocked("channel_count", "evidence_required", "interface", "Declare required shifted channel count."))
    elif channel_count <= 4:
        constraints.append(
            passed(
                "level_shifter_channel_count",
                "evidence_required",
                shifter or "level_shifter",
                "4-channel level shifter covers required channels.",
                value={"required_channels": channel_count, "available_channels": 4},
            )
        )
    else:
        missing.append("level_shifter_channel_count")
        constraints.append(
            blocked(
                "level_shifter_channel_count",
                "evidence_required",
                shifter or "level_shifter",
                "Required shifted channel count exceeds bounded 4-channel shifter.",
                value={"required_channels": channel_count, "available_channels": 4},
            )
        )

    if shifter and low_v is not None and high_v is not None:
        topology.append(
            TopologyOperator(
                operator_id="logic_level_translation",
                operator_type="level_shifter",
                inputs=["low_voltage_logic", "high_voltage_logic", "shared_ground"],
                outputs=["translated_logic_bus"],
                required_part_types=["level_shifter", "controller", "peripheral"],
                required_ports=["LV", "HV", "GND", "LVx", "HVx"],
                notes="Level shifting candidate; verify rail references and channel mapping before power-on.",
                metadata={
                    "module_id": shifter,
                    "controller_module": controller,
                    "peer_module": peer,
                    "low_v": low_v,
                    "high_v": high_v,
                    "channel_count": channel_count,
                },
            )
        )

    result = "blocked" if has_blocker(constraints, missing) else "ready_for_review"
    return SynthesisCandidate(
        candidate_id="level_shift_candidate",
        selected_parts=[
            {
                "id": "logic_translation",
                "type": "level_shifter",
                "low_v": low_v,
                "high_v": high_v,
                "channel_count": channel_count,
            }
        ],
        selected_modules=dedupe(selected_modules),
        generated_topology=topology,
        assumptions=[
            "Candidate is ready for human review only; channel mapping and rail references must be bench-checked."
            if result == "ready_for_review"
            else "Planner stopped before compile/readiness approval because level-shift evidence is missing or incompatible."
        ],
        missing_evidence=dedupe(missing),
        constraints=constraints,
        verification_gates=_verification_gates(low_v=low_v, high_v=high_v, channel_count=channel_count),
        recommended_build_path=build_path(available=available, selected=selected_modules),
        result=result,
        notes="Bounded logic-level translation topology plan.",
        metadata={"goal": circuit_intent.goal, "controller": controller, "peer": peer},
    )


def _peer_module(available: set[str], controller: str) -> str:
    for module_id in sorted(available):
        if module_id == controller or module_id in LEVEL_SHIFTER_MODULES or module_id in {"usb-power-5v", "dc-barrel-12v"}:
            continue
        spec = find_module(module_id) or {}
        category = str(spec.get("category") or "")
        if category in {"sensor", "display", "interface", "actuator"}:
            return module_id
    return ""


def _logic_pair(intent: CircuitIntent, controller: str, peer: str) -> tuple[float | None, float | None]:
    for row in intent.signal_requirements:
        low = _first_float(row, ("low_voltage_v", "controller_voltage_v", "mcu_voltage_v", "source_voltage_v"))
        high = _first_float(row, ("high_voltage_v", "peripheral_voltage_v", "device_voltage_v", "target_voltage_v"))
        if low is not None and high is not None:
            return min(low, high), max(low, high)
    values = [module_logic_voltage(module_id) for module_id in (controller, peer) if module_id]
    values = [v for v in values if v is not None]
    if len(values) >= 2:
        return min(values), max(values)
    return None, None


def _channel_count(intent: CircuitIntent) -> int | None:
    for row in intent.signal_requirements:
        raw = row.get("channels") or row.get("channel_count") or row.get("required_channels")
        value = float_or_none(raw)
        if value is not None:
            return int(value)
        bus = str(row.get("type") or row.get("bus") or row.get("signal_type") or "").lower()
        if bus in {"i2c", "uart"}:
            return 2
        if bus == "spi":
            return 4
        if bus in {"gpio", "digital", "pwm"}:
            return 1
    return None


def _available_shifter(available: set[str]) -> str:
    for module_id in LEVEL_SHIFTER_MODULES:
        if module_id in available:
            return module_id
    return ""


def _first_float(row: Mapping[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = float_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _verification_gates(*, low_v: float | None, high_v: float | None, channel_count: int | None) -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "level_shifter_rail_reference",
            "gate_type": "dmm_voltage",
            "critical": True,
            "prompt": "Measure LV, HV, and GND references before connecting signal channels.",
            "expected_low_v": low_v,
            "expected_high_v": high_v,
            "status": "open",
        },
        {
            "gate_id": "level_shifter_channel_mapping",
            "gate_type": "continuity_logic_probe",
            "critical": True,
            "prompt": "Verify each LVx/HVx channel mapping and idle level before attaching the peripheral.",
            "required_channels": channel_count,
            "status": "open",
        },
    ]
