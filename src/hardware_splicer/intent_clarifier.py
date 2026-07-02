"""Lightweight pre-flight clarifications for vague hardware intents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping

SCHEMA_VERSION = "hardware_splicer.intent_clarifier.v1"

_DEFAULT_QUESTIONS = (
    {
        "id": "power_source",
        "prompt": "What is the primary power source (e.g. USB 5V, 12V barrel, battery)?",
        "maps_to": "supply_rails",
    },
    {
        "id": "controller",
        "prompt": "Which controller should drive logic (e.g. ESP32, Arduino Nano, Pico)?",
        "maps_to": "allowed_modules",
    },
    {
        "id": "load_type",
        "prompt": "What load or function are you driving (motor, pump, sensor bus, relay)?",
        "maps_to": "load_requirements",
    },
    {
        "id": "donor_context",
        "prompt": "Are you reusing donor hardware (junk board photo/fixture) or building greenfield?",
        "maps_to": "salvage_mode",
    },
)


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return [str(item).strip() for item in value if str(item).strip()]


def _needs_clarification(intent: Mapping[str, Any]) -> bool:
    goal = str(intent.get("goal") or intent.get("project_name") or "").strip()
    if len(goal) < 8:
        return True
    has_supply = bool(intent.get("supply_rails") or intent.get("power_topology"))
    has_load = bool(intent.get("load_requirements") or intent.get("available_parts"))
    has_splice = bool(intent.get("circuit") or intent.get("donor_context") or intent.get("salvage_mode"))
    has_modules = bool(intent.get("allowed_modules") or intent.get("module_ids"))
    vague_tokens = ("something", "gadget", "device", "project", "board", "hardware")
    goal_lower = goal.lower()
    if any(token in goal_lower for token in vague_tokens) and not (has_supply and (has_load or has_modules)):
        return True
    return not (has_supply or has_load or has_splice or has_modules)


def analyze_intent_clarifications(intent: Mapping[str, Any]) -> Dict[str, Any]:
    """Return clarifying questions and optional enriched intent when answers are present."""
    body = dict(intent)
    answers = dict(body.get("clarification_answers") or {})
    needs = _needs_clarification(body)
    questions = [dict(row) for row in _DEFAULT_QUESTIONS] if needs else []
    enriched = apply_clarification_answers(body) if answers else body
    return {
        "schema_version": SCHEMA_VERSION,
        "needs_clarification": needs and not answers,
        "questions": questions,
        "clarification_answers": answers,
        "enriched_intent": enriched,
        "notes": (
            "Answer clarification_answers on the intent before planning when needs_clarification is true."
            if needs and not answers
            else "Intent has enough structure for bounded planning."
        ),
    }


def apply_clarification_answers(intent: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge clarification_answers into a planning-ready intent copy."""
    body = deepcopy(dict(intent))
    answers = dict(body.pop("clarification_answers", None) or {})

    power = str(answers.get("power_source") or "").lower()
    if power and not body.get("supply_rails"):
        if "12" in power:
            body["supply_rails"] = [{"name": "+12V", "voltage_v": 12.0, "max_current_a": 2.0}]
        elif "battery" in power or "li" in power:
            body["supply_rails"] = [{"name": "VBAT", "voltage_v": 7.4, "max_current_a": 2.0}]
        else:
            body["supply_rails"] = [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}]

    controller = str(answers.get("controller") or "").lower()
    allowed = _string_list(body.get("allowed_modules"))
    if controller:
        if "esp32" in controller and "esp32-devkit" not in allowed:
            allowed.append("esp32-devkit")
        if "arduino" in controller and "arduino-nano" not in allowed:
            allowed.append("arduino-nano")
        if "pico" in controller and "rpi-pico" not in allowed:
            allowed.append("rpi-pico")
    if allowed:
        body["allowed_modules"] = allowed

    load = str(answers.get("load_type") or "").lower()
    if load and not body.get("load_requirements"):
        load_row: Dict[str, Any] = {"name": "load", "type": "generic"}
        if "motor" in load or "pump" in load:
            load_row.update({"type": "dc_motor", "voltage_v": 5.0, "current_a": 0.5})
        elif "relay" in load:
            load_row.update({"type": "relay_load", "voltage_v": 5.0, "current_a": 0.2})
        elif "sensor" in load:
            load_row.update({"type": "sensor_bus", "voltage_v": 3.3})
        body["load_requirements"] = [load_row]

    donor = str(answers.get("donor_context") or "").lower()
    if donor:
        if any(token in donor for token in ("donor", "junk", "salvage", "reuse", "splice")):
            body["salvage_mode"] = True
        elif any(token in donor for token in ("greenfield", "new", "scratch")):
            body["salvage_mode"] = False

    return body
