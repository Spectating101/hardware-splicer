"""Qwen intake normalization — archetype + part typing (replaces keyword scaffolds)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping

from ..build_compiler import ARCHETYPE_BUILD_IDS
from .build_id_hints import keyword_build_id
from .llm_policy import offline_salvage_enabled, qwen_llm_first
from .build_id_hints import keyword_build_id, reconcile_build_pick
from .qwen_build_pick import call_qwen_build_pick
from .qwen_salvage_resolver import call_qwen_salvage_map_intake
from .qwen_text_client import qwen_configured

SCHEMA_VERSION = "hardware_splicer.qwen_intake_normalize.v1"

_BUILD_TO_ARCHETYPE = {
    "automatic_plant_watering": "automatic_watering",
    "automatic_plant_watering_usb": "automatic_watering",
    "robot_drive_base": "rover",
    "usb_fume_extractor": "airflow_controller",
    "inspection_motion_fixture": "pan_tilt",
    "low_voltage_motor_test_jig": "gripper",
    "sensor_logger": "sensor_logger",
    "generic_low_voltage_build": "generic_mechatronics",
}


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def detect_archetype_llm(goal: str, parts: List[Mapping[str, Any]]) -> str:
    """LLM archetype from goal+parts; offline uses keyword fallback in project_intake."""
    if not qwen_llm_first() or offline_salvage_enabled():
        return _detect_archetype_keywords(goal, parts)

    pick = call_qwen_build_pick(goal=goal, parts=list(parts))
    if pick.get("ok") and pick.get("build_id"):
        build_id = reconcile_build_pick(
            str(pick["build_id"]),
            keyword_build_id(goal, parts),
            llm_confidence=float(pick.get("confidence") or 0.75),
        ) or str(pick["build_id"])
        for archetype, bid in ARCHETYPE_BUILD_IDS.items():
            if bid == build_id:
                return archetype
        if build_id in _BUILD_TO_ARCHETYPE:
            return _BUILD_TO_ARCHETYPE[build_id]

    return _detect_archetype_keywords(goal, parts)


def _detect_archetype_keywords(goal: str, parts: List[Mapping[str, Any]]) -> str:
    hinted = keyword_build_id(goal, parts)
    if hinted and hinted in _BUILD_TO_ARCHETYPE:
        return _BUILD_TO_ARCHETYPE[hinted]
    text = " ".join(
        [goal] + [str(part.get("name") or "") + " " + str(part.get("type") or "") for part in parts]
    ).lower()
    if any(word in text for word in ["soil", "water", "watering", "pump", "irrigation", "plant"]):
        return "automatic_watering"
    if any(word in text for word in ["rover", "wheel", "wheeled", "robot car", "drive motor"]):
        return "rover"
    if any(word in text for word in ["fan", "airflow", "vent", "blower"]):
        return "airflow_controller"
    if any(word in text for word in ["pan", "tilt", "camera mount", "gimbal"]):
        return "pan_tilt"
    if any(word in text for word in ["gripper", "claw", "grab"]):
        return "gripper"
    return "generic_mechatronics"


def classify_intake_parts_llm(
    goal: str,
    parts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Enrich intake parts with type/class fields via Qwen (batch)."""
    if not parts:
        return parts
    if not qwen_llm_first() or offline_salvage_enabled():
        return parts

    need = [
        p
        for p in parts
        if not str(p.get("type") or "").strip()
        or str(p.get("type") or "").strip().lower() in {"part", "material", "unknown"}
    ]
    if not need:
        return parts

    mapped = call_qwen_salvage_map_intake(goal=goal, parts=need)
    if not mapped.get("ok"):
        return parts

    by_name = {str(r.get("part_name") or "").lower(): r for r in mapped.get("resolved") or []}
    out: List[Dict[str, Any]] = []
    for part in parts:
        row = dict(part)
        hit = by_name.get(str(row.get("name") or "").lower())
        if hit:
            row.setdefault("type", _role_to_type(str(hit.get("role") or "")))
            row.setdefault("class", _role_to_class(str(hit.get("role") or "")))
            if hit.get("module_id"):
                row.setdefault("module_id", hit.get("module_id"))
        out.append(row)
    return out


def _role_to_type(role: str) -> str:
    return {
        "mcu": "microcontroller",
        "sns": "sensor",
        "mot": "dc_motor",
        "load": "load",
        "drv": "driver",
        "pwr": "power_source",
        "act": "actuator",
    }.get(role, role or "part")


def _role_to_class(role: str) -> str:
    return {
        "mcu": "controller",
        "sns": "sensor",
        "mot": "actuator",
        "load": "actuator",
        "drv": "driver",
        "pwr": "power",
        "act": "actuator",
    }.get(role, "material")
