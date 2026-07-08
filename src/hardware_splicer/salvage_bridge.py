from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from .build_compiler import ensure_circuit_import_path, resolve_build_id
from .module_resolver import (
    coalesce_resolved_modules,
    fill_salvage_gaps,
    infer_power_topology,
    merge_module_overrides,
    module_overrides_for_build,
    overrides_from_resource_plan,
    resolve_parts_to_modules,
    resolve_parts_to_modules_with_llm,
    salvage_plan_input_from_intake,
)
from .integrations.build_id_hints import keyword_build_id, reconcile_build_pick
from .salvage_intelligence import analyze_salvage_gaps, build_bringup_card
from .salvage_bom_estimate import build_salvage_bom_estimate
from .firmware_scaffold import generate_firmware_from_salvage
from .scratch_pipeline import (
    merge_goal_modules_with_inventory,
    module_ids_from_resolved,
    should_use_scratch_compose,
)


SCHEMA_VERSION = "hardware_splicer.salvage_bridge.v1"


def _keyword_build_id(
    goal: str,
    parts: List[Mapping[str, Any]],
    *,
    salvage_id: str = "",
) -> str | None:
    return keyword_build_id(goal, parts, salvage_id=salvage_id)


def _pick_build_id(
    goal: str,
    parts: List[Mapping[str, Any]],
    splice_plan: Mapping[str, Any],
    diy_plan: Mapping[str, Any],
) -> str | None:
    salvage_id = str((splice_plan.get("target") or {}).get("recommended_build_id") or "")
    diy_id = str(((diy_plan.get("project_intent") or {}).get("mapped_build_id")) or "")

    from .integrations.llm_policy import offline_salvage_enabled
    from .integrations.qwen_build_pick import call_qwen_build_pick, qwen_build_pick_enabled

    keyword_id = _keyword_build_id(goal, parts, salvage_id=salvage_id)
    llm_id: str | None = None
    llm_confidence = 0.0

    if qwen_build_pick_enabled() and not offline_salvage_enabled():
        pick = call_qwen_build_pick(
            goal=goal,
            parts=parts,
            planner_hints={
                "diy_mapped_build_id": diy_id,
                "splice_recommended_build_id": salvage_id,
                "planners_agree": bool(diy_id and diy_id == salvage_id),
                "keyword_build_hint": keyword_id,
            },
        )
        if pick.get("ok") and pick.get("build_id"):
            llm_id = str(pick["build_id"])
            llm_confidence = float(pick.get("confidence") or 0.75)

    reconciled = reconcile_build_pick(
        llm_id,
        keyword_id,
        diy_build_id=diy_id,
        splice_build_id=salvage_id,
        llm_confidence=llm_confidence,
    )
    if reconciled:
        return reconciled

    if keyword_id:
        return keyword_id
    if diy_id and salvage_id and diy_id == salvage_id:
        return diy_id
    if diy_id:
        return diy_id
    if salvage_id:
        return salvage_id

    return resolve_build_id(archetype="generic_mechatronics")


def build_intake_salvage_package(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    project_name: str | None = None,
    budget: Mapping[str, Any] | None = None,
    donor_context: Mapping[str, Any] | None = None,
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
    if donor_context:
        for key in ("analysis", "circuit", "functional_salvage", "donor_boards"):
            if key in donor_context and donor_context.get(key) is not None:
                payload[key] = donor_context[key]
    constraints_map = dict(constraints or {})
    splice_plan = SalvageSplicePlanner().plan(payload)
    diy_plan = build_diy_project_engineering_plan(payload)
    resolved_modules, salvage_resolution = resolve_parts_to_modules_with_llm(parts, goal=goal)
    resolved_modules = fill_salvage_gaps(resolved_modules, parts=parts)
    build_id = _pick_build_id(goal, parts, splice_plan, diy_plan) or ""

    from .catalog import CATALOG_BUILD_IDS

    explicit_build = str(
        constraints_map.get("target_build_id") or constraints_map.get("build_id") or ""
    ).strip()
    if explicit_build in CATALOG_BUILD_IDS:
        build_id = explicit_build

    from .integrations.qwen_workshop_review import (
        apply_workshop_review,
        call_qwen_workshop_review,
        workshop_review_enabled,
    )

    workshop_review: Dict[str, Any] = {"ok": False, "skipped": True}
    if workshop_review_enabled():
        workshop_review = call_qwen_workshop_review(
            goal=goal,
            parts=parts,
            resolved_modules=resolved_modules,
            constraints=constraints_map,
            recommended_build_id=build_id or None,
        )
        if workshop_review.get("ok"):
            resolved_modules = fill_salvage_gaps(
                apply_workshop_review(resolved_modules, workshop_review),
                parts=parts,
            )
            suggested = str(workshop_review.get("suggested_build_id") or "").strip()
            if suggested:
                build_id = (
                    reconcile_build_pick(
                        suggested,
                        keyword_build_id(goal, parts),
                        splice_build_id=build_id,
                    )
                    or build_id
                )
    salvage_resolution["workshop_review"] = workshop_review
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
    power_topology = infer_power_topology(parts, merged_modules, constraints=constraints_map)
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
    bringup_card = build_bringup_card(
        goal=goal,
        resolved_modules=merged_modules if use_scratch else resolved_modules,
        module_overrides=module_overrides,
        power_topology=power_topology,
        graph_input=graph_input,
    )
    resolved_for_bom = merged_modules if use_scratch else resolved_modules
    gap_analysis = analyze_salvage_gaps(
        goal=goal,
        parts=parts,
        resolved_modules=resolved_for_bom,
        constraints=constraints_map,
        power_topology=power_topology,
    )
    bom_estimate = build_salvage_bom_estimate(
        resolved_modules=resolved_for_bom,
        gap_analysis=gap_analysis,
        budget=budget,
    )
    module_id_list = [str(r.get("module_id") or "") for r in resolved_for_bom if r.get("module_id")]
    firmware_scaffold = generate_firmware_from_salvage(
        build_id=build_id or "salvage_build",
        bringup_card=bringup_card,
        module_ids=module_id_list,
        goal=goal,
    )
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
        "salvage_resolution": salvage_resolution,
        "gap_analysis": gap_analysis,
        "bringup_card": bringup_card,
        "bom_estimate": bom_estimate,
        "firmware_scaffold": firmware_scaffold,
    }


def resolve_salvage_compose_inputs(
    *,
    goal: str | None = None,
    phrase: str | None = None,
    parts: Sequence[Mapping[str, Any]] | None = None,
    donor_context: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    project_name: str | None = None,
    salvage_mode: bool = False,
    module_ids: Sequence[str] | None = None,
    canvas_nodes: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any] | None:
    """Map donor_context / salvage parts into compose_dispatch kwargs + salvage_package."""
    if canvas_nodes:
        return None
    donor = dict(donor_context or {})
    parts_list = [dict(row) for row in (parts or []) if isinstance(row, Mapping)]
    effective_goal = str(goal or phrase or project_name or "").strip()
    should_plan = bool(donor) or (bool(salvage_mode) and (parts_list or effective_goal))
    if not should_plan:
        return None
    if not effective_goal:
        effective_goal = "salvage splice carrier"

    pkg = build_intake_salvage_package(
        goal=effective_goal,
        parts=parts_list,
        constraints=dict(constraints or {}),
        project_name=project_name or effective_goal,
        donor_context=donor or None,
    )
    constraints_out = dict(constraints or {})
    graph_mode = str(pkg.get("graph_mode") or "scratch")
    resolved = [dict(row) for row in (pkg.get("resolved_modules") or []) if isinstance(row, Mapping)]
    compose_ids = list(module_ids or []) or list(pkg.get("compose_module_ids") or [])
    if not compose_ids and graph_mode == "scratch":
        compose_ids = module_ids_from_resolved(resolved)

    compose: Dict[str, Any] = {
        "phrase": effective_goal,
        "salvage_mode": True,
        "material_mode": "salvage",
        "constraints": constraints_out,
        "allow_llm_first": False,
        "salvage_package": pkg,
    }
    if graph_mode == "catalog" and pkg.get("recommended_build_id"):
        compose["build_id"] = str(pkg["recommended_build_id"])
        graph_input = pkg.get("graph_input")
        if isinstance(graph_input, Mapping):
            compose["splice_plan"] = dict(graph_input)
        compose["resolved_modules"] = resolved or None
    else:
        compose["module_ids"] = compose_ids or None
        compose["resolved_modules"] = resolved or None
    return compose
