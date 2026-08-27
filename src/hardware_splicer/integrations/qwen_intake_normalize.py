"""Model-first intake normalization with explicit legacy/offline provenance.

Natural-language archetype interpretation is semantic reasoning. On model-first paths a
failed or unresolved model proposal must therefore remain unresolved rather than being
silently replaced by the historical keyword classifier. The keyword path survives only
when the product is explicitly operating in legacy/offline mode, and is labeled as such.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from ..build_compiler import ARCHETYPE_BUILD_IDS
from .build_id_hints import keyword_build_id, reconcile_build_pick_with_provenance
from .llm_policy import offline_salvage_enabled, qwen_llm_first
from .qwen_build_pick import call_qwen_build_pick
from .qwen_salvage_resolver import call_qwen_salvage_map_intake

SCHEMA_VERSION = "hardware_splicer.qwen_intake_normalize.v2"
UNRESOLVED_ARCHETYPE = "generic_mechatronics"

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


def _archetype_from_build_id(build_id: str | None) -> str | None:
    candidate = str(build_id or "").strip()
    if not candidate:
        return None
    for archetype, registered_build_id in ARCHETYPE_BUILD_IDS.items():
        if registered_build_id == candidate:
            return archetype
    return _BUILD_TO_ARCHETYPE.get(candidate)


def detect_archetype_proposal(goal: str, parts: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """Return archetype interpretation together with provenance and authority state.

    Model-first mode never falls through to the keyword classifier. Explicit offline or
    non-model mode may still use the legacy classifier for compatibility, but the result
    is labeled ``legacy_heuristic`` and has zero authority effect.
    """
    legacy_mode = bool(not qwen_llm_first() or offline_salvage_enabled())
    if legacy_mode:
        legacy_build_id = keyword_build_id(goal, parts)
        archetype = _archetype_from_build_id(legacy_build_id) or _detect_archetype_keywords(goal, parts)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "legacy_heuristic",
            "archetype": archetype,
            "build_id": legacy_build_id,
            "source": "legacy_keyword",
            "confidence": 0.0,
            "reasoning": "Legacy/offline compatibility classifier; not engineering truth.",
            "unresolved_questions": [],
            "authority_effect": "none",
            "automatic_execution": False,
        }

    pick = call_qwen_build_pick(goal=goal, parts=list(parts))
    model_build_id = pick.get("build_id") if pick.get("ok") else None
    decision = reconcile_build_pick_with_provenance(
        str(model_build_id) if model_build_id else None,
        None,
        llm_confidence=float(pick.get("confidence") or 0.0) if pick.get("ok") else 0.0,
        allow_legacy_fallback=False,
    )
    archetype = _archetype_from_build_id(decision.get("build_id"))
    if archetype:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "model_proposed",
            "archetype": archetype,
            "build_id": decision.get("build_id"),
            "source": "model_proposed",
            "confidence": decision.get("confidence", 0.0),
            "reasoning": str(pick.get("reasoning") or ""),
            "unresolved_questions": list(pick.get("unresolved_questions") or []),
            "authority_effect": "none",
            "automatic_execution": False,
        }

    reason = str(
        pick.get("message")
        or pick.get("reason")
        or pick.get("error")
        or pick.get("reasoning")
        or "No bounded catalog build was defensibly selected by the model."
    )
    unresolved = [
        str(row).strip()
        for row in list(pick.get("unresolved_questions") or [])[:24]
        if str(row).strip()
    ]
    if not unresolved:
        unresolved = [reason]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "unresolved",
        "archetype": UNRESOLVED_ARCHETYPE,
        "build_id": None,
        "source": "unresolved",
        "confidence": 0.0,
        "reasoning": reason,
        "unresolved_questions": unresolved,
        "authority_effect": "none",
        "automatic_execution": False,
    }


def detect_archetype_llm(goal: str, parts: List[Mapping[str, Any]]) -> str:
    """Compatibility projection returning only the archetype string.

    New code should prefer :func:`detect_archetype_proposal` so provenance is not lost.
    On model-first failure this returns ``generic_mechatronics`` as an unresolved neutral
    projection, never a keyword-selected architecture.
    """
    proposal = detect_archetype_proposal(goal, parts)
    return str(proposal.get("archetype") or UNRESOLVED_ARCHETYPE)


def _detect_archetype_keywords(goal: str, parts: List[Mapping[str, Any]]) -> str:
    """Legacy/offline compatibility classifier. Never authoritative."""
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
    return UNRESOLVED_ARCHETYPE


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
