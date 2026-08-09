from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .build_compiler import ensure_circuit_import_path
from .module_resolver import (
    merge_module_overrides,
    overrides_from_resource_plan,
    salvage_plan_input_from_intake,
)
from .module_resolution_truth import (
    SCHEMA_VERSION as MODULE_IDENTITY_SCHEMA,
    fill_capability_gaps,
    functional_salvage_identity_rows,
    infer_power_topology_truth,
    merge_truth_rows,
    module_overrides_truth,
    resolve_inventory_identity,
)
from .integrations.build_id_hints import keyword_build_id, reconcile_build_pick_with_provenance
from .salvage_intelligence import analyze_salvage_gaps, build_bringup_card
from .salvage_bom_estimate import build_salvage_bom_estimate
from .firmware_scaffold import generate_firmware_from_salvage
from .mechanism_bridge import build_mecha_project_spec
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


def _pick_build_decision(
    goal: str,
    parts: List[Mapping[str, Any]],
    splice_plan: Mapping[str, Any],
    diy_plan: Mapping[str, Any],
) -> Dict[str, Any]:
    salvage_id = str((splice_plan.get("target") or {}).get("recommended_build_id") or "")
    diy_id = str(((diy_plan.get("project_intent") or {}).get("mapped_build_id")) or "")

    from .integrations.llm_policy import offline_salvage_enabled
    from .integrations.qwen_build_pick import call_qwen_build_pick, qwen_build_pick_enabled

    offline = offline_salvage_enabled()
    # Keyword routing is historical semantic machinery. Do not execute it in
    # model-first mode merely to record a shadow answer.
    keyword_id = _keyword_build_id(goal, parts, salvage_id=salvage_id) if offline else None
    ignored = {
        "keyword": keyword_id or None,
        "diy": diy_id or None,
        "splice": salvage_id or None,
    }

    if offline:
        decision = reconcile_build_pick_with_provenance(
            None,
            keyword_id,
            diy_build_id=diy_id,
            splice_build_id=salvage_id,
            allow_legacy_fallback=True,
        )
        return {
            **decision,
            "reasoning": "Explicit offline compatibility may use historical build-selection signals.",
            "unresolved_questions": [],
            "legacy_planner_ids_ignored": {},
        }

    if qwen_build_pick_enabled():
        pick = call_qwen_build_pick(goal=goal, parts=parts, planner_hints={})
        if pick.get("ok") and pick.get("build_id"):
            decision = reconcile_build_pick_with_provenance(
                str(pick.get("build_id") or ""),
                None,
                llm_confidence=float(pick.get("confidence") or 0.0),
                allow_legacy_fallback=False,
            )
            return {
                **decision,
                "reasoning": str(pick.get("reasoning") or ""),
                "unresolved_questions": list(pick.get("unresolved_questions") or []),
                "legacy_planner_ids_ignored": ignored,
                "model": pick.get("model"),
            }
        return {
            "build_id": None,
            "source": "unresolved",
            "confidence": 0.0,
            "authority_effect": "none",
            "legacy_fallback_used": False,
            "reasoning": str(
                pick.get("message")
                or pick.get("error")
                or "Semantic build selector did not resolve a bounded catalog architecture."
            ),
            "unresolved_questions": list(pick.get("unresolved_questions") or [])
            or ["Resolve a bounded build architecture from project evidence before selecting a catalog recipe."],
            "legacy_planner_ids_ignored": ignored,
        }

    return {
        "build_id": None,
        "source": "unresolved",
        "confidence": 0.0,
        "authority_effect": "none",
        "legacy_fallback_used": False,
        "reasoning": "Semantic build selection is unavailable; legacy planner IDs are not architecture truth in model-first mode.",
        "unresolved_questions": [
            "Resolve a bounded build architecture from project evidence before selecting a catalog recipe."
        ],
        "legacy_planner_ids_ignored": ignored,
    }


def _pick_build_id(
    goal: str,
    parts: List[Mapping[str, Any]],
    splice_plan: Mapping[str, Any],
    diy_plan: Mapping[str, Any],
) -> str | None:
    return _pick_build_decision(goal, parts, splice_plan, diy_plan).get("build_id")


def _sanitize_legacy_splice_plan(
    splice_plan: Mapping[str, Any],
    *,
    offline: bool,
    executed: bool = True,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Quarantine legacy guesses, or record that model-first never executed them."""
    body = dict(splice_plan or {})
    if offline:
        return body, {
            "executed": executed,
            "quarantined": False,
            "legacy_recommended_build_id": None,
            "legacy_reusable_block_count": 0,
        }

    if not executed:
        return {
            "target": dict(body.get("target") or {}),
            "reusable_blocks": [],
            "architecture_authority": "not_executed_model_first",
        }, {
            "executed": False,
            "quarantined": False,
            "legacy_recommended_build_id": None,
            "legacy_reusable_block_count": 0,
        }

    target = dict(body.get("target") or {})
    legacy_build = str(target.pop("recommended_build_id", "") or "").strip() or None
    legacy_blocks = list(body.get("reusable_blocks") or [])
    if legacy_build:
        target["legacy_recommended_build_id_ignored"] = legacy_build
    body["target"] = target
    if legacy_blocks:
        body["legacy_reusable_blocks_ignored"] = legacy_blocks
    body["reusable_blocks"] = []
    body["architecture_authority"] = "ignored_legacy_heuristic"
    return body, {
        "executed": True,
        "quarantined": True,
        "legacy_recommended_build_id": legacy_build,
        "legacy_reusable_block_count": len(legacy_blocks),
    }


def _identity_summary(
    rows: Sequence[Mapping[str, Any]],
    resolution: Mapping[str, Any],
    *,
    offline: bool,
) -> Dict[str, Any]:
    physical_rows = [
        row
        for row in rows
        if str(row.get("source") or "")
        in {"declared_catalog_identity", "model_identity_proposed", "unresolved_identity"}
    ]
    donor_rows = [
        row
        for row in rows
        if str(row.get("source") or "").startswith("donor_functional_salvage")
    ]
    return {
        "schema_version": MODULE_IDENTITY_SCHEMA,
        "mode": "offline_compatibility" if offline else "model_first_identity",
        "resolved_physical_identity_count": sum(bool(row.get("module_id")) for row in physical_rows),
        "unresolved_physical_identity_count": sum(not bool(row.get("module_id")) for row in physical_rows),
        "external_donor_capability_count": sum(bool(row.get("external_capability_only")) for row in donor_rows),
        "unresolved_capability_gap_count": sum(
            str(row.get("source") or "") == "unresolved_capability_gap" for row in rows
        ),
        "legacy_heuristic_used": bool(
            resolution.get("mode") not in {None, "model_first_identity"}
        )
        if offline
        else False,
        "functional_similarity_is_identity": False if not offline else None,
        "authority_effect": "none",
    }


def build_intake_salvage_package(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    project_name: str | None = None,
    budget: Mapping[str, Any] | None = None,
    donor_context: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build a salvage package while keeping physical identity distinct from capability."""
    ensure_circuit_import_path()
    from .integrations.llm_policy import offline_salvage_enabled

    offline = offline_salvage_enabled()
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
    if offline:
        from src.intelligence.diy_project_engineer import build_diy_project_engineering_plan
        from src.intelligence.salvage_splice_planner import SalvageSplicePlanner

        legacy_splice_plan = SalvageSplicePlanner().plan(payload)
        diy_plan = build_diy_project_engineering_plan(payload)
    else:
        # Model-first mode must not run legacy semantic planners even as shadow
        # evaluators. Their absence is explicit audit state, not an empty vote.
        legacy_splice_plan = {}
        diy_plan = {}

    build_selection = _pick_build_decision(goal, parts, legacy_splice_plan, diy_plan)
    splice_plan, legacy_quarantine = _sanitize_legacy_splice_plan(
        legacy_splice_plan,
        offline=offline,
        executed=offline,
    )

    # Model-first donor capability truth comes only from persisted donor context.
    # Historical planner-generated blocks exist only in explicit offline compatibility.
    if offline:
        fs_context: Dict[str, Any] = {
            **dict(donor_context or {}),
            "splice_plan": legacy_splice_plan,
            "reusable_blocks": list(legacy_splice_plan.get("reusable_blocks") or []),
        }
    else:
        fs_context = dict(donor_context or {})

    fs_rows = functional_salvage_identity_rows(fs_context, parts=parts)
    inventory_rows, salvage_resolution = resolve_inventory_identity(parts, goal=goal)
    resolved_modules = merge_truth_rows(fs_rows, inventory_rows)
    resolved_modules = fill_capability_gaps(resolved_modules, parts=parts)

    salvage_resolution = dict(salvage_resolution or {})
    salvage_resolution["physical_identity_boundary"] = _identity_summary(
        resolved_modules,
        salvage_resolution,
        offline=offline,
    )
    salvage_resolution["legacy_planner_quarantine"] = legacy_quarantine
    salvage_resolution["functional_salvage_bound"] = {
        "rows": len(fs_rows),
        "donor_block_ids": [
            str(row.get("donor_block_id") or "")
            for row in fs_rows
            if row.get("donor_block_id")
        ],
        "external_capability_rows": sum(
            bool(row.get("external_capability_only")) for row in fs_rows
        ),
        "declared_catalog_identity_rows": sum(bool(row.get("module_id")) for row in fs_rows),
        "driver_capability_present": any(str(row.get("role") or "") == "drv" for row in fs_rows),
        "catalog_standin_required": False if not offline else None,
    }

    build_id = str(build_selection.get("build_id") or "")
    from .catalog import CATALOG_BUILD_IDS

    explicit_build = str(
        constraints_map.get("target_build_id") or constraints_map.get("build_id") or ""
    ).strip()
    if explicit_build in CATALOG_BUILD_IDS:
        build_id = explicit_build
        build_selection = {
            "build_id": explicit_build,
            "source": "declared",
            "confidence": 1.0,
            "authority_effect": "none",
            "legacy_fallback_used": False,
            "reasoning": "Explicit target_build_id/build_id persisted in project constraints.",
            "unresolved_questions": [],
            "legacy_planner_ids_ignored": build_selection.get("legacy_planner_ids_ignored") or {},
        }

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
            if offline:
                resolved_modules = apply_workshop_review(resolved_modules, workshop_review)
                resolved_modules = fill_capability_gaps(resolved_modules, parts=parts)
                suggested = str(workshop_review.get("suggested_build_id") or "").strip()
                if suggested:
                    build_selection = reconcile_build_pick_with_provenance(
                        suggested,
                        _keyword_build_id(goal, parts),
                        splice_build_id=build_id,
                        allow_legacy_fallback=True,
                    )
                    build_id = str(build_selection.get("build_id") or build_id)
            else:
                workshop_review = {
                    **workshop_review,
                    "application_status": "advisory_only_model_first",
                    "physical_identity_mutated": False,
                    "architecture_mutated": False,
                    "authority_effect": "none",
                }
    salvage_resolution["workshop_review"] = workshop_review

    strategy_mode = str(
        ((diy_plan.get("resource_plan") or {}).get("strategy_mode") if offline else None)
        or constraints_map.get("strategy_mode")
        or "constrained"
    )
    constrained = (
        strategy_mode == "constrained"
        or constraints_map.get("compose_from_inventory") is True
    )
    merged_modules = merge_goal_modules_with_inventory(
        goal,
        resolved_modules,
        constrained=constrained,
    )
    power_topology = infer_power_topology_truth(
        parts,
        merged_modules,
        constraints=constraints_map,
    )

    use_scratch = should_use_scratch_compose(
        goal=goal,
        build_id=build_id or None,
        resolved_modules=merged_modules,
        constraints=constraints_map,
        strategy_mode=strategy_mode,
    )
    from .scratch_pipeline import NAMED_CATALOG_BUILD_IDS

    if use_scratch and str(build_id or "") not in NAMED_CATALOG_BUILD_IDS:
        # Scratch is an execution mechanism, not architecture truth.
        build_id = "generic_low_voltage_build" if offline else ""
    if build_id:
        target = dict(splice_plan.get("target") or {})
        target["recommended_build_id"] = build_id
        target["recommendation_source"] = str(build_selection.get("source") or "unknown")
        splice_plan = {**splice_plan, "target": target}

    resource_overrides = overrides_from_resource_plan(diy_plan) if offline else {}
    inventory_overrides = module_overrides_truth(
        merged_modules if use_scratch else resolved_modules,
        build_id=build_id or None,
    )
    module_overrides = merge_module_overrides(resource_overrides, inventory_overrides)
    if offline and power_topology == "usb_5v":
        # Historical compatibility only. A topology requirement is not exact identity.
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
    module_id_list = [
        str(row.get("module_id") or "")
        for row in resolved_for_bom
        if row.get("module_id")
    ]
    firmware_scaffold = generate_firmware_from_salvage(
        build_id=build_id or "salvage_build",
        bringup_card=bringup_card,
        module_ids=module_id_list,
        goal=goal,
    )
    mech_plan = build_mecha_project_spec(
        project_name=str(project_name or build_id or "salvage_mech"),
        build_id=str(build_id or ""),
        goal=goal,
        resolved_modules=resolved_for_bom,
    )
    mechanism_pack = {
        "schema_version": "hardware_splicer.mechanism_pack.v1",
        "status": "planned",
        "kind": mech_plan["kind"],
        "project_spec": mech_plan["project_spec"],
        "outputs": [],
        "parts": [],
        "bundle_dir": None,
        "claim_boundary": "Starter printable pack from electronics roles — verify fit on bench.",
        "degraded_reason": None,
    }

    package = {
        "schema_version": SCHEMA_VERSION,
        "splice_plan": splice_plan,
        "diy_plan": diy_plan,
        "resolved_modules": resolved_for_bom,
        "module_overrides": module_overrides,
        "power_topology": power_topology,
        "power_topology_status": (
            "resolved"
            if power_topology in {"usb_5v", "barrel_12v", "hybrid"}
            else "unresolved"
        ),
        "strategy_mode": strategy_mode,
        "graph_mode": graph_mode,
        "compose_module_ids": module_ids_from_resolved(merged_modules) if use_scratch else [],
        "graph_input": graph_input,
        "recommended_build_id": build_id or None,
        "build_selection": build_selection,
        "legacy_planner_architecture_authority": (
            "compatibility_only" if offline else "not_executed"
        ),
        "legacy_planner_context": {
            **legacy_quarantine,
            "diy_mapped_build_id": str(
                ((diy_plan.get("project_intent") or {}).get("mapped_build_id")) or ""
            )
            or None,
            "diy_architecture_authority": "compatibility_only" if offline else "not_executed",
        },
        "physical_identity_schema": MODULE_IDENTITY_SCHEMA,
        "physical_identity_authority": (
            "declared_or_validated_exact_only"
            if not offline
            else "legacy_compatibility"
        ),
        "verdict": splice_plan.get("verdict"),
        "planning_confidence": float(splice_plan.get("confidence") or 0.0),
        "salvage_resolution": salvage_resolution,
        "gap_analysis": gap_analysis,
        "bringup_card": bringup_card,
        "bom_estimate": bom_estimate,
        "firmware_scaffold": firmware_scaffold,
        "mechanism_pack": mechanism_pack,
    }
    from .evidence_salvage_bridge import attach_evidence_first_integrations

    return attach_evidence_first_integrations(package)


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
    resolved = [
        dict(row)
        for row in (pkg.get("resolved_modules") or [])
        if isinstance(row, Mapping)
    ]
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


def write_compose_salvage_bench_artifacts(
    out_dir: str | Path,
    *,
    salvage_package: Mapping[str, Any],
    goal: str = "",
    project_name: str = "",
    donor_context: Mapping[str, Any] | None = None,
    parts: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, str]:
    root = Path(out_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    pkg = dict(salvage_package)
    paths: Dict[str, str] = {}

    splice_plan_path = root / "SPLICE_PLAN.json"
    splice_plan_path.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
    paths["splice_plan"] = str(splice_plan_path)

    intake_snapshot: Dict[str, Any] = {
        "project_name": project_name or goal or root.name,
        "goal": goal or project_name or root.name,
        "salvage_mode": True,
        "recommended_build_id": pkg.get("recommended_build_id"),
        "available_parts": [
            dict(row)
            for row in (parts or [])
            if isinstance(row, Mapping)
        ],
    }
    donor = dict(donor_context or {})
    for key in ("circuit", "functional_salvage", "donor_boards", "analysis", "evidence_notes"):
        if donor.get(key) is not None:
            intake_snapshot[key] = donor[key]
    intake_path = root / "PROJECT_INTAKE.json"
    intake_path.write_text(json.dumps(intake_snapshot, indent=2), encoding="utf-8")
    paths["project_intake"] = str(intake_path)

    if isinstance(pkg.get("bringup_card"), Mapping):
        bringup_path = root / "BRINGUP_CARD.json"
        bringup_path.write_text(json.dumps(pkg["bringup_card"], indent=2), encoding="utf-8")
        paths["bringup_card"] = str(bringup_path)
    if isinstance(pkg.get("gap_analysis"), Mapping):
        gap_path = root / "SALVAGE_GAP_ANALYSIS.json"
        gap_path.write_text(json.dumps(pkg["gap_analysis"], indent=2), encoding="utf-8")
        paths["gap_analysis"] = str(gap_path)

    return paths
