"""Bridge vision-language board evidence into planner/session inputs.

Qwen-VL and similar models are useful for proposing visible components,
connectors, damage, and salvage candidates. This adapter turns those proposals
into structured candidates for the deterministic hardware engine. It does not
mark resources as verified or clear safety gates.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Sequence


SCHEMA_VERSION = "vision_board_evidence_bridge.v1"


def enrich_payload_with_board_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of payload with Qwen/vision board evidence bridged in."""

    body = dict(payload or {})
    evidence = extract_board_evidence(body)
    if not evidence:
        return body

    bridge = board_evidence_bridge(evidence)
    if not bridge.get("available"):
        return body

    analysis = dict(body.get("analysis") if isinstance(body.get("analysis"), dict) else {})
    analysis.setdefault("mode", "vision_board_evidence")
    analysis["board_evidence"] = bridge["board_evidence"]
    analysis["vision_evidence_bridge"] = bridge
    if bridge.get("detections"):
        existing_detections = analysis.get("detections") if isinstance(analysis.get("detections"), list) else []
        analysis["detections"] = _dedupe_rows(existing_detections + bridge["detections"], key_fields=("class_name", "label", "bbox"))
        analysis["detection_summary"] = _detection_summary(analysis["detections"])

    existing_resources = body.get("available_resources") if isinstance(body.get("available_resources"), list) else []
    body["available_resources"] = _dedupe_rows(existing_resources + bridge["resource_candidates"], key_fields=("resource_id",))

    existing_hazard = body.get("hazard_profile") if isinstance(body.get("hazard_profile"), dict) else {}
    body["hazard_profile"] = _merge_hazard_profiles(existing_hazard, bridge["hazard_profile"])
    body["analysis"] = analysis
    body["vision_evidence_bridge"] = bridge
    return body


def extract_board_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Find a board_evidence.v1-style object in common payload shapes."""

    for root in _candidate_roots(payload):
        if not isinstance(root, dict):
            continue
        evidence = root.get("board_evidence")
        if isinstance(evidence, dict):
            return evidence
        if str(root.get("schema_version") or "") == "board_evidence.v1":
            return root
        parsed = _parse_qwen_response(root)
        if parsed:
            evidence = parsed.get("board_evidence")
            if isinstance(evidence, dict):
                return evidence
    return {}


def board_evidence_bridge(board_evidence: Dict[str, Any]) -> Dict[str, Any]:
    evidence = _normalize_board_evidence(board_evidence)
    components = evidence.get("components") or []
    connectors = evidence.get("connectors") or []
    markings = evidence.get("markings") or []
    salvage_candidates = evidence.get("salvage_candidates") or []
    damage = evidence.get("damage") or []
    regions = evidence.get("regions") or []
    test_points = evidence.get("test_points") or []
    candidates = _resource_candidates(components, connectors, salvage_candidates, test_points, markings)
    hazards = _hazard_candidates(evidence, damage, regions, components)
    detections = _detections_from_evidence(components, connectors, damage, test_points)
    return {
        "schema_version": SCHEMA_VERSION,
        "available": bool(components or connectors or salvage_candidates or damage or test_points),
        "source": "vision_language_board_evidence",
        "board_evidence": evidence,
        "detections": detections,
        "resource_candidates": candidates,
        "hazard_profile": {
            "schema_version": "hardware_hazard_profile.v1",
            "energy_domain": _energy_domain(hazards, candidates),
            "hazards": hazards,
            "clearance_requirements": _dedupe(
                hazard.get("clearance_requires")
                for hazard in hazards
                if hazard.get("clearance_requires")
            )[:12],
            "source_policy": {
                "structured_sources": ["board_evidence.v1"],
                "raw_text_release_logic": False,
                "llm_outputs_must_be_structured_hazard_candidates": True,
                "vision_candidates_require_measurement_or_review": True,
            },
        },
        "policy": {
            "vision_evidence_is_candidate_only": True,
            "resources_require_measurement_or_review": True,
            "hazards_can_block_release": True,
            "hazards_cannot_be_cleared_by_vision_text": True,
        },
    }


def _candidate_roots(payload: Dict[str, Any]) -> List[Any]:
    roots: List[Any] = [payload]
    for key in ["qwen", "qwen_response", "vision", "vision_response", "analysis", "results"]:
        value = payload.get(key)
        if isinstance(value, dict):
            roots.append(value)
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    for key in ["qwen", "qwen_response", "vision", "vision_response"]:
        value = analysis.get(key)
        if isinstance(value, dict):
            roots.append(value)
    return roots


def _parse_qwen_response(root: Dict[str, Any]) -> Dict[str, Any]:
    choices = root.get("choices") if isinstance(root.get("choices"), list) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return {}
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _normalize_board_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    component_rows, promoted_connectors = _split_component_connector_rows(_rows(evidence.get("components")))
    normalized = {
        "schema_version": "board_evidence.v1",
        "components": [_normalize_item(item, "component", index) for index, item in enumerate(component_rows, start=1)],
        "markings": [_normalize_item(item, "marking", index) for index, item in enumerate(_rows(evidence.get("markings")), start=1)],
        "regions": [_normalize_item(item, "region", index) for index, item in enumerate(_rows(evidence.get("regions")), start=1)],
        "damage": [_normalize_item(item, "damage", index) for index, item in enumerate(_rows(evidence.get("damage")), start=1)],
        "connectors": [
            _normalize_item(item, "connector", index)
            for index, item in enumerate([*_rows(evidence.get("connectors")), *promoted_connectors], start=1)
        ],
        "test_points": [_normalize_item(item, "test_point", index) for index, item in enumerate(_rows(evidence.get("test_points")), start=1)],
        "salvage_candidates": [_normalize_item(item, "salvage_candidate", index) for index, item in enumerate(_rows(evidence.get("salvage_candidates")), start=1)],
    }
    if isinstance(evidence.get("multiview_reconstruction"), dict):
        normalized["multiview_reconstruction"] = evidence["multiview_reconstruction"]
    return normalized


def _split_component_connector_rows(rows: Sequence[Any]) -> tuple[List[Any], List[Any]]:
    components: List[Any] = []
    connectors: List[Any] = []
    for row in rows:
        if isinstance(row, dict) and _looks_like_connector_item(row):
            connectors.append(row)
        else:
            components.append(row)
    return components, connectors


def _looks_like_connector_item(row: Dict[str, Any]) -> bool:
    kind_text = " ".join(str(row.get(key) or "") for key in ["kind", "type"]).lower()
    label_text = " ".join(
        str(row.get(key) or "")
        for key in ["label", "function", "notes", "visible_text"]
    ).lower()
    if any(term in kind_text for term in ["integrated_circuit", "ic", "chip", "processor", "mcu", "controller", "memory"]):
        return False
    if any(term in kind_text for term in ["connector", "header", "port", "socket", "terminal_block", "terminal block", "rj45"]):
        return True
    if any(term in label_text for term in ["connector", "header", "socket", "terminal block", "rj45"]):
        return True
    if any(
        term in label_text
        for term in [
            "usb port",
            "usb-a port",
            "usb-c port",
            "usb_a",
            "usb-c",
            "usb c",
            "usb type c",
            "type-c",
            "hdmi port",
            "ethernet port",
            "gpio header",
        ]
    ):
        return True
    return False


def _normalize_item(item: Any, kind: str, index: int) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {"label": str(item)}
    label = str(
        row.get("label")
        or row.get("name")
        or (row.get("text") if kind == "marking" else "")
        or row.get("type")
        or row.get("kind")
        or f"{kind} {index}"
    ).strip()
    normalized = {
        "id": str(row.get("id") or row.get(f"{kind}_id") or f"{kind}_{index}").strip(),
        "label": label,
        "kind": str(row.get("kind") or row.get("type") or kind).strip(),
        "bbox": _bbox(row.get("bbox") or row.get("box") or row.get("bbox_2d")),
        "confidence": _safe_float(row.get("confidence"), 0.62),
        "warnings": _string_list(row.get("warnings") or row.get("risk_flags")),
        "missing_evidence": _string_list(row.get("missing_evidence") or row.get("recommended_checks") or row.get("required_tests")),
        "source": "board_evidence.v1",
    }
    for key in ["function", "capabilities", "severity", "notes", "marking", "text", "markings", "pin_count", "visible_text"]:
        if key in row:
            normalized[key] = row.get(key)
    for key in ["source_refs", "support_count", "cross_view", "geometry", "resolved_markings", "identity_status"]:
        if key in row:
            normalized[key] = row.get(key)
    return normalized


def _resource_candidates(
    components: Sequence[Dict[str, Any]],
    connectors: Sequence[Dict[str, Any]],
    salvage_candidates: Sequence[Dict[str, Any]],
    test_points: Sequence[Dict[str, Any]],
    markings: Sequence[Dict[str, Any]] = (),
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, kind in [
        (components, "component"),
        (connectors, "connector"),
        (salvage_candidates, "salvage_candidate"),
        (markings, "marking"),
    ]:
        for item in source:
            label = str(item.get("label") or item.get("kind") or kind)
            caps = _capabilities_for_item(item)
            rows.append(
                {
                    "resource_id": f"vision_{_safe_id(item.get('id') or label)}",
                    "name": label,
                    "resource_kind": "salvaged",
                    "source": "board_evidence.v1",
                    "capabilities": caps,
                    "confidence": round(max(0.35, min(_safe_float(item.get("confidence"), 0.62), 0.82)), 3),
                    "evidence_status": "needs_evidence",
                    "source_refs": [str(item.get("id") or label)],
                    "missing_evidence": _resource_missing_evidence(item, caps),
                    "required_tests": _resource_missing_evidence(item, caps),
                    "notes": "Vision-language candidate; not verified until reviewed or measured.",
                }
            )
    if test_points:
        rows.append(
            {
                "resource_id": "vision_test_points",
                "name": "visible test points",
                "resource_kind": "salvaged",
                "source": "board_evidence.v1",
                "capabilities": ["connector"],
                "confidence": 0.62,
                "evidence_status": "needs_evidence",
                "source_refs": [str(item.get("id") or item.get("label")) for item in test_points],
                "missing_evidence": ["Map test points with continuity and voltage measurements before reuse."],
                "required_tests": ["Map test points with continuity and voltage measurements before reuse."],
                "notes": "Vision-language candidate test pads.",
            }
        )
    return _dedupe_rows(rows, key_fields=("resource_id",))


def _hazard_candidates(
    evidence: Dict[str, Any],
    damage: Sequence[Dict[str, Any]],
    regions: Sequence[Dict[str, Any]],
    components: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    hazards: List[Dict[str, Any]] = []
    for item in list(damage) + list(regions) + list(components):
        text = _item_text(item)
        hazard_id = _hazard_id(text, item)
        if not hazard_id:
            continue
        severity = _hazard_severity(text, item)
        hazards.append(
            {
                "hazard_id": hazard_id,
                "source": f"board_evidence.v1:{item.get('id') or item.get('label')}",
                "severity": severity,
                "unsupported_for_production_authority": severity in {"critical", "unsupported"},
                "evidence": item,
                "clearance_requires": _clearance_requirement(hazard_id),
            }
        )
    safety = str(evidence.get("safety_level") or "").strip().lower()
    if safety == "hazard":
        hazards.append(
            {
                "hazard_id": "vision_reported_hazard",
                "source": "board_evidence.v1:safety_level",
                "severity": "critical",
                "unsupported_for_production_authority": True,
                "evidence": {"safety_level": safety},
                "clearance_requires": "Resolve vision-reported hazard with inspection and measurement before production authority.",
            }
        )
    return _dedupe_hazards(hazards)


def _detections_from_evidence(
    components: Sequence[Dict[str, Any]],
    connectors: Sequence[Dict[str, Any]],
    damage: Sequence[Dict[str, Any]],
    test_points: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    detections: List[Dict[str, Any]] = []
    for item in list(components) + list(connectors) + list(test_points):
        detections.append(
            {
                "class_name": str(item.get("kind") or item.get("label") or "component"),
                "label": str(item.get("label") or item.get("kind") or "component"),
                "confidence": _safe_float(item.get("confidence"), 0.62),
                "bbox": item.get("bbox") or [],
                "source": "board_evidence.v1",
            }
        )
    for item in damage:
        detections.append(
            {
                "class_name": "damage",
                "label": str(item.get("label") or item.get("kind") or "damage"),
                "confidence": _safe_float(item.get("confidence"), 0.62),
                "bbox": item.get("bbox") or [],
                "source": "board_evidence.v1",
            }
        )
    return detections


def _capabilities_for_item(item: Dict[str, Any]) -> List[str]:
    explicit = _string_list(item.get("capabilities"))
    if explicit:
        return _dedupe(_normalize_capability(cap) for cap in explicit)
    text = _item_text(item)
    mapping = [
        (("ch340", "cp210", "ft232", "uart", "usb serial", "usb bridge"), ["usb_serial", "connector"]),
        (("connector", "header", "jst", "usb", "port", "socket", "test point", "pad"), ["connector"]),
        (("ethernet", "rj45", "canh", "canl", "rs485"), ["network_interface", "connector"]),
        (("hdmi", "display connector", "display port"), ["display_or_ui", "connector"]),
        (("esp32", "esp8266", "atmega", "stm32", "rp2040", "raspberry pi", "single board computer", "sbc", "processor", "cpu", "soc", "microcontroller", "mcu", "controller", "arduino"), ["controller"]),
        (("gpio",), ["controller", "connector"]),
        (("esp32", "esp8266", "wifi", "ble", "bluetooth", "rf", "lora", "antenna"), ["wireless"]),
        (("max485", "sp3485", "sn75176", "adm485", "rs485", "mcp2551", "mcp2562", "tja1050", "sn65hvd230", "canh", "canl"), ["network_interface", "connector"]),
        (("sensor", "accelerometer", "temperature", "pressure", "camera", "bme280", "bmp280", "sht31", "mpu6050", "ads1115"), ["sensor_or_adc"]),
        (("camera", "image sensor"), ["camera_or_vision", "sensor_or_adc"]),
        (("regulator", "ldo", "buck", "boost", "power", "usb-c", "5v", "12v", "ams1117", "lm1117", "ld1117", "lm2596", "mp1584"), ["power"]),
        (("mosfet", "motor driver", "driver", "relay", "drv", "tb6612", "a4988", "drv8833", "l298n", "uln2003"), ["actuator_driver"]),
        (("motor", "fan", "pump"), ["motor_or_load"]),
        (("fan", "pump"), ["fan_or_pump"]),
        (("switch", "button", "keypad"), ["switch_or_button"]),
        (("led", "lamp", "light"), ["led_or_light"]),
        (("display", "oled", "lcd"), ["display_or_ui"]),
        (("audio", "speaker", "amplifier", "amp", "pam8403", "lm386", "buzzer", "max98357"), ["speaker_or_audio"]),
        (("battery", "cell", "pack", "charger", "bms", "tp4056", "dw01a", "li-ion", "lipo"), ["battery", "power"]),
        (("fuse", "protection", "polyfuse", "diode"), ["protection"]),
    ]
    caps: List[str] = []
    for needles, values in mapping:
        if any(needle in text for needle in needles):
            caps.extend(values)
    return _dedupe(caps) or ["unknown_reusable_part"]


def _resource_missing_evidence(item: Dict[str, Any], caps: Sequence[str]) -> List[str]:
    missing = list(_string_list(item.get("missing_evidence")))
    label = str(item.get("label") or item.get("kind") or "candidate")
    if "connector" in caps:
        missing.append(f"Map pinout and continuity for {label}.")
    if "power" in caps or "battery" in caps:
        missing.append(f"Measure voltage, polarity, current limit, and thermal behavior for {label}.")
    if "usb_serial" in caps:
        missing.append(f"Verify UART voltage level, shared ground, TX/RX continuity, and loopback for {label}.")
    if "actuator_driver" in caps or "motor_or_load" in caps:
        missing.append(f"Measure drive current, stall/abnormal current behavior, and thermal behavior for {label}.")
    if not missing:
        missing.append(f"Review visible marking and continuity before reusing {label}.")
    return _dedupe(missing)[:8]


def _hazard_id(text: str, item: Dict[str, Any]) -> str:
    if any(term in text for term in ["swollen", "punctured", "leaking", "lithium", "li-ion", "battery pack"]):
        return "damaged_lithium_pack" if any(term in text for term in ["swollen", "punctured", "leaking", "damaged"]) else "battery_pack"
    if any(term in text for term in ["mains", "ac line", "120v", "240v", "high voltage", "hv", "crt", "microwave"]):
        return "mains_voltage" if any(term in text for term in ["mains", "ac line", "120v", "240v"]) else "high_voltage"
    if "laser" in text:
        return "laser_radiation"
    if any(term in text for term in ["burn", "char", "scorch", "corrosion", "short", "bridge"]):
        return "visible_board_damage"
    severity = str(item.get("severity") or "").strip().lower()
    if severity in {"critical", "hazard", "unsupported"}:
        return "vision_reported_hazard"
    return ""


def _hazard_severity(text: str, item: Dict[str, Any]) -> str:
    raw = str(item.get("severity") or "").strip().lower()
    if raw in {"critical", "unsupported", "hard_stop"}:
        return "critical" if raw == "hard_stop" else raw
    if any(term in text for term in ["swollen", "punctured", "leaking", "mains", "120v", "240v", "high voltage", "crt", "microwave", "laser"]):
        return "critical"
    if any(term in text for term in ["burn", "char", "scorch", "short", "bridge"]):
        return "review"
    return raw or "review"


def _clearance_requirement(hazard_id: str) -> str:
    if hazard_id in {"battery_pack", "damaged_lithium_pack"}:
        return "Move battery evidence into the battery specialist workflow before production release."
    if hazard_id in {"mains_voltage", "high_voltage"}:
        return "Move mains/high-voltage evidence into the specialist safety workflow before production release."
    if hazard_id == "laser_radiation":
        return "Move laser/radiation evidence into the specialist safety workflow before production release."
    return "Resolve visible damage with inspection, cleaning/repair, and measurements before reuse."


def _merge_hazard_profiles(existing: Dict[str, Any], generated: Dict[str, Any]) -> Dict[str, Any]:
    if not existing:
        return generated
    merged = dict(existing)
    merged["hazards"] = _dedupe_hazards((existing.get("hazards") or []) + (generated.get("hazards") or []))
    merged["clearance_requirements"] = _dedupe((existing.get("clearance_requirements") or []) + (generated.get("clearance_requirements") or []))[:12]
    merged.setdefault("schema_version", "hardware_hazard_profile.v1")
    merged.setdefault("source_policy", generated.get("source_policy") or {})
    if generated.get("energy_domain") and not merged.get("energy_domain"):
        merged["energy_domain"] = generated["energy_domain"]
    return merged


def _detection_summary(detections: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    confidences = [_safe_float(row.get("confidence"), 0.0) for row in detections if isinstance(row, dict)]
    return {
        "total_components": len(detections),
        "average_confidence": round(sum(confidences) / max(len(confidences), 1), 3),
        "source": "board_evidence.v1",
    }


def _energy_domain(hazards: Sequence[Dict[str, Any]], resources: Sequence[Dict[str, Any]]) -> str:
    hazard_ids = {str(hazard.get("hazard_id") or "") for hazard in hazards}
    caps = {
        str(cap)
        for resource in resources
        if isinstance(resource, dict)
        for cap in resource.get("capabilities") or []
    }
    if hazard_ids & {"mains_voltage", "high_voltage"}:
        return "mains_or_high_voltage_candidate"
    if hazard_ids & {"battery_pack", "damaged_lithium_pack"} or "battery" in caps:
        return "battery_candidate"
    if hazard_ids:
        return "unknown_or_damaged_candidate"
    return "low_voltage_or_unknown_candidate"


def _rows(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        return [{"label": value.strip()}]
    return []


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _bbox(value: Any) -> List[Any]:
    if isinstance(value, list) and len(value) == 4:
        return value
    if isinstance(value, dict):
        if all(key in value for key in ["x", "y", "w", "h"]):
            return [value["x"], value["y"], value["w"], value["h"]]
        if all(key in value for key in ["x1", "y1", "x2", "y2"]):
            return [value["x1"], value["y1"], value["x2"], value["y2"]]
    return []


def _item_text(item: Dict[str, Any]) -> str:
    parts = [
        item.get("label"),
        item.get("kind"),
        item.get("function"),
        item.get("notes"),
        item.get("marking"),
        item.get("visible_text"),
        " ".join(_string_list(item.get("warnings"))),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _normalize_capability(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "uart": "usb_serial",
        "usb_device_or_bridge": "usb_serial",
        "motor_driver": "actuator_driver",
        "regulator": "power",
        "sensor": "sensor_or_adc",
        "button": "switch_or_button",
        "switch": "switch_or_button",
        "led": "led_or_light",
    }
    return aliases.get(raw, raw)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "vision_candidate"


def _dedupe(items: Iterable[Any]) -> List[str]:
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


def _dedupe_rows(rows: Sequence[Dict[str, Any]], *, key_fields: Sequence[str]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = tuple(str(row.get(field) or "").lower() for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _dedupe_hazards(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("hazard_id") or ""), str(row.get("source") or ""))
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept
