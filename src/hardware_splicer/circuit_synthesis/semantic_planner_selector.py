"""Typed semantic selection for bounded circuit-synthesis planners.

The bounded planners are deterministic engineering machinery. This module replaces raw
prose keyword dispatch with a model-visible planner registry and a typed, zero-authority
selection record. Selection does not compile, fabricate, flash, or energize anything;
it only chooses which bounded planner may produce a reviewable circuit candidate.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .analog_conditioning_planner import plan_analog_conditioning
from .battery_power_planner import plan_battery_power
from .h_bridge_planner import plan_h_bridge
from .ir import CircuitIntent, SynthesisCandidate
from .level_shift_planner import plan_level_shift
from .motor_driver_planner import plan_motor_driver
from .power_rail_planner import plan_power_rail
from .relay_switch_planner import plan_relay_switch
from .sensor_interface_planner import plan_sensor_interface


SCHEMA_VERSION = "hardware_splicer.semantic_circuit_planner_selection.v1"

PLANNER_REGISTRY: Dict[str, Dict[str, str]] = {
    "battery_power": {
        "purpose": "battery source, charging, protection, portable power and battery rail planning",
        "boundary": "requires declared battery/charger requirements; missing chemistry/current remains unresolved",
    },
    "power_rail": {
        "purpose": "regulated power conversion or distribution between declared supply/load rails",
        "boundary": "requires sufficient input/output voltage and load requirements for defensible sizing",
    },
    "level_shift": {
        "purpose": "logic or signal voltage translation between explicitly different electrical domains",
        "boundary": "requires source/target logic domains or equivalent interface evidence",
    },
    "analog_conditioning": {
        "purpose": "bounded sensor/ADC analog conditioning such as divider/filter/interface preparation",
        "boundary": "not a generic analog amplifier synthesizer; signal and ADC constraints must be explicit",
    },
    "sensor_interface": {
        "purpose": "bounded sensor/display/digital-bus interface planning",
        "boundary": "requires interface/bus or peripheral requirements; unknown pin/electrical facts remain blockers",
    },
    "relay_switch": {
        "purpose": "relay-driven or isolated switched-load interface planning",
        "boundary": "requires load/control/interface requirements and preserves isolation/protection blockers",
    },
    "h_bridge": {
        "purpose": "bidirectional/reversible DC motor drive planning",
        "boundary": "requires motor supply/current/control requirements; no guessed driver ratings",
    },
    "motor_driver": {
        "purpose": "bounded unidirectional MCU-controlled motor, pump, fan or solenoid load driving",
        "boundary": "requires load voltage/current/control facts; protection and current evidence remain explicit",
    },
}

_PLANNERS: Dict[str, Callable[[CircuitIntent], SynthesisCandidate]] = {
    "battery_power": plan_battery_power,
    "power_rail": plan_power_rail,
    "level_shift": plan_level_shift,
    "analog_conditioning": plan_analog_conditioning,
    "sensor_interface": plan_sensor_interface,
    "relay_switch": plan_relay_switch,
    "h_bridge": plan_h_bridge,
    "motor_driver": plan_motor_driver,
}


class SemanticPlannerSelectionError(ValueError):
    """Raised when planner selection violates the bounded semantic contract."""


class SelectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticPlannerSelection(SelectionModel):
    schema_version: str = SCHEMA_VERSION
    selected_planner: str | None = None
    rationale: str = Field(default="", max_length=4_000)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=24)
    assumptions: list[str] = Field(default_factory=list, max_length=24)
    authority_effect: str = "none"
    automatic_execution: bool = False

    @field_validator("selected_planner")
    @classmethod
    def known_planner_or_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        planner_id = str(value).strip()
        if planner_id not in PLANNER_REGISTRY:
            raise ValueError(f"unknown bounded planner {planner_id!r}")
        return planner_id

    @field_validator("authority_effect")
    @classmethod
    def zero_authority_only(cls, value: str) -> str:
        if value != "none":
            raise ValueError("planner selection cannot change engineering authority")
        return value

    @field_validator("automatic_execution")
    @classmethod
    def selection_cannot_execute(cls, value: bool) -> bool:
        if value:
            raise ValueError("planner selection cannot automatically execute hardware actions")
        return False


class SemanticPlannerTrace(SelectionModel):
    schema_version: str = "hardware_splicer.semantic_circuit_planner_trace.v1"
    intent: Dict[str, Any]
    selection: SemanticPlannerSelection
    candidate: Dict[str, Any] | None = None
    authority_effect: str = "none"
    automatic_execution: bool = False


def planner_registry_payload() -> Dict[str, Dict[str, str]]:
    return {planner_id: dict(metadata) for planner_id, metadata in PLANNER_REGISTRY.items()}


def _intent_payload(intent: CircuitIntent) -> Dict[str, Any]:
    # CircuitIntent already carries structured requirements. Keep raw goal/notes because
    # semantic interpretation may need them, but do not expose keyword trigger tables.
    return intent.to_dict()


def semantic_planner_prompt(intent: CircuitIntent | Mapping[str, Any]) -> str:
    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    return f"""Choose at most one bounded Hardware Splicer circuit planner for this intent.

Circuit intent:
{json.dumps(_intent_payload(circuit_intent), sort_keys=True, indent=2)}

Available bounded planners:
{json.dumps(planner_registry_payload(), sort_keys=True, indent=2)}

Return JSON only:
{{
  "selected_planner": "planner-id-or-null",
  "rationale": "why this bounded planner matches the stated engineering function",
  "unresolved_questions": [],
  "assumptions": [],
  "authority_effect": "none",
  "automatic_execution": false
}}

Rules:
- Select only a planner ID from the supplied registry, or null when none is defensible.
- Base selection on the engineering function and structured constraints, not literal keyword matching.
- Do not invent voltage, current, chemistry, interface, isolation, or component facts.
- Put facts needed to choose defensibly in unresolved_questions rather than guessing them.
- Planner selection only chooses a bounded planning algorithm; it grants no compile or physical authority.
"""


def _extract_json_object(text: str) -> Dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, Mapping):
        raise SemanticPlannerSelectionError("planner selection response must be a JSON object")
    return dict(parsed)


def parse_semantic_planner_selection(value: Mapping[str, Any] | str) -> SemanticPlannerSelection:
    body = _extract_json_object(value) if isinstance(value, str) else dict(value)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("authority_effect", "none")
    body.setdefault("automatic_execution", False)
    try:
        selection = SemanticPlannerSelection.model_validate(body)
    except ValidationError as exc:
        raise SemanticPlannerSelectionError(str(exc)) from exc
    if selection.selected_planner is None and not selection.unresolved_questions:
        # Null is acceptable for a genuinely unsupported function, but the trace must
        # explain why the bounded registry cannot proceed instead of silently dropping it.
        if not selection.rationale.strip():
            raise SemanticPlannerSelectionError(
                "null planner selection requires a rationale or unresolved question"
            )
    return selection


def select_semantic_circuit_planner(
    intent: CircuitIntent | Mapping[str, Any],
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> SemanticPlannerSelection:
    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    prompt = semantic_planner_prompt(circuit_intent)

    if llm_callable is None:
        from ..integrations.qwen_text_client import call_qwen_chat

        response = call_qwen_chat(
            prompt,
            json_mode=True,
            stage="semantic_circuit_planner_selection",
            system="Choose only from the supplied bounded planner registry; never invent missing engineering facts.",
            timeout_s=60,
        )
    else:
        response = llm_callable(
            prompt,
            json_mode=True,
            stage="semantic_circuit_planner_selection",
            system="Choose only from the supplied bounded planner registry; never invent missing engineering facts.",
            timeout_s=60,
        )
    if not response.get("ok"):
        raise SemanticPlannerSelectionError(
            str(response.get("error") or response.get("reason") or "planner selection provider failed")
        )
    return parse_semantic_planner_selection(str(response.get("content") or "{}"))


def plan_circuit_from_semantic_selection(
    intent: CircuitIntent | Mapping[str, Any],
    selection: SemanticPlannerSelection | Mapping[str, Any],
) -> SemanticPlannerTrace:
    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    selected = (
        selection
        if isinstance(selection, SemanticPlannerSelection)
        else parse_semantic_planner_selection(selection)
    )

    candidate_payload: Dict[str, Any] | None = None
    if selected.selected_planner is not None:
        planner = _PLANNERS[selected.selected_planner]
        candidate = planner(circuit_intent)
        candidate_payload = candidate.to_dict()
        candidate_payload.setdefault("metadata", {})["dispatch"] = {
            "schema_version": SCHEMA_VERSION,
            "selected_planner": selected.selected_planner,
            "selection_source": "semantic_typed_selection",
            "selection_rationale": selected.rationale,
            "selection_authority_effect": "none",
        }

    return SemanticPlannerTrace(
        intent=_intent_payload(circuit_intent),
        selection=selected,
        candidate=candidate_payload,
        authority_effect="none",
        automatic_execution=False,
    )


def semantic_plan_circuit(
    intent: CircuitIntent | Mapping[str, Any],
    *,
    llm_callable: Callable[..., Dict[str, Any]] | None = None,
) -> SemanticPlannerTrace:
    circuit_intent = intent if isinstance(intent, CircuitIntent) else CircuitIntent.from_dict(intent)
    selection = select_semantic_circuit_planner(circuit_intent, llm_callable=llm_callable)
    return plan_circuit_from_semantic_selection(circuit_intent, selection)
