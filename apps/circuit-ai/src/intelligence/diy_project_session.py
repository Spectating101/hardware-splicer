"""Stateful DIY project intake sessions.

This layer keeps conversational project planning from becoming "latest prompt
only". Each turn updates structured intake state, then the deterministic DIY
planner runs from that state.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.intelligence.design_test_kit import build_design_test_kit
from src.intelligence.diy_project_engineer import build_diy_project_engineering_plan


SCHEMA_VERSION = "diy_project_session.v1"


RESOURCE_HINTS: Sequence[Tuple[Sequence[str], str, Sequence[str]]] = [
    (("esp32",), "ESP32 dev board", ("controller", "wireless", "usb_serial", "connector")),
    (("esp8266",), "ESP8266 dev board", ("controller", "wireless", "usb_serial", "connector")),
    (("arduino",), "Arduino-compatible controller board", ("controller", "usb_serial", "connector")),
    (("microcontroller", "mcu", "controller board"), "microcontroller board", ("controller", "connector")),
    (("soil sensor", "moisture sensor", "soil probe"), "soil moisture sensor module", ("sensor_or_adc", "connector")),
    (("temperature sensor", "humidity sensor", "sensor"), "sensor module", ("sensor_or_adc", "connector")),
    (("pump",), "mini pump", ("motor_or_load", "fan_or_pump")),
    (("pc fan", "usb fan", "fan"), "fan module", ("motor_or_load", "fan_or_pump")),
    (("motor", "toy motor"), "small motor", ("motor_or_load", "mechanical_motion")),
    (("solenoid", "valve"), "solenoid or valve load", ("motor_or_load", "actuator_driver")),
    (("mosfet", "driver"), "load driver module", ("actuator_driver", "protection")),
    (("relay",), "relay module", ("actuator_driver", "connector")),
    (("usb charger", "phone charger", "usb power", "power bank"), "USB power source", ("power", "connector")),
    (("laptop adapter", "adapter", "wall wart"), "DC adapter", ("power", "connector")),
    (("jumper wires", "hookup wire", "wires", "cable"), "hookup/jumper wire", ("connector",)),
    (("led strip", "leds", "led", "lamp", "light"), "low-voltage LED/light load", ("led_or_light",)),
    (("button", "switches", "switch", "keypad"), "button or switch input", ("switch_or_button", "connector")),
    (("speaker", "buzzer", "audio"), "speaker or buzzer module", ("speaker_or_audio", "connector")),
    (("camera", "webcam"), "camera or capture module", ("camera_or_vision", "connector")),
    (("wheel", "wheels", "gear", "chassis"), "mechanical drive hardware", ("mechanical_motion",)),
    (("case", "box", "enclosure", "bracket", "mount"), "case or mounting hardware", ("enclosure_candidate",)),
]


class DIYProjectSessionStore:
    """JSON-backed project-intake sessions for chat-driven hardware planning."""

    def __init__(self, store_path: str | Path = "data/diy_project_sessions/sessions.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions: List[Dict[str, Any]] = []
        self._load()

    def update_from_turn(
        self,
        payload: Dict[str, Any],
        *,
        user_id: str = "anonymous",
        commit: bool = True,
    ) -> Dict[str, Any]:
        body = dict(payload or {})
        text = _turn_text(body)
        session = self._session_for_payload(body, user_id=user_id)
        now = _now()

        if text:
            turns = session.setdefault("conversation", {}).setdefault("turns", [])
            turns.append({"role": "user", "text": text, "created_at": now})
            session["conversation"]["turn_count"] = len(turns)

        intake = session.setdefault("intake_state", _empty_intake())
        self._merge_explicit_resources(intake, body)
        self._merge_explicit_constraints(intake, body)
        self._merge_text_intake(intake, text)
        self._refresh_project_brief(session, body)

        plan_payload = self._plan_payload(session, body)
        plan = build_diy_project_engineering_plan(plan_payload)
        test_kit_payload = dict(body)
        test_kit_payload.update(plan_payload)
        test_kit_payload["diy_project_engineering"] = plan
        test_kit = build_design_test_kit(test_kit_payload)
        session["latest_plan"] = _compact_plan(plan)
        session["latest_test_kit"] = _compact_test_kit(test_kit)
        session["latest_plan_payload"] = {
            "strategy_mode": plan_payload.get("strategy_mode"),
            "required_resource_count": len(plan_payload.get("available_resources") or []),
            "use_reference_catalog": bool(plan_payload.get("use_reference_catalog", True)),
        }
        session["evidence_tasks"] = plan.get("next_evidence_tasks") or []
        session["updated_at"] = now

        if commit:
            self._upsert(session)
            self._save()

        return {
            "diy_project_session": session,
            "diy_project_engineering": plan,
            "design_test_kit": test_kit,
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        wanted = str(session_id or "").strip()
        if not wanted:
            return None
        for session in self.sessions:
            if session.get("session_id") == wanted:
                return json.loads(json.dumps(session))
        return None

    def _session_for_payload(self, payload: Dict[str, Any], *, user_id: str) -> Dict[str, Any]:
        existing = self.get_session(str(payload.get("session_id") or payload.get("diy_project_session_id") or ""))
        if existing:
            return existing
        now = _now()
        session_id = str(payload.get("session_id") or payload.get("diy_project_session_id") or f"diy_{uuid.uuid4().hex[:12]}")
        return {
            "session_id": session_id,
            "schema_version": SCHEMA_VERSION,
            "user_id": user_id,
            "status": "open",
            "created_at": now,
            "updated_at": now,
            "conversation": {"turns": [], "turn_count": 0},
            "intake_state": _empty_intake(),
            "evidence_tasks": [],
            "latest_plan": {},
        }

    def _merge_explicit_constraints(self, intake: Dict[str, Any], payload: Dict[str, Any]) -> None:
        constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
        budget = _first_number(
            constraints.get("budget_usd"),
            constraints.get("max_budget_usd"),
            constraints.get("budget"),
            payload.get("budget_usd"),
            payload.get("max_budget_usd"),
        )
        if budget is not None:
            intake.setdefault("constraints", {})["budget_usd"] = budget
        for key in ["safety_level", "environment", "time_priority", "cost_priority"]:
            value = constraints.get(key) or payload.get(key)
            if value:
                intake.setdefault("constraints", {})[key] = str(value)

    def _merge_explicit_resources(self, intake: Dict[str, Any], payload: Dict[str, Any]) -> None:
        resources = intake.setdefault("available_resources", [])
        for key in ["available_resources", "resources", "owned_resources", "inventory", "modules", "available_parts"]:
            for row in _rows(payload.get(key)):
                resource = _resource_from_explicit(row)
                if resource:
                    _merge_resource(resources, resource)

    def _merge_text_intake(self, intake: Dict[str, Any], text: str) -> None:
        if not text:
            return
        budget = _extract_budget_usd(text)
        if budget is not None:
            intake.setdefault("constraints", {})["budget_usd"] = budget
        resources, absent = _extract_resources_from_text(text)
        for resource in resources:
            _merge_resource(intake.setdefault("available_resources", []), resource)
        for resource in absent:
            _merge_resource(intake.setdefault("known_absent_resources", []), resource)
        labels = _extract_pinout_labels(text)
        if labels:
            known = set(intake.setdefault("observed_labels", []))
            intake["observed_labels"] = sorted(known | set(labels))
        measurements = _extract_measurement_notes(text)
        for measurement in measurements:
            _merge_measurement(intake.setdefault("measurements", []), measurement)

    def _refresh_project_brief(self, session: Dict[str, Any], payload: Dict[str, Any]) -> None:
        intake = session.setdefault("intake_state", _empty_intake())
        turns = [turn.get("text", "") for turn in (session.get("conversation") or {}).get("turns", []) if isinstance(turn, dict)]
        explicit_goal = _first_text(payload, ["diy_project", "project_brief", "build_goal", "target_build", "goal", "description", "title"])
        if explicit_goal and not intake.get("goal"):
            intake["goal"] = explicit_goal
        elif not intake.get("goal"):
            intake["goal"] = next((text for text in turns if _looks_like_goal(text)), "")
        intake["project_brief"] = "\n".join([text for text in turns[-12:] if text]).strip() or explicit_goal

    def _plan_payload(self, session: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        intake = session.get("intake_state") if isinstance(session.get("intake_state"), dict) else {}
        constraints = dict(intake.get("constraints") or {})
        plan_payload = {
            "diy_project": intake.get("project_brief") or intake.get("goal") or _turn_text(payload),
            "project_brief": intake.get("project_brief") or intake.get("goal") or _turn_text(payload),
            "strategy_mode": payload.get("strategy_mode") or constraints.get("strategy_mode") or "hybrid",
            "constraints": constraints,
            "available_resources": intake.get("available_resources") or [],
            "use_reference_catalog": payload.get("use_reference_catalog", True),
        }
        for key in ["required_capabilities", "target_build_id", "procurable_catalog"]:
            if payload.get(key):
                plan_payload[key] = payload[key]
        return plan_payload

    def _upsert(self, session: Dict[str, Any]) -> None:
        for index, existing in enumerate(self.sessions):
            if existing.get("session_id") == session.get("session_id"):
                self.sessions[index] = session
                return
        self.sessions.append(session)

    def _load(self) -> None:
        try:
            if self.store_path.exists():
                payload = json.loads(self.store_path.read_text(encoding="utf-8"))
                self.sessions = payload.get("sessions", []) if isinstance(payload, dict) else []
        except Exception:
            self.sessions = []

    def _save(self) -> None:
        self.store_path.write_text(json.dumps({"sessions": self.sessions}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _empty_intake() -> Dict[str, Any]:
    return {
        "goal": "",
        "project_brief": "",
        "constraints": {},
        "available_resources": [],
        "known_absent_resources": [],
        "measurements": [],
        "observed_labels": [],
    }


def _turn_text(payload: Dict[str, Any]) -> str:
    return _first_text(payload, ["user_message", "message", "turn_text", "text", "diy_project", "project_brief", "build_goal", "goal", "description"])


def _first_text(payload: Dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _looks_like_goal(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ["build", "make", "need", "want", "create", "diy", "project", "system", "thing"])


def _extract_resources_from_text(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    lower = text.lower()
    resources: List[Dict[str, Any]] = []
    absent: List[Dict[str, Any]] = []
    for terms, default_name, caps in RESOURCE_HINTS:
        for term in terms:
            if term not in lower:
                continue
            target = absent if _term_is_negated(lower, term) else resources
            ratings = _ratings_near(text, term)
            target.append(
                {
                    "resource_id": _safe_id("absent_" + default_name if target is absent else _resource_name(default_name, ratings)),
                    "name": _resource_name(default_name, ratings),
                    "resource_kind": "owned" if target is resources else "absent",
                    "capabilities": list(caps),
                    "confidence": 0.66 if target is resources else 0.72,
                    "evidence_status": "operator_reported_needs_measurement",
                    "ratings": ratings,
                    "source": "chat_intake",
                }
            )
            break
    return _dedupe_resources(resources), _dedupe_resources(absent)


def _resource_name(default_name: str, ratings: Dict[str, Any]) -> str:
    voltage = ratings.get("voltage_v")
    if voltage is not None and not re.search(r"\b\d+(?:\.\d+)?\s*v\b", default_name, flags=re.IGNORECASE):
        return f"{_format_number(voltage)}V {default_name}"
    return default_name


def _ratings_near(text: str, term: str) -> Dict[str, Any]:
    lower = text.lower()
    index = lower.find(term)
    if index < 0:
        window = text
    else:
        start = max(lower.rfind(sep, 0, index) for sep in [",", ";", ".", "\n"])
        end_candidates = [pos for pos in (lower.find(sep, index + len(term)) for sep in [",", ";", ".", "\n"]) if pos >= 0]
        start = 0 if start < 0 else start + 1
        end = min(end_candidates) if end_candidates else len(text)
        window = text[start:end]
    ratings: Dict[str, Any] = {}
    voltage = re.search(r"\b(\d+(?:\.\d+)?)\s*v\b", window, flags=re.IGNORECASE)
    if voltage:
        ratings["voltage_v"] = float(voltage.group(1))
    current = re.search(r"\b(\d+(?:\.\d+)?)\s*(ma|a)\b", window, flags=re.IGNORECASE)
    if current:
        value = float(current.group(1))
        ratings["current_a"] = round(value / 1000, 4) if current.group(2).lower() == "ma" else value
    return ratings


def _extract_pinout_labels(text: str) -> List[str]:
    labels = []
    for label in ["vcc", "gnd", "ground", "sig", "sda", "scl", "tx", "rx", "vin", "5v", "3v3", "en"]:
        if re.search(rf"\b{re.escape(label)}\b", text, flags=re.IGNORECASE):
            labels.append(label.upper() if label != "ground" else "GND")
    return sorted(set(labels))


def _extract_measurement_notes(text: str) -> List[Dict[str, Any]]:
    measurements = []
    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(v|ma|a|ohm|k|kohm)\b", text, flags=re.IGNORECASE):
        value = float(match.group(1))
        unit = match.group(2).lower()
        if unit == "ma":
            value = round(value / 1000, 4)
            unit = "A"
        elif unit == "k":
            value *= 1000
            unit = "ohm"
        measurements.append(
            {
                "measurement_id": _safe_id(f"{match.group(0)}_{match.start()}"),
                "type": "operator_reported_rating",
                "value": value,
                "unit": unit.upper() if unit in {"v", "a"} else unit,
                "raw": match.group(0),
                "confidence": 0.55,
            }
        )
    return measurements


def _resource_from_explicit(row: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(row, dict):
        if not str(row or "").strip():
            return None
        name = str(row).strip()
        resources, _ = _extract_resources_from_text(name)
        return resources[0] if resources else {"resource_id": _safe_id(name), "name": name, "resource_kind": "owned", "capabilities": [], "confidence": 0.5}
    name = str(row.get("name") or row.get("label") or row.get("resource_id") or row.get("id") or "").strip()
    if not name:
        return None
    return {
        "resource_id": _safe_id(row.get("resource_id") or row.get("id") or name),
        "name": name,
        "resource_kind": str(row.get("resource_kind") or row.get("kind") or "owned"),
        "capabilities": [str(cap) for cap in row.get("capabilities") or []],
        "confidence": float(row.get("confidence", 0.7) or 0.7),
        "evidence_status": str(row.get("evidence_status") or "operator_reported_needs_measurement"),
        "ratings": row.get("ratings") if isinstance(row.get("ratings"), dict) else {},
        "source": str(row.get("source") or "explicit_payload"),
    }


def _merge_resource(resources: List[Dict[str, Any]], resource: Dict[str, Any]) -> None:
    key_caps = set(resource.get("capabilities") or [])
    key_name = _safe_id(resource.get("name"))
    for existing in resources:
        same_name = _safe_id(existing.get("name")) == key_name
        overlapping_caps = bool(key_caps & set(existing.get("capabilities") or []))
        existing_name = _safe_id(existing.get("name"))
        if same_name or (overlapping_caps and (key_name in existing_name or existing_name in key_name)):
            existing["capabilities"] = sorted(set(existing.get("capabilities") or []) | key_caps)
            existing["confidence"] = max(float(existing.get("confidence", 0) or 0), float(resource.get("confidence", 0) or 0))
            existing.setdefault("ratings", {}).update(resource.get("ratings") or {})
            if resource.get("ratings") and re.search(r"\b\d+(?:\.\d+)?\s*v\b", str(resource.get("name") or ""), flags=re.IGNORECASE):
                existing["name"] = resource["name"]
                existing["resource_id"] = _safe_id(resource["name"])
            return
    resources.append(resource)


def _merge_measurement(measurements: List[Dict[str, Any]], measurement: Dict[str, Any]) -> None:
    key = (measurement.get("type"), measurement.get("raw"))
    for existing in measurements:
        if (existing.get("type"), existing.get("raw")) == key:
            return
    measurements.append(measurement)


def _dedupe_resources(resources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for resource in resources:
        _merge_resource(kept, resource)
    return kept


def _compact_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    intent = plan.get("project_intent") if isinstance(plan.get("project_intent"), dict) else {}
    readiness = plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {}
    resource_plan = plan.get("resource_plan") if isinstance(plan.get("resource_plan"), dict) else {}
    coverage = resource_plan.get("coverage") if isinstance(resource_plan.get("coverage"), dict) else {}
    procurement = resource_plan.get("procurement") if isinstance(resource_plan.get("procurement"), dict) else {}
    return {
        "available": bool(plan.get("available")),
        "profile_id": intent.get("profile_id"),
        "profile_label": intent.get("profile_label"),
        "readiness": readiness.get("level"),
        "readiness_score": readiness.get("score"),
        "coverage_score": coverage.get("coverage_score"),
        "missing_capabilities": coverage.get("missing_capabilities") or [],
        "estimated_cost_usd": procurement.get("estimated_cost_usd"),
        "budget_usd": procurement.get("budget_usd"),
        "within_budget": procurement.get("within_budget"),
    }


def _compact_test_kit(test_kit: Dict[str, Any]) -> Dict[str, Any]:
    suite = test_kit.get("test_suite") if isinstance(test_kit.get("test_suite"), dict) else {}
    release = test_kit.get("release_gate") if isinstance(test_kit.get("release_gate"), dict) else {}
    simulation = test_kit.get("simulation") if isinstance(test_kit.get("simulation"), dict) else {}
    return {
        "available": bool(test_kit.get("available")),
        "score": suite.get("score"),
        "pass_count": suite.get("pass_count"),
        "warning_count": suite.get("warning_count"),
        "fail_count": suite.get("fail_count"),
        "blocked_count": suite.get("blocked_count"),
        "pending_count": suite.get("pending_count"),
        "decision": release.get("decision"),
        "simulation_available": bool(simulation.get("available")),
        "can_advance_to_controlled_bench": release.get("can_advance_to_controlled_bench"),
        "can_power_or_splice": release.get("can_power_or_splice"),
    }


def _extract_budget_usd(text: str) -> Optional[float]:
    patterns = [
        r"\$\s*(\d+(?:\.\d+)?)",
        r"\b(\d+(?:\.\d+)?)\s*(?:usd|dollars?|bucks?)\b",
        r"\b(?:budget|max|under|below|around|about|only|spend|ceiling|limit)\b(?:\s+\w+){0,4}?\s+(\d+(?:\.\d+)?)\b",
    ]
    lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            value = _first_number(match.group(1))
            if value is not None and 0 < value < 100000:
                return value
    return None


def _term_is_negated(lower_text: str, term: str) -> bool:
    pattern = re.escape(term).replace(r"\ ", r"\s+")
    return bool(re.search(rf"\b(?:no|not|without|missing|dont\s+have|don't\s+have)\b(?:\s+\w+){{0,4}}\s+{pattern}\b", lower_text))


def _first_number(*values: Any) -> Optional[float]:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return None


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", "\n").splitlines() if item.strip()]
    return [value]


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "item"


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else str(number)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
