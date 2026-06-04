"""Constraint-aware hardware resource strategy.

This layer makes salvage, owned inventory, procurement, and designed parts the
same kind of planning input. The selected strategy mode changes the scoring
policy; it does not change the core engine.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


SCHEMA_VERSION = "resource_strategy.v1"

STRATEGY_MODE_ALIASES = {
    "constrained": "constrained",
    "constraint": "constrained",
    "salvage": "constrained",
    "junk": "constrained",
    "reuse": "constrained",
    "reuse_first": "constrained",
    "owned": "constrained",
    "open": "open_procurement",
    "open_procurement": "open_procurement",
    "unlimited": "open_procurement",
    "buy": "open_procurement",
    "buy_first": "open_procurement",
    "procure": "open_procurement",
    "procurement": "open_procurement",
    "hybrid": "hybrid",
    "mixed": "hybrid",
    "gap_fill": "hybrid",
}

RESOURCE_KIND_ALIASES = {
    "owned": "owned",
    "inventory": "owned",
    "operator_inventory": "owned",
    "available": "owned",
    "salvaged": "salvaged",
    "salvage": "salvaged",
    "junk": "salvaged",
    "circuit_functional_salvage": "salvaged",
    "analysis": "salvaged",
    "part_marking": "salvaged",
    "functional_block": "salvaged",
    "procurable": "procurable",
    "catalog": "procurable",
    "purchase": "procurable",
    "new": "procurable",
    "designed": "designed",
    "to_design": "designed",
    "unknown": "unknown",
}

NON_RESOURCE_SALVAGE_SOURCES = {
    "case_text",
    "description_text",
    "goal_text",
    "goal_text_inference",
    "text_inference",
    "text_signal",
}

CAPABILITY_ALIASES = {
    "firmware_controller": "controller",
    "programmable_debuggable": "controller",
    "microcontroller": "controller",
    "mcu": "controller",
    "i2c_expansion": "sensor_or_adc",
    "sensor": "sensor_or_adc",
    "adc": "sensor_or_adc",
    "usb_device_or_bridge": "usb_serial",
    "uart_link": "usb_serial",
    "uart": "usb_serial",
    "power_distribution_or_input": "power",
    "power_regulation": "power",
    "regulator": "power",
    "load_or_motor_control": "actuator_driver",
    "pwm_actuation": "actuator_driver",
    "motor_driver": "actuator_driver",
    "motor": "motor_or_load",
    "load": "motor_or_load",
    "fan": "fan_or_pump",
    "button": "switch_or_button",
    "switch": "switch_or_button",
    "light": "led_or_light",
    "led": "led_or_light",
    "display": "display_or_ui",
    "enclosure": "enclosure_candidate",
    "mechanical": "mechanical_motion",
}

HARD_HAZARD_TERMS = {
    "mains",
    "ac line",
    "120v",
    "240v",
    "crt",
    "microwave",
    "neon",
    "inverter",
    "high voltage",
    "swollen",
    "punctured",
    "leaking lithium",
}

CAPABILITY_COST_ESTIMATES = {
    "controller": 4.5,
    "wireless": 4.5,
    "sensor_or_adc": 2.5,
    "actuator_driver": 2.0,
    "motor_or_load": 2.5,
    "fan_or_pump": 2.5,
    "power": 2.0,
    "usb_serial": 2.5,
    "connector": 1.0,
    "switch_or_button": 0.8,
    "led_or_light": 1.2,
    "display_or_ui": 3.5,
    "mechanical_motion": 4.0,
    "enclosure_candidate": 2.0,
    "protection": 0.5,
}

REFERENCE_CATALOG = [
    {
        "resource_id": "esp32_dev_board",
        "name": "ESP32 dev board",
        "resource_kind": "procurable",
        "capabilities": ["controller", "wireless", "usb_serial"],
        "cost_usd": 4.5,
        "confidence": 0.9,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "lm2596_buck_converter",
        "name": "LM2596 buck converter module",
        "resource_kind": "procurable",
        "capabilities": ["power"],
        "cost_usd": 2.0,
        "confidence": 0.86,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "logic_mosfet_driver",
        "name": "logic-level MOSFET driver module",
        "resource_kind": "procurable",
        "capabilities": ["actuator_driver", "protection"],
        "cost_usd": 1.5,
        "confidence": 0.84,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "tb6612_motor_driver",
        "name": "TB6612 motor driver module",
        "resource_kind": "procurable",
        "capabilities": ["actuator_driver", "motor_or_load"],
        "cost_usd": 3.0,
        "confidence": 0.86,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "sensor_breakout",
        "name": "generic I2C sensor breakout",
        "resource_kind": "procurable",
        "capabilities": ["sensor_or_adc", "connector"],
        "cost_usd": 2.5,
        "confidence": 0.82,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "connector_wire_pack",
        "name": "headers, JST leads, and hookup wire",
        "resource_kind": "procurable",
        "capabilities": ["connector"],
        "cost_usd": 1.0,
        "confidence": 0.88,
        "evidence_status": "catalog_reference",
        "lead_time_days": 2,
    },
    {
        "resource_id": "switch_button_pack",
        "name": "toggle switch and pushbutton pack",
        "resource_kind": "procurable",
        "capabilities": ["switch_or_button"],
        "cost_usd": 0.8,
        "confidence": 0.88,
        "evidence_status": "catalog_reference",
        "lead_time_days": 2,
    },
    {
        "resource_id": "5v_usb_fan",
        "name": "5V USB fan module",
        "resource_kind": "procurable",
        "capabilities": ["motor_or_load", "fan_or_pump", "power"],
        "cost_usd": 2.5,
        "confidence": 0.84,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "led_light_segment",
        "name": "low-voltage LED light segment",
        "resource_kind": "procurable",
        "capabilities": ["led_or_light", "display_or_ui"],
        "cost_usd": 1.2,
        "confidence": 0.84,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "usb_camera_module",
        "name": "USB camera or camera trigger breakout",
        "resource_kind": "procurable",
        "capabilities": ["camera_or_vision", "connector"],
        "cost_usd": 5.0,
        "confidence": 0.78,
        "evidence_status": "catalog_reference",
        "lead_time_days": 5,
    },
    {
        "resource_id": "buzzer_audio_module",
        "name": "piezo buzzer or small audio amplifier module",
        "resource_kind": "procurable",
        "capabilities": ["speaker_or_audio", "connector"],
        "cost_usd": 2.5,
        "confidence": 0.82,
        "evidence_status": "catalog_reference",
        "lead_time_days": 3,
    },
    {
        "resource_id": "motion_mechanics_pack",
        "name": "small rail, belt, and bracket hardware",
        "resource_kind": "procurable",
        "capabilities": ["mechanical_motion", "enclosure_candidate"],
        "cost_usd": 4.0,
        "confidence": 0.72,
        "evidence_status": "catalog_reference",
        "lead_time_days": 5,
    },
]

BUILD_REQUIREMENTS = {
    "usb_fume_extractor": ["power", "motor_or_load", "fan_or_pump", "switch_or_button", "connector"],
    "inspection_motion_fixture": ["mechanical_motion", "led_or_light", "sensor_or_adc", "power"],
    "low_voltage_motor_test_jig": ["power", "motor_or_load", "connector", "switch_or_button"],
    "robot_drive_base": ["motor_or_load", "actuator_driver", "power", "controller"],
    "plotter_motion_stage": ["mechanical_motion", "sensor_or_adc", "power"],
    "smart_relay_box": ["controller", "actuator_driver", "power"],
    "sensor_logger": ["controller", "sensor_or_adc", "power"],
    "network_status_indicator": ["wireless", "display_or_ui", "power"],
    "small_audio_amp_box": ["speaker_or_audio", "power", "connector"],
    "salvaged_input_panel": ["switch_or_button", "connector", "controller"],
    "camera_ir_light_or_sensor_mount": ["camera_or_vision", "power", "connector"],
    "bench_power_adapter": ["power", "connector", "protection"],
    "usb_uart_debug_adapter": ["usb_serial", "connector"],
    "indicator_or_task_light": ["led_or_light", "power", "switch_or_button"],
}

GOAL_HINTS = [
    ({"fume", "extractor", "fan", "airflow", "cooling"}, ["power", "motor_or_load", "fan_or_pump", "switch_or_button"]),
    ({"inspection", "scanner", "camera", "fixture", "motion", "rail"}, ["mechanical_motion", "led_or_light", "sensor_or_adc", "power"]),
    ({"motor", "pump", "relay", "load", "actuator"}, ["power", "actuator_driver", "motor_or_load"]),
    ({"robot", "drive", "wheels", "mobile"}, ["controller", "actuator_driver", "motor_or_load", "power"]),
    ({"sensor", "logger", "monitor", "telemetry"}, ["controller", "sensor_or_adc", "power"]),
    ({"wifi", "network", "wireless", "status"}, ["controller", "wireless", "display_or_ui", "power"]),
    ({"audio", "speaker", "amp", "alert"}, ["speaker_or_audio", "power", "connector"]),
    ({"debug", "uart", "serial", "console"}, ["usb_serial", "connector"]),
    ({"power", "bench", "adapter", "supply", "breakout"}, ["power", "connector", "protection"]),
    ({"button", "keyboard", "panel", "macro", "input"}, ["switch_or_button", "connector", "controller"]),
    ({"light", "lamp", "led", "indicator"}, ["led_or_light", "power", "switch_or_button"]),
]

DISCOVERY_GOAL_TERMS = {
    "inspect",
    "identify",
    "understand",
    "photographed",
    "photo",
    "board",
    "salvage",
    "reuse",
    "repair",
    "recycle",
    "harvest",
    "inventory",
    "arbitrary",
}

DISCOVERY_CAPABILITY_PRIORITY = [
    "controller",
    "power",
    "connector",
    "network_interface",
    "display_or_ui",
    "usb_serial",
    "sensor_or_adc",
    "actuator_driver",
    "motor_or_load",
    "wireless",
    "switch_or_button",
    "led_or_light",
    "protection",
    "unknown_reusable_part",
]

DISCOVERY_EXCLUDED_CAPABILITIES = {
    "battery",
    "mains",
    "mains_voltage",
    "high_voltage",
    "hv",
    "laser",
}


def build_resource_strategy(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a resource strategy with the default deterministic planner."""

    return ResourceStrategyPlanner().plan(payload)


class ResourceStrategyPlanner:
    """Score resource pools for constrained, open-procurement, and hybrid builds."""

    def __init__(self, salvage_planner: Optional[SalvageSplicePlanner] = None):
        self.salvage_planner = salvage_planner or SalvageSplicePlanner()

    def plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = payload or {}
        strategy_mode = _strategy_mode(body)
        constraints = _constraints(body)
        required = _required_capabilities(body)
        available = self._available_resources(body)
        catalog = self._procurement_catalog(body)
        resources = _dedupe_resources([*available, *catalog])
        blocked = [resource for resource in resources if resource["status"] in {"unsafe_hold", "blocked_failed_evidence"}]
        scored = [
            _score_resource(resource, required, strategy_mode, constraints)
            for resource in resources
        ]
        selected, missing = _select_resources(scored, required, strategy_mode)
        procurement = _procurement_plan(selected, missing, catalog, required, constraints)
        evidence_gates = _evidence_gates(selected, missing, blocked)
        readiness = _build_readiness(required, selected, missing, procurement, evidence_gates, blocked, strategy_mode)
        selected_caps = _covered_capabilities(selected, required)
        return {
            "mode": "hardware_resource_strategy",
            "schema_version": SCHEMA_VERSION,
            "strategy_mode": strategy_mode,
            "resource_interpretation": {
                "core_rule": "salvage, owned inventory, procurement, and designed blocks are scored as resources; the resource pool changes, not the engine.",
                "constrained": "Prefer already-owned or salvaged resources and surface evidence gates before reuse.",
                "open_procurement": "Prefer reliable procurable modules when they beat uncertain reuse.",
                "hybrid": "Reuse proven resources and buy only the gaps.",
            },
            "goal": str(body.get("goal") or body.get("description") or ""),
            "constraints": constraints,
            "required_capabilities": required,
            "coverage": {
                "covered_capabilities": selected_caps,
                "missing_capabilities": missing,
                "coverage_score": round(len(selected_caps) / max(len(required), 1), 3) if required else 0.0,
            },
            "recommended_path": _recommended_path(strategy_mode, readiness, selected, missing),
            "build_readiness": readiness,
            "selected_resources": selected,
            "procurement_plan": procurement,
            "evidence_gates": evidence_gates,
            "blocked_resources": [_public_resource(resource) for resource in blocked],
            "candidate_resources": [_public_resource(resource) for resource in sorted(scored, key=lambda row: row["strategy_score"], reverse=True)[:12]],
            "value_summary": _value_summary(selected, procurement, constraints),
            "next_actions": _next_actions(readiness, selected, missing, procurement, evidence_gates, blocked),
            "handoff": {
                "next_engine": "salvage_splice_planner" if selected else "requirements_intake",
                "build_plan_inputs": {
                    "goal": body.get("goal"),
                    "selected_resource_ids": [resource["resource_id"] for resource in selected],
                    "required_capabilities": required,
                    "evidence_gate_count": len(evidence_gates),
                    "procurement_item_count": len(procurement.get("items") or []),
                },
            },
            "honesty": [
                "Catalog costs are rough planning estimates, not live quotes.",
                "A selected salvaged or owned resource is not splice-ready until its evidence gates close.",
                "Do not use blocked battery, mains, high-voltage, or failed-evidence resources as gap fillers.",
            ],
        }

    def _available_resources(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        resources: List[Dict[str, Any]] = []
        explicit_roots = [
            ("available_resources", "owned"),
            ("resources", "owned"),
            ("owned_resources", "owned"),
            ("inventory", "owned"),
            ("modules", "owned"),
            ("available_parts", "owned"),
            ("salvaged_resources", "salvaged"),
        ]
        for key, default_kind in explicit_roots:
            resources.extend(_resources_from_value(payload.get(key), default_kind=default_kind, source_key=key))

        for plan in _salvage_plans(payload):
            resources.extend(_resources_from_salvage_plan(plan))

        resources.extend(_resources_from_functional_salvage(payload.get("functional_salvage")))
        analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
        resources.extend(_resources_from_functional_salvage(analysis.get("functional_salvage")))

        if payload.get("derive_salvage_plan", True) and not any(resource["resource_kind"] == "salvaged" for resource in resources):
            derived = self._derive_salvage_resources(payload)
            resources.extend(derived)

        return _dedupe_resources(resources)

    def _derive_salvage_resources(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not any(payload.get(key) for key in ["analysis", "circuit", "functional_salvage", "inventory", "modules", "available_parts"]):
            return []
        plan_payload = dict(payload)
        plan_payload.pop("use_llm", None)
        plan_payload.pop("use_llm_reasoner", None)
        try:
            plan = self.salvage_planner.plan(plan_payload)
        except Exception:
            return []
        return _resources_from_salvage_plan(plan)

    def _procurement_catalog(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for key in ["procurable_catalog", "procurement_catalog", "catalog", "procurement_options"]:
            rows.extend(_resources_from_value(payload.get(key), default_kind="procurable", source_key=key))
        if payload.get("use_reference_catalog", True):
            rows.extend(_resources_from_value(REFERENCE_CATALOG, default_kind="procurable", source_key="reference_catalog"))
        return _dedupe_resources(rows)


def _strategy_mode(payload: Dict[str, Any]) -> str:
    constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
    raw = (
        payload.get("strategy_mode")
        or payload.get("resource_mode")
        or payload.get("mode")
        or constraints.get("strategy_mode")
        or constraints.get("resource_mode")
        or "hybrid"
    )
    return STRATEGY_MODE_ALIASES.get(str(raw).strip().lower(), "hybrid")


def _constraints(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
    budget = _first_number(
        raw.get("budget_usd"),
        raw.get("max_budget_usd"),
        raw.get("budget"),
        payload.get("budget_usd"),
        payload.get("max_budget_usd"),
    )
    return {
        "budget_usd": budget,
        "safety_level": str(raw.get("safety_level") or payload.get("safety_level") or "low_voltage_only"),
        "time_priority": str(raw.get("time_priority") or payload.get("time_priority") or "balanced"),
        "cost_priority": str(raw.get("cost_priority") or payload.get("cost_priority") or "balanced"),
        "environment": str(raw.get("environment") or payload.get("environment") or "bench_prototype"),
    }


def _first_number(*values: Any) -> Optional[float]:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return None


def _required_capabilities(payload: Dict[str, Any]) -> List[str]:
    constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else {}
    explicit = (
        payload.get("required_capabilities")
        or payload.get("capabilities_required")
        or payload.get("goal_capabilities")
        or constraints.get("required_capabilities")
        or constraints.get("capabilities")
    )
    caps = _normalise_capabilities(explicit)
    if caps:
        return caps

    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    build_id = str(
        payload.get("target_build_id")
        or target.get("recommended_build_id")
        or target.get("build_id")
        or ""
    )
    if build_id in BUILD_REQUIREMENTS:
        return _normalise_capabilities(BUILD_REQUIREMENTS[build_id])

    for plan in _salvage_plans(payload):
        plan_target = plan.get("target") if isinstance(plan.get("target"), dict) else {}
        plan_build_id = str(plan_target.get("recommended_build_id") or "")
        if plan_build_id in BUILD_REQUIREMENTS:
            return _normalise_capabilities(BUILD_REQUIREMENTS[plan_build_id])

    text = " ".join(
        str(payload.get(key) or "")
        for key in ["goal", "description", "title", "device_hint"]
    ).lower()
    found: List[str] = []
    for terms, hinted_caps in GOAL_HINTS:
        if any(term in text for term in terms):
            found.extend(hinted_caps)
    hinted = _dedupe(_normalise_capabilities(found))
    if hinted:
        return hinted
    return _candidate_capabilities_for_discovery(payload, text)


def _candidate_capabilities_for_discovery(payload: Dict[str, Any], text: str) -> List[str]:
    if not (_has_candidate_board_context(payload) or any(term in text for term in DISCOVERY_GOAL_TERMS)):
        return []
    counts: Dict[str, int] = {}
    for row in _candidate_resource_rows(payload):
        if not isinstance(row, dict):
            continue
        caps = _normalise_capabilities(row.get("capabilities") or row.get("capability") or row.get("functions"))
        if not caps:
            name = " ".join(
                str(row.get(key) or "")
                for key in ["name", "label", "title", "kind", "type", "notes", "marking", "visible_text"]
            )
            caps = _capabilities_for_text(name)
        for cap in caps:
            if cap in DISCOVERY_EXCLUDED_CAPABILITIES:
                continue
            counts[cap] = counts.get(cap, 0) + 1
    ordered = [cap for cap in DISCOVERY_CAPABILITY_PRIORITY if cap in counts]
    extras = sorted((cap for cap in counts if cap not in set(ordered)), key=lambda cap: (-counts[cap], cap))
    return _dedupe([*ordered, *extras])[:5]


def _has_candidate_board_context(payload: Dict[str, Any]) -> bool:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    return bool(
        payload.get("board_evidence")
        or payload.get("vision_evidence_bridge")
        or analysis.get("board_evidence")
        or analysis.get("vision_evidence_bridge")
    )


def _candidate_resource_rows(payload: Dict[str, Any]) -> List[Any]:
    rows: List[Any] = []
    for key in ["available_resources", "resources", "owned_resources", "inventory", "modules", "available_parts", "salvaged_resources"]:
        rows.extend(_rows(payload.get(key)))
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    for container in [payload.get("vision_evidence_bridge"), analysis.get("vision_evidence_bridge")]:
        if isinstance(container, dict):
            rows.extend(_rows(container.get("resource_candidates")))
    return rows


def _resources_from_value(value: Any, *, default_kind: str, source_key: str) -> List[Dict[str, Any]]:
    rows = _rows(value)
    return [
        _resource_from_row(row, default_kind=default_kind, source_key=source_key, index=index)
        for index, row in enumerate(rows)
    ]


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", "\n").splitlines() if item.strip()]
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return [value]


def _resource_from_row(row: Any, *, default_kind: str, source_key: str, index: int) -> Dict[str, Any]:
    if isinstance(row, dict):
        name = str(
            row.get("name")
            or row.get("label")
            or row.get("title")
            or row.get("part")
            or row.get("function_type")
            or row.get("block_id")
            or f"{source_key} {index + 1}"
        )
        raw_kind = row.get("resource_kind") or row.get("kind") or row.get("source_type") or row.get("source") or default_kind
        kind = _resource_kind(raw_kind, default_kind)
        caps = _normalise_capabilities(row.get("capabilities") or row.get("capability") or row.get("functions"))
        if not caps:
            caps = _capabilities_for_text(name)
        confidence = _safe_float(row.get("confidence"), _default_confidence(kind))
        cost = _first_number(row.get("cost_usd"), row.get("price_usd"), row.get("estimated_cost_usd"))
        if cost is None:
            cost = 0.0 if kind in {"owned", "salvaged"} else _estimated_cost(caps)
        evidence_gates = _gate_rows(row)
        resource = {
            "resource_id": _safe_id(row.get("resource_id") or row.get("block_id") or row.get("id") or name),
            "name": name,
            "resource_kind": kind,
            "source": str(row.get("source") or source_key),
            "capabilities": caps,
            "quantity": _safe_int(row.get("quantity") or row.get("qty") or 1, 1),
            "confidence": round(max(0.0, min(confidence, 0.99)), 3),
            "cost_usd": round(max(0.0, float(cost)), 2),
            "replacement_value_usd": round(_first_number(row.get("value_usd"), row.get("replacement_value_usd"), row.get("estimated_output_value_usd")) or _estimated_cost(caps), 2),
            "lead_time_days": _safe_int(row.get("lead_time_days"), 0 if kind in {"owned", "salvaged"} else 3),
            "evidence_status": str(row.get("evidence_status") or row.get("status") or ""),
            "source_refs": [str(item) for item in row.get("source_refs") or row.get("connector_refs") or []],
            "evidence_gates": evidence_gates,
            "notes": str(row.get("notes") or row.get("rationale") or ""),
        }
    else:
        name = str(row)
        kind = _resource_kind(default_kind, default_kind)
        caps = _capabilities_for_text(name)
        resource = {
            "resource_id": _safe_id(name),
            "name": name,
            "resource_kind": kind,
            "source": source_key,
            "capabilities": caps,
            "quantity": 1,
            "confidence": _default_confidence(kind),
            "cost_usd": 0.0 if kind in {"owned", "salvaged"} else _estimated_cost(caps),
            "replacement_value_usd": _estimated_cost(caps),
            "lead_time_days": 0 if kind in {"owned", "salvaged"} else 3,
            "evidence_status": "",
            "source_refs": [],
            "evidence_gates": [],
            "notes": "",
        }

    resource["status"] = _resource_status(resource)
    return resource


def _resource_kind(value: Any, default_kind: str) -> str:
    raw = str(value or default_kind).strip().lower()
    return RESOURCE_KIND_ALIASES.get(raw, RESOURCE_KIND_ALIASES.get(default_kind, "unknown"))


def _normalise_capabilities(value: Any) -> List[str]:
    caps: List[str] = []
    for item in _rows(value):
        if isinstance(item, dict):
            item = item.get("capability") or item.get("name") or item.get("id")
        raw = str(item or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not raw:
            continue
        caps.append(CAPABILITY_ALIASES.get(raw, raw))
    return _dedupe(caps)


def _capabilities_for_text(text: str) -> List[str]:
    lower = text.lower()
    mapping = [
        (["esp32", "esp8266", "arduino", "mcu", "microcontroller", "controller"], ["controller"]),
        (["wifi", "ble", "bluetooth", "radio", "antenna"], ["wireless"]),
        (["uart", "serial", "ch340", "cp210", "ft232", "usb"], ["usb_serial", "connector"]),
        (["sensor", "bme", "bmp", "sht", "adc", "optical", "limit switch"], ["sensor_or_adc"]),
        (["buck", "boost", "ldo", "regulator", "power", "5v", "12v", "usb-c", "battery"], ["power"]),
        (["mosfet", "driver", "relay", "tb6612", "drv", "a4988"], ["actuator_driver"]),
        (["motor", "fan", "pump", "speaker load"], ["motor_or_load"]),
        (["fan", "pump"], ["fan_or_pump"]),
        (["switch", "button", "keyboard", "macro", "keypad"], ["switch_or_button"]),
        (["connector", "jst", "header", "wire", "harness", "cable"], ["connector"]),
        (["led", "light", "lamp"], ["led_or_light", "display_or_ui"]),
        (["display", "oled", "lcd"], ["display_or_ui"]),
        (["rail", "belt", "gear", "stepper", "servo", "slider"], ["mechanical_motion"]),
        (["case", "enclosure", "bracket", "mount"], ["enclosure_candidate"]),
        (["fuse", "polyfuse", "protection", "diode"], ["protection"]),
        (["camera", "vision", "ir"], ["camera_or_vision", "sensor_or_adc"]),
        (["audio", "speaker", "amplifier", "amp"], ["speaker_or_audio"]),
    ]
    caps: List[str] = []
    for needles, values in mapping:
        if any(needle in lower for needle in needles):
            caps.extend(values)
    return _dedupe(caps) or ["unknown_reusable_part"]


def _gate_rows(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    gates = []
    for gate in row.get("evidence_gates") or []:
        if isinstance(gate, dict):
            gates.append(
                {
                    "gate_id": gate.get("gate_id") or gate.get("id"),
                    "status": gate.get("status", "open"),
                    "prompt": gate.get("prompt") or gate.get("action"),
                    "target": gate.get("target"),
                }
            )
    for prompt in row.get("required_tests") or row.get("missing_evidence") or []:
        gates.append({"gate_id": _safe_id(prompt), "status": "open", "prompt": str(prompt), "target": row.get("name")})
    return gates[:12]


def _resource_status(resource: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(resource.get("name") or ""),
            str(resource.get("notes") or ""),
            str(resource.get("evidence_status") or ""),
        ]
    ).lower()
    if any(term in text for term in HARD_HAZARD_TERMS):
        return "unsafe_hold"
    status = str(resource.get("evidence_status") or "").lower()
    if status in {"unsafe_hold", "unsafe", "failed", "blocked_failed_evidence", "electrical_viability_hold"}:
        return "blocked_failed_evidence" if "failed" in status else "unsafe_hold"
    if any(str(gate.get("status") or "").lower() == "failed" for gate in resource.get("evidence_gates") or []):
        return "blocked_failed_evidence"
    if resource.get("resource_kind") == "procurable":
        return "procurable"
    if status in {"verified", "reuse_ready", "measurement_backed", "authoritative_low_risk", "available", "proven"}:
        return "verified"
    if status in {"blocked_until_evidence", "needs_evidence", "open", "review_required"}:
        return "needs_evidence"
    if float(resource.get("confidence") or 0.0) < 0.58:
        return "needs_evidence"
    return "available"


def _salvage_plans(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    plans = []
    for key in ["salvage_plan", "splice_plan", "salvage_splice_plan"]:
        value = payload.get(key)
        if not isinstance(value, dict):
            continue
        if isinstance(value.get("splice_plan"), dict) and value.get("splice_plan", {}).get("mode") == "salvage_splice_reuse_plan":
            plans.append(value["splice_plan"])
        else:
            plans.append(value)
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    embedded = analysis.get("salvage_splice_plan")
    if isinstance(embedded, dict):
        plans.append(embedded)
    return plans


def _resources_from_salvage_plan(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for block in plan.get("reusable_blocks") or []:
        if isinstance(block, dict) and _is_physical_salvage_resource(block):
            row = dict(block)
            row.setdefault("resource_kind", "salvaged")
            rows.append(row)
    functional = plan.get("functional_reuse_plan") if isinstance(plan.get("functional_reuse_plan"), dict) else {}
    for key in ["ready_blocks", "top_blocks"]:
        for block in functional.get(key) or []:
            if isinstance(block, dict) and _is_physical_salvage_resource(block):
                row = dict(block)
                row.setdefault("resource_kind", "salvaged")
                rows.append(row)
    return [
        _resource_from_row(row, default_kind="salvaged", source_key="salvage_plan", index=index)
        for index, row in enumerate(rows)
    ]


def _is_physical_salvage_resource(row: Dict[str, Any]) -> bool:
    source = str(row.get("source") or "").strip().lower()
    if source in NON_RESOURCE_SALVAGE_SOURCES:
        return False
    backing = str(row.get("resource_backing") or row.get("evidence_backing") or "").strip().lower()
    if backing in {"hint", "text", "goal_text", "inferred_from_goal"}:
        return False
    return True


def _resources_from_functional_salvage(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    rows = []
    for key in ["reusable_blocks", "top_reusable_blocks", "ready_blocks", "top_blocks"]:
        for block in value.get(key) or []:
            if isinstance(block, dict):
                row = dict(block)
                row.setdefault("resource_kind", "salvaged")
                rows.append(row)
    return [
        _resource_from_row(row, default_kind="salvaged", source_key="functional_salvage", index=index)
        for index, row in enumerate(rows)
    ]


def _score_resource(resource: Dict[str, Any], required: Sequence[str], mode: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
    public = _public_resource(resource)
    required_set = set(required)
    caps = set(resource.get("capabilities") or [])
    matched = sorted(caps & required_set) if required_set else []
    coverage = len(matched) / max(len(required_set), 1) if required_set else 0.0
    confidence = float(resource.get("confidence") or 0.0)
    score = 0.12 + 0.45 * coverage + 0.20 * confidence
    score += _kind_mode_weight(resource, mode)
    score += _evidence_weight(resource)
    score += _cost_weight(resource, mode, constraints)
    if resource["status"] in {"unsafe_hold", "blocked_failed_evidence"}:
        score -= 1.0
    public["matched_capabilities"] = matched
    public["strategy_score"] = round(max(0.0, min(score, 0.99)), 3)
    public["selection_reason"] = _selection_reason(resource, mode, matched)
    return public


def _kind_mode_weight(resource: Dict[str, Any], mode: str) -> float:
    kind = resource.get("resource_kind")
    proven = _is_proven(resource)
    if mode == "constrained":
        if kind in {"owned", "salvaged"}:
            return 0.24 if proven else 0.15
        if kind == "procurable":
            return -0.12
        return 0.0
    if mode == "open_procurement":
        if kind == "procurable":
            return 0.28
        if kind in {"owned", "salvaged"}:
            return 0.08 if proven else -0.10
        return 0.05
    if kind in {"owned", "salvaged"}:
        return 0.22 if proven else 0.04
    if kind == "procurable":
        return 0.18
    return 0.04


def _evidence_weight(resource: Dict[str, Any]) -> float:
    status = resource.get("status")
    if status in {"verified", "available", "procurable"}:
        return 0.14
    if status == "needs_evidence":
        return -0.04
    return -0.18


def _cost_weight(resource: Dict[str, Any], mode: str, constraints: Dict[str, Any]) -> float:
    cost = float(resource.get("cost_usd") or 0.0)
    budget = constraints.get("budget_usd")
    if cost <= 0:
        return 0.12 if mode in {"constrained", "hybrid"} else 0.04
    if budget is None or budget <= 0:
        return -0.02 if mode == "open_procurement" else -0.06
    if cost <= budget:
        return max(0.0, 0.10 * (1 - (cost / max(budget, 0.01))))
    return -0.18


def _is_proven(resource: Dict[str, Any]) -> bool:
    return resource.get("status") in {"verified", "available"} and float(resource.get("confidence") or 0.0) >= 0.62


def _selection_reason(resource: Dict[str, Any], mode: str, matched: Sequence[str]) -> str:
    if resource.get("status") in {"unsafe_hold", "blocked_failed_evidence"}:
        return "blocked by safety or failed evidence"
    if resource.get("resource_kind") == "procurable":
        return "selected as a reliable purchasable gap filler" if mode != "constrained" else "catalog option for a missing resource"
    if _is_proven(resource):
        return "selected because it is already available and has enough evidence for planning"
    if matched:
        return "candidate resource, but evidence gates must close before splice/build use"
    return "candidate resource outside the current required capability set"


def _select_resources(resources: Sequence[Dict[str, Any]], required: Sequence[str], mode: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    required_set = set(required)
    if not required_set:
        return [], []
    uncovered = set(required_set)
    selected: List[Dict[str, Any]] = []
    candidates = sorted(
        [
            resource
            for resource in resources
            if resource.get("status") not in {"unsafe_hold", "blocked_failed_evidence"}
        ],
        key=lambda row: (
            -float(row.get("strategy_score") or 0.0),
            float(row.get("cost_usd") or 0.0),
            str(row.get("resource_id") or ""),
        ),
    )

    if mode == "hybrid":
        for resource in candidates:
            if resource.get("resource_kind") not in {"owned", "salvaged"}:
                continue
            gain = set(resource.get("capabilities") or []) & uncovered
            if not gain:
                continue
            selected.append(resource)
            uncovered -= gain
            if not uncovered:
                return selected[:12], []

    while uncovered:
        best = None
        best_gain: Set[str] = set()
        for resource in candidates:
            if resource in selected:
                continue
            if mode == "constrained" and resource.get("resource_kind") == "procurable":
                continue
            gain = set(resource.get("capabilities") or []) & uncovered
            if not gain:
                continue
            if best is None or (len(gain), resource.get("strategy_score", 0)) > (len(best_gain), best.get("strategy_score", 0)):
                best = resource
                best_gain = gain
        if best is None:
            break
        selected.append(best)
        uncovered -= best_gain

    if mode in {"open_procurement", "hybrid"} and uncovered:
        for resource in candidates:
            if resource in selected or resource.get("resource_kind") != "procurable":
                continue
            gain = set(resource.get("capabilities") or []) & uncovered
            if not gain:
                continue
            selected.append(resource)
            uncovered -= gain
            if not uncovered:
                break

    return selected[:12], sorted(uncovered)


def _procurement_plan(
    selected: Sequence[Dict[str, Any]],
    missing: Sequence[str],
    catalog: Sequence[Dict[str, Any]],
    required: Sequence[str],
    constraints: Dict[str, Any],
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = [
        _public_resource(resource)
        for resource in selected
        if resource.get("resource_kind") == "procurable"
    ]
    uncovered = set(missing)
    catalog_scored = sorted(
        [_score_resource(resource, required, "open_procurement", constraints) for resource in catalog],
        key=lambda row: (-float(row.get("strategy_score") or 0.0), float(row.get("cost_usd") or 0.0)),
    )
    for resource in catalog_scored:
        if resource.get("resource_id") in {item.get("resource_id") for item in items}:
            continue
        gain = set(resource.get("capabilities") or []) & uncovered
        if not gain:
            continue
        item = _public_resource(resource)
        item["fills_capabilities"] = sorted(gain)
        items.append(item)
        uncovered -= gain
        if not uncovered:
            break

    total = round(sum(float(item.get("cost_usd") or 0.0) for item in items), 2)
    budget = constraints.get("budget_usd")
    return {
        "items": items,
        "estimated_cost_usd": total,
        "budget_usd": budget,
        "within_budget": True if budget is None else total <= budget,
        "unfilled_capabilities": sorted(uncovered),
        "cost_basis": "rough_reference_estimate",
    }


def _evidence_gates(
    selected: Sequence[Dict[str, Any]],
    missing: Sequence[str],
    blocked: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    gates: List[Dict[str, Any]] = []
    for resource in selected:
        if resource.get("resource_kind") == "procurable":
            gates.append(
                {
                    "gate_id": f"datasheet_{resource['resource_id']}",
                    "resource_id": resource["resource_id"],
                    "type": "review",
                    "status": "open",
                    "prompt": f"Confirm datasheet, voltage/current rating, pinout, and seller part variant for {resource['name']}.",
                }
            )
            continue
        if resource.get("status") == "needs_evidence":
            existing = [
                gate for gate in resource.get("evidence_gates") or []
                if str(gate.get("status", "open")) != "closed"
            ]
            if existing:
                for gate in existing[:4]:
                    gates.append(
                        {
                            "gate_id": gate.get("gate_id") or f"evidence_{resource['resource_id']}",
                            "resource_id": resource["resource_id"],
                            "type": "measurement",
                            "status": gate.get("status", "open"),
                            "prompt": gate.get("prompt") or f"Close evidence for {resource['name']}.",
                        }
                    )
            else:
                for prompt in _generic_gates_for_caps(resource.get("capabilities") or [])[:3]:
                    gates.append(
                        {
                            "gate_id": _safe_id(f"{resource['resource_id']}_{prompt}"),
                            "resource_id": resource["resource_id"],
                            "type": "measurement",
                            "status": "open",
                            "prompt": prompt,
                        }
                    )
    for cap in missing:
        gates.append(
            {
                "gate_id": f"missing_{cap}",
                "resource_id": None,
                "type": "resource_gap",
                "status": "open",
                "prompt": f"Provide, procure, design, or remove requirement for missing capability: {cap}.",
            }
        )
    for resource in blocked[:5]:
        gates.append(
            {
                "gate_id": f"blocked_{resource['resource_id']}",
                "resource_id": resource["resource_id"],
                "type": "safety",
                "status": "blocked",
                "prompt": f"Do not use {resource['name']} until the safety or failed-evidence condition is separately resolved.",
            }
        )
    return _dedupe_gates(gates)[:20]


def _generic_gates_for_caps(caps: Sequence[str]) -> List[str]:
    cap_set = set(caps)
    prompts = []
    if "power" in cap_set:
        prompts.extend(["Measure no-short resistance between power and ground.", "Measure voltage, polarity, and current limit before interconnect."])
    if cap_set & {"motor_or_load", "fan_or_pump", "actuator_driver"}:
        prompts.extend(["Measure load resistance and startup current.", "Verify driver flyback/protection path and thermal behavior."])
    if cap_set & {"controller", "sensor_or_adc", "usb_serial", "wireless"}:
        prompts.append("Confirm logic voltage, shared ground requirement, and idle bus state.")
    if "connector" in cap_set:
        prompts.append("Map pinout and ground continuity before cutting or splicing.")
    if "mechanical_motion" in cap_set:
        prompts.append("Confirm travel limits, mechanical clearance, and wire strain relief.")
    return prompts or ["Record close-up evidence and bench-test the block before reuse."]


def _build_readiness(
    required: Sequence[str],
    selected: Sequence[Dict[str, Any]],
    missing: Sequence[str],
    procurement: Dict[str, Any],
    gates: Sequence[Dict[str, Any]],
    blocked: Sequence[Dict[str, Any]],
    mode: str,
) -> Dict[str, Any]:
    if not required:
        status = "define_goal"
        reason = "No required capabilities were explicit or inferable from the goal."
    elif missing and mode == "constrained":
        status = "blocked_missing_resources"
        reason = "Constrained mode cannot cover all required capabilities from available resources."
    elif missing:
        status = "blocked_missing_resources"
        reason = "Required capabilities remain uncovered after available resources and catalog options."
    elif not procurement.get("within_budget"):
        status = "blocked_over_budget"
        reason = "The selected procurement items exceed the stated budget."
    elif blocked and not selected and not procurement.get("items"):
        status = "safety_hold"
        reason = "Only blocked safety or failed-evidence resources are available for the goal."
    elif any(gate.get("type") == "measurement" and gate.get("status") != "closed" for gate in gates):
        status = "prototype_after_evidence"
        reason = "Selected resources cover the goal, but bench evidence is still required."
    elif selected:
        status = "ready_for_build_plan"
        reason = "Required capabilities are covered and no blocking resource gates remain."
    else:
        status = "collect_resources"
        reason = "No usable resources were selected."
    return {
        "status": status,
        "reason": reason,
        "selected_count": len(selected),
        "blocked_count": len(blocked),
        "open_gate_count": len([gate for gate in gates if gate.get("status", "open") not in {"closed", "pass"}]),
    }


def _recommended_path(mode: str, readiness: Dict[str, Any], selected: Sequence[Dict[str, Any]], missing: Sequence[str]) -> str:
    if readiness.get("status") in {"safety_hold", "blocked_missing_resources"} and missing:
        return "blocked_until_resource_gap_closed"
    if readiness.get("status") == "safety_hold":
        return "blocked_until_safety_review"
    if mode == "constrained":
        return "reuse_first"
    if mode == "open_procurement":
        return "buy_first"
    if any(resource.get("resource_kind") == "procurable" for resource in selected):
        return "hybrid_gap_fill"
    return "reuse_verified_inventory_first"


def _value_summary(selected: Sequence[Dict[str, Any]], procurement: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
    reused = [
        resource for resource in selected
        if resource.get("resource_kind") in {"owned", "salvaged"}
    ]
    avoided = round(sum(float(resource.get("replacement_value_usd") or 0.0) for resource in reused), 2)
    procurement_cost = float(procurement.get("estimated_cost_usd") or 0.0)
    budget = constraints.get("budget_usd")
    return {
        "reused_resource_count": len(reused),
        "estimated_replacement_value_reused_usd": avoided,
        "estimated_procurement_usd": procurement_cost,
        "estimated_net_cash_needed_usd": procurement_cost,
        "budget_usd": budget,
        "remaining_budget_usd": None if budget is None else round(budget - procurement_cost, 2),
        "value_logic": "Value comes from preserving proven resources and spending only where the capability gap is real.",
    }


def _next_actions(
    readiness: Dict[str, Any],
    selected: Sequence[Dict[str, Any]],
    missing: Sequence[str],
    procurement: Dict[str, Any],
    gates: Sequence[Dict[str, Any]],
    blocked: Sequence[Dict[str, Any]],
) -> List[str]:
    actions: List[str] = []
    if readiness.get("status") == "define_goal":
        actions.append("State the target output function and required capabilities.")
    if blocked:
        actions.append("Exclude blocked safety/failed-evidence resources from the build candidate pool.")
    if missing:
        actions.append("Close missing capabilities by adding inventory, procuring gap-fill modules, or changing scope.")
    if procurement.get("items"):
        actions.append("Review procurement items against the budget before buying.")
    if any(gate.get("type") == "measurement" for gate in gates):
        actions.append("Run the listed bench measurements before generating pin-level splice instructions.")
    if selected and not missing:
        actions.append("Pass selected resources into the splice/build planner for wiring, measurement, and first-power steps.")
    return actions[:6] or ["Collect resources and evidence for the target build."]


def _covered_capabilities(resources: Sequence[Dict[str, Any]], required: Sequence[str]) -> List[str]:
    required_set = set(required)
    covered = {
        cap
        for resource in resources
        for cap in resource.get("capabilities") or []
        if cap in required_set
    }
    return sorted(covered)


def _public_resource(resource: Dict[str, Any]) -> Dict[str, Any]:
    public = {
        "resource_id": resource.get("resource_id"),
        "name": resource.get("name"),
        "resource_kind": resource.get("resource_kind"),
        "source": resource.get("source"),
        "capabilities": resource.get("capabilities") or [],
        "quantity": resource.get("quantity", 1),
        "confidence": resource.get("confidence", 0.0),
        "status": resource.get("status", "unknown"),
        "cost_usd": resource.get("cost_usd", 0.0),
        "replacement_value_usd": resource.get("replacement_value_usd", 0.0),
        "lead_time_days": resource.get("lead_time_days", 0),
        "source_refs": resource.get("source_refs") or [],
    }
    for key in ["matched_capabilities", "strategy_score", "selection_reason"]:
        if key in resource:
            public[key] = resource[key]
    return public


def _estimated_cost(caps: Sequence[str]) -> float:
    costs = [CAPABILITY_COST_ESTIMATES.get(str(cap), 1.0) for cap in caps if str(cap) != "unknown_reusable_part"]
    return round(max(costs or [1.0]), 2)


def _default_confidence(kind: str) -> float:
    if kind == "procurable":
        return 0.84
    if kind == "owned":
        return 0.62
    if kind == "salvaged":
        return 0.55
    return 0.5


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "resource"


def _dedupe(items: Iterable[str]) -> List[str]:
    kept: List[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        kept.append(text)
    return kept


def _dedupe_resources(resources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for resource in resources:
        key = (
            str(resource.get("resource_id") or "").lower(),
            tuple(sorted(resource.get("capabilities") or [])),
            str(resource.get("resource_kind") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(resource)
    return kept[:80]


def _dedupe_gates(gates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for gate in gates:
        key = (gate.get("resource_id"), gate.get("type"), gate.get("prompt"))
        if key in seen:
            continue
        seen.add(key)
        kept.append(gate)
    return kept
