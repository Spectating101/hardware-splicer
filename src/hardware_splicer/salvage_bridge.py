from __future__ import annotations

from typing import Any, Dict, List, Mapping

from .build_compiler import ensure_circuit_import_path, resolve_build_id
from .module_resolver import (
    module_overrides_for_build,
    resolve_parts_to_modules,
    salvage_plan_input_from_intake,
)


SCHEMA_VERSION = "hardware_splicer.salvage_bridge.v1"


def _pick_build_id(
    goal: str,
    parts: List[Mapping[str, Any]],
    splice_plan: Mapping[str, Any],
    diy_plan: Mapping[str, Any],
) -> str | None:
    text = " ".join(
        [goal]
        + [str(part.get("name") or "") + " " + str(part.get("type") or "") for part in parts]
    ).lower()
    salvage_id = str((splice_plan.get("target") or {}).get("recommended_build_id") or "")
    diy_id = str(((diy_plan.get("project_intent") or {}).get("mapped_build_id")) or "")

    if any(word in text for word in ["soil", "water", "watering", "pump", "irrigation", "plant"]):
        return "automatic_plant_watering"
    if any(word in text for word in ["rover", "wheel", "wheeled", "robot car", "drive motor"]):
        return "robot_drive_base"
    if any(word in text for word in ["fan", "airflow", "vent", "blower", "fume"]):
        return "usb_fume_extractor"
    if any(word in text for word in ["pan", "tilt", "camera mount", "gimbal"]):
        return "inspection_motion_fixture"
    if any(word in text for word in ["gripper", "claw", "grab"]):
        return "low_voltage_motor_test_jig"
    if diy_id:
        return diy_id
    if salvage_id:
        return salvage_id
    if salvage_id == "sensor_logger" and any("pump" in str(part.get("type") or "").lower() for part in parts):
        return "automatic_plant_watering"
    return resolve_build_id(archetype="generic_mechatronics")


def build_intake_salvage_package(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    project_name: str | None = None,
) -> Dict[str, Any]:
    """Run Circuit-AI salvage + DIY planners on intake-normalized parts."""
    ensure_circuit_import_path()
    from src.intelligence.diy_project_engineer import build_diy_project_engineering_plan
    from src.intelligence.salvage_splice_planner import SalvageSplicePlanner

    payload: Dict[str, Any] = {
        "goal": goal,
        "title": project_name or goal,
        "available_parts": parts,
        "inventory": parts,
        "constraints": dict(constraints or {}),
    }
    splice_plan = SalvageSplicePlanner().plan(payload)
    diy_plan = build_diy_project_engineering_plan(payload)
    resolved_modules = resolve_parts_to_modules(parts)
    build_id = _pick_build_id(goal, parts, splice_plan, diy_plan) or ""
    if build_id:
        target = dict(splice_plan.get("target") or {})
        target["recommended_build_id"] = build_id
        splice_plan = {**splice_plan, "target": target}
    module_overrides = module_overrides_for_build(
        build_id=build_id or None,
        resolved_modules=resolved_modules,
    )
    graph_input = salvage_plan_input_from_intake(
        splice_plan,
        resolved_modules=resolved_modules,
        module_overrides=module_overrides,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "splice_plan": splice_plan,
        "diy_plan": diy_plan,
        "resolved_modules": resolved_modules,
        "module_overrides": module_overrides,
        "graph_input": graph_input,
        "recommended_build_id": build_id or None,
        "verdict": splice_plan.get("verdict"),
        "planning_confidence": float(splice_plan.get("confidence") or 0.0),
    }
