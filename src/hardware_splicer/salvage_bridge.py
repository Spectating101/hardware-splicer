from __future__ import annotations

from typing import Any, Dict, List, Mapping

from .build_compiler import ensure_circuit_import_path, resolve_build_id
from .module_resolver import (
    coalesce_resolved_modules,
    infer_power_topology,
    merge_module_overrides,
    module_overrides_for_build,
    overrides_from_resource_plan,
    resolve_parts_to_modules,
    salvage_plan_input_from_intake,
)
from .scratch_pipeline import (
    merge_goal_modules_with_inventory,
    module_ids_from_resolved,
    should_use_scratch_compose,
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
    if any(
        word in text
        for word in ["tft", "oled", "display station", "room display", "room temp", "ili9341"]
    ):
        return "room_display_station"
    if any(word in text for word in ["relay box", "smart relay", "relay module", "desk lamp"]):
        return "smart_relay_box"
    if any(
        word in text
        for word in ["sensor logger", "bme280", "log temperature", "environment sensor", "data logger"]
    ):
        return "sensor_logger"
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
    constraints_map = dict(constraints or {})
    strategy_mode = str(
        ((diy_plan.get("resource_plan") or {}).get("strategy_mode"))
        or constraints_map.get("strategy_mode")
        or "constrained"
    )
    constrained = strategy_mode == "constrained" or constraints_map.get("compose_from_inventory") is True
    merged_modules = merge_goal_modules_with_inventory(
        goal,
        resolved_modules,
        constrained=constrained,
    )
    power_topology = infer_power_topology(parts, merged_modules)
    merged_modules = coalesce_resolved_modules(parts, merged_modules, power_topology=power_topology)
    use_scratch = should_use_scratch_compose(
        goal=goal,
        build_id=build_id or None,
        resolved_modules=merged_modules,
        constraints=constraints_map,
        strategy_mode=strategy_mode,
    )
    if use_scratch:
        build_id = "generic_low_voltage_build"
    if build_id:
        target = dict(splice_plan.get("target") or {})
        target["recommended_build_id"] = build_id
        splice_plan = {**splice_plan, "target": target}
    resource_overrides = overrides_from_resource_plan(diy_plan)
    inventory_overrides = module_overrides_for_build(
        build_id=build_id or None,
        resolved_modules=merged_modules if use_scratch else resolved_modules,
    )
    module_overrides = merge_module_overrides(inventory_overrides, resource_overrides)
    if power_topology == "usb_5v":
        module_overrides["pwr"] = "usb-power-5v"
        for drop_role in ("buck", "psu", "mot_psu", "svo_psu"):
            module_overrides.pop(drop_role, None)
    graph_input = salvage_plan_input_from_intake(
        splice_plan,
        resolved_modules=merged_modules if use_scratch else resolved_modules,
        module_overrides=module_overrides,
        power_topology=power_topology,
        strategy_mode=strategy_mode,
        compose_from_inventory=use_scratch,
    )
    graph_mode = "scratch" if use_scratch else "catalog"
    return {
        "schema_version": SCHEMA_VERSION,
        "splice_plan": splice_plan,
        "diy_plan": diy_plan,
        "resolved_modules": merged_modules if use_scratch else resolved_modules,
        "module_overrides": module_overrides,
        "power_topology": power_topology,
        "strategy_mode": strategy_mode,
        "graph_mode": graph_mode,
        "compose_module_ids": module_ids_from_resolved(merged_modules) if use_scratch else [],
        "graph_input": graph_input,
        "recommended_build_id": build_id or None,
        "verdict": splice_plan.get("verdict"),
        "planning_confidence": float(splice_plan.get("confidence") or 0.0),
    }
