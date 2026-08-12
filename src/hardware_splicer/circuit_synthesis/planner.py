"""Dispatcher for bounded circuit synthesis planners.

Model-first routing uses the typed semantic planner registry and never falls back to
natural-language keyword selection when semantic selection fails. The historical keyword
dispatcher is retained only for explicit offline compatibility/regression.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from .analog_conditioning_planner import plan_analog_conditioning
from .battery_power_planner import plan_battery_power
from .h_bridge_planner import plan_h_bridge
from .level_shift_planner import plan_level_shift
from .power_rail_planner import plan_power_rail
from .relay_switch_planner import plan_relay_switch
from .sensor_interface_planner import plan_sensor_interface
from .ir import CircuitIntent, Constraint, SynthesisCandidate
from .motor_driver_planner import plan_motor_driver
from .semantic_planner_selector import (
    SemanticPlannerSelection,
    SemanticPlannerSelectionError,
    plan_circuit_from_semantic_selection,
    select_semantic_circuit_planner,
)


SCHEMA_VERSION = "hardware_splicer.circuit_synthesis_dispatch.v2"
LEGACY_SCHEMA_VERSION = "hardware_splicer.circuit_synthesis_dispatch.v1"

MOTOR_KEYWORDS = {
    "motor",
    "pump",
    "fan",
    "blower",
    "solenoid",
    "h-bridge",
    "hbridge",
    "low side",
    "low-side",
    "mosfet",
    "actuator",
}
H_BRIDGE_KEYWORDS = {
    "h-bridge",
    "hbridge",
    "bidirectional",
    "bi-directional",
    "reverse motor",
    "reversible",
    "forward reverse",
    "direction control",
    "wheel drive",
}
RELAY_KEYWORDS = {
    "relay",
    "contact",
    "isolated switch",
    "switched load",
    "solenoid valve",
    "lamp",
    "mains",
    "vac",
}
BATTERY_KEYWORDS = {
    "battery",
    "lipo",
    "li-po",
    "liion",
    "li-ion",
    "charger",
    "tp4056",
    "protected cell",
    "fuel gauge",
    "portable",
}
ANALOG_KEYWORDS = {
    "adc",
    "voltage divider",
    "divider",
    "rc filter",
    "filter",
    "sensor output",
    "sample rate",
    "calibration",
}
POWER_KEYWORDS = {
    "buck",
    "boost",
    "ldo",
    "regulator",
    "regulated",
    "power rail",
    "rail",
    "step down",
    "step-down",
    "12v to 5v",
    "12v to 3.3v",
    "5v to 3.3v",
    "3v3",
}
LEVEL_SHIFT_KEYWORDS = {
    "level shifter",
    "level shift",
    "logic level",
    "translate logic",
    "voltage translate",
}
SENSOR_KEYWORDS = {
    "sensor",
    "i2c",
    "onewire",
    "one wire",
    "ultrasonic",
    "hc-sr04",
    "bme280",
    "dht22",
    "soil moisture",
    "tof",
    "vl53",
    "imu",
    "mpu6050",
    "display",
    "oled",
}


def plan_circuit(
    intent: CircuitIntent | Mapping[str, Any],
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> SynthesisCandidate:
    """Route arbitrary circuit intent through the bounded planner registry.

    Production/model-first mode asks the model only which bounded planner applies. The
    selected deterministic planner remains responsible for electrical constraints and may
    still block on missing evidence. If semantic selection is unresolved or unavailable,
    this dispatcher returns a structured blocked candidate; it never falls back to
    keyword routing. Explicit offline compatibility retains the historical dispatcher.
    """

    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    from ..integrations.llm_policy import offline_salvage_enabled

    if offline_salvage_enabled():
        return _legacy_plan_circuit(circuit_intent)

    try:
        selection = select_semantic_circuit_planner(
            circuit_intent,
            llm_callable=llm_callable,
        )
    except SemanticPlannerSelectionError as exc:
        return _semantic_selection_blocked(
            circuit_intent,
            rationale=str(exc),
            unresolved_questions=["Resolve bounded circuit planner selection before synthesis."],
            selection_source="semantic_selection_error",
        )

    if selection.selected_planner is None:
        return _semantic_selection_blocked(
            circuit_intent,
            rationale=selection.rationale,
            unresolved_questions=selection.unresolved_questions,
            selection_source="semantic_typed_selection",
            selection=selection,
        )

    trace = plan_circuit_from_semantic_selection(circuit_intent, selection)
    if not isinstance(trace.candidate, Mapping):
        return _semantic_selection_blocked(
            circuit_intent,
            rationale="Semantic planner selection produced no deterministic candidate.",
            unresolved_questions=selection.unresolved_questions,
            selection_source="semantic_typed_selection",
            selection=selection,
        )
    candidate = SynthesisCandidate.from_dict(trace.candidate)
    body = candidate.to_dict()
    metadata = dict(body.get("metadata") or {})
    dispatch = dict(metadata.get("dispatch") or {})
    dispatch.update(
        {
            "schema_version": SCHEMA_VERSION,
            "selected_planner": selection.selected_planner,
            "selection_source": "semantic_typed_selection",
            "selection_rationale": selection.rationale,
            "legacy_keyword_dispatch_used": False,
            "authority_effect": "none",
            "automatic_execution": False,
        }
    )
    metadata["dispatch"] = dispatch
    metadata["semantic_planner_selection"] = selection.model_dump(mode="json")
    body["metadata"] = metadata
    return SynthesisCandidate.from_dict(body)


def _semantic_selection_blocked(
    intent: CircuitIntent,
    *,
    rationale: str,
    unresolved_questions: list[str],
    selection_source: str,
    selection: SemanticPlannerSelection | None = None,
) -> SynthesisCandidate:
    questions = [str(row).strip() for row in unresolved_questions if str(row).strip()]
    missing = ["bounded_planner_selection"]
    missing.extend(f"planner_question:{index + 1}" for index, _ in enumerate(questions))
    selection_payload = (
        selection.model_dump(mode="json")
        if selection is not None
        else {
            "selected_planner": None,
            "rationale": rationale,
            "unresolved_questions": questions,
            "authority_effect": "none",
            "automatic_execution": False,
        }
    )
    return SynthesisCandidate(
        candidate_id="semantic_planner_selection_unresolved",
        result="blocked",
        assumptions=[],
        missing_evidence=missing,
        constraints=[
            Constraint(
                constraint_id="bounded_planner_selection",
                type="unsupported_goal",
                target="circuit_intent",
                requirement=(
                    questions[0]
                    if questions
                    else rationale or "Resolve a bounded circuit planner before synthesis."
                ),
                status="blocked",
            )
        ],
        recommended_build_path={
            "build_id": None,
            "compose_mode": "blocked_semantic_planner_selection",
            "module_ids": [],
            "can_compile_with_existing_auto_wire": False,
            "notes": [
                "No deterministic bounded circuit planner executes until semantic selection is resolved.",
            ],
        },
        notes=rationale or "Circuit planner selection remains unresolved.",
        metadata={
            "goal": intent.goal,
            "dispatch": {
                "schema_version": SCHEMA_VERSION,
                "selected_planner": None,
                "selection_source": selection_source,
                "selection_rationale": rationale,
                "legacy_keyword_dispatch_used": False,
                "authority_effect": "none",
                "automatic_execution": False,
            },
            "semantic_planner_selection": selection_payload,
        },
    )


def _legacy_plan_circuit(circuit_intent: CircuitIntent) -> SynthesisCandidate:
    """Historical natural-language dispatcher for explicit offline compatibility only."""
    if _looks_like_battery_power(circuit_intent):
        return _with_dispatch(
            plan_battery_power(circuit_intent),
            selected_planner="battery_power",
            reason="Intent includes battery/charger/portable power terms.",
        )
    if _looks_like_level_shift(circuit_intent):
        return _with_dispatch(
            plan_level_shift(circuit_intent),
            selected_planner="level_shift",
            reason="Intent includes logic-level translation terms or explicit voltage mismatch.",
        )
    if _looks_like_h_bridge(circuit_intent):
        return _with_dispatch(
            plan_h_bridge(circuit_intent),
            selected_planner="h_bridge",
            reason="Intent includes reversible/bidirectional DC motor drive terms.",
        )
    if _looks_like_relay_switch(circuit_intent):
        return _with_dispatch(
            plan_relay_switch(circuit_intent),
            selected_planner="relay_switch",
            reason="Intent includes relay/isolated switched-load terms.",
        )
    if _looks_like_analog_conditioning(circuit_intent):
        return _with_dispatch(
            plan_analog_conditioning(circuit_intent),
            selected_planner="analog_conditioning",
            reason="Intent includes analog/ADC conditioning terms.",
        )
    if _looks_like_power_rail(circuit_intent):
        return _with_dispatch(
            plan_power_rail(circuit_intent),
            selected_planner="power_rail",
            reason="Intent includes regulator/power-rail terms or explicit voltage/current rail constraints.",
        )
    if _looks_like_motor_driver(circuit_intent):
        return _with_dispatch(
            plan_motor_driver(circuit_intent),
            selected_planner="motor_driver",
            reason="Intent includes motor/pump/fan/solenoid/driver terms or load/module hints.",
        )
    if _looks_like_sensor_interface(circuit_intent):
        return _with_dispatch(
            plan_sensor_interface(circuit_intent),
            selected_planner="sensor_interface",
            reason="Intent includes sensor/display/interface terms or known sensor modules.",
        )
    return _unsupported_candidate(circuit_intent)


def _with_dispatch(candidate: SynthesisCandidate, *, selected_planner: str, reason: str) -> SynthesisCandidate:
    body = candidate.to_dict()
    body.setdefault("metadata", {})["dispatch"] = {
        "schema_version": LEGACY_SCHEMA_VERSION,
        "selected_planner": selected_planner,
        "reason": reason,
        "selection_source": "legacy_keyword",
        "legacy_keyword_dispatch_used": True,
        "authority_effect": "none",
        "automatic_execution": False,
    }
    return SynthesisCandidate.from_dict(body)


def _looks_like_motor_driver(intent: CircuitIntent) -> bool:
    return _has_keywords(intent, MOTOR_KEYWORDS)


def _looks_like_h_bridge(intent: CircuitIntent) -> bool:
    return _has_keywords(intent, H_BRIDGE_KEYWORDS)


def _looks_like_relay_switch(intent: CircuitIntent) -> bool:
    return _has_keywords(intent, RELAY_KEYWORDS)


def _looks_like_battery_power(intent: CircuitIntent) -> bool:
    if _has_keywords(intent, BATTERY_KEYWORDS):
        return True
    return any(str(row.get("chemistry") or row.get("type") or row.get("kind") or "").lower() in {"li-ion", "liion", "lipo", "li-po", "battery"} for row in intent.supply_rails + intent.allowed_parts)


def _looks_like_analog_conditioning(intent: CircuitIntent) -> bool:
    text = _intent_text(intent)
    if any(token in text for token in ("audio", "preamplifier", "preamp", "amplifier", "op amp", "op-amp")) and "adc" not in text:
        return False
    if _has_keywords(intent, ANALOG_KEYWORDS):
        return True
    for row in intent.signal_requirements:
        kind = str(row.get("type") or row.get("signal_type") or row.get("bus") or "").lower()
        if kind == "adc":
            return True
        if kind == "analog" and any(token in text for token in ("adc", "sensor", "controller", "mcu", "esp32", "arduino", "pico")):
            return True
    return False


def _looks_like_power_rail(intent: CircuitIntent) -> bool:
    if len(intent.supply_rails) >= 2 or intent.voltage_constraints:
        return True
    return _has_keywords(intent, POWER_KEYWORDS)


def _looks_like_level_shift(intent: CircuitIntent) -> bool:
    has_signal_voltage = False
    for row in intent.signal_requirements:
        values = [str(row.get(key) or "").lower() for key in ("low_voltage_v", "high_voltage_v", "source_voltage_v", "target_voltage_v", "controller_voltage_v", "peripheral_voltage_v")]
        if any(value for value in values):
            has_signal_voltage = True
            break
    if has_signal_voltage:
        return True
    return _has_keywords(intent, LEVEL_SHIFT_KEYWORDS)


def _looks_like_sensor_interface(intent: CircuitIntent) -> bool:
    return _has_keywords(intent, SENSOR_KEYWORDS)


def _has_keywords(intent: CircuitIntent, keywords: set[str]) -> bool:
    text = _intent_text(intent)
    return any(token in text for token in keywords)


def _intent_text(intent: CircuitIntent) -> str:
    text_parts = [intent.goal, intent.notes]
    for row in (
        intent.supply_rails
        + intent.load_requirements
        + intent.signal_requirements
        + intent.voltage_constraints
        + intent.current_constraints
        + intent.allowed_parts
    ):
        text_parts.extend(str(row.get(key) or "") for key in ("id", "name", "type", "kind", "role", "module_id", "bus", "signal_type"))
    text_parts.extend(intent.allowed_modules)
    return " ".join(text_parts).lower()


def _unsupported_candidate(intent: CircuitIntent) -> SynthesisCandidate:
    return SynthesisCandidate(
        candidate_id="unsupported_circuit_intent",
        result="blocked",
        assumptions=[
            "No bounded topology planner is registered for this intent yet.",
            "The offline compatibility dispatcher refuses unsupported goals instead of inventing a schematic.",
        ],
        missing_evidence=["bounded_planner", "functional_requirements", "component_constraints"],
        constraints=[
            Constraint(
                constraint_id="unsupported_goal",
                type="unsupported_goal",
                target="circuit_intent",
                requirement="Add a bounded planner or provide a supported intent.",
                status="blocked",
            )
        ],
        recommended_build_path={
            "build_id": None,
            "compose_mode": "blocked_unsupported_intent",
            "module_ids": [],
            "can_compile_with_existing_auto_wire": False,
            "notes": [
                "Supported bounded planners today: battery power, power rail, level shifter, analog conditioning, sensor/interface, relay switch, H-bridge motor, and MCU-controlled DC motor/pump/fan/solenoid driver.",
                "Do not route unsupported arbitrary intents into compose_dispatch.",
            ],
        },
        notes="Unsupported arbitrary circuit intent.",
        metadata={
            "goal": intent.goal,
            "dispatch": {
                "schema_version": LEGACY_SCHEMA_VERSION,
                "selected_planner": None,
                "reason": "No registered bounded planner matched this request.",
                "selection_source": "legacy_keyword",
                "legacy_keyword_dispatch_used": True,
                "authority_effect": "none",
                "automatic_execution": False,
            },
        },
    )
