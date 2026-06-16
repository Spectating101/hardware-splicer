"""Incremental salvage edits and package diffs."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Set

SCHEMA_VERSION = "hardware_splicer.salvage_revision.v1"


def _module_ids(rows: List[Mapping[str, Any]]) -> Set[str]:
    return {str(r.get("module_id") or "").strip() for r in rows if r.get("module_id")}


def diff_salvage_packages(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, Any]:
    """Human-readable diff between two salvage packages."""
    b_mods = _module_ids(list(before.get("resolved_modules") or []))
    a_mods = _module_ids(list(after.get("resolved_modules") or []))
    added = sorted(a_mods - b_mods)
    removed = sorted(b_mods - a_mods)
    return {
        "schema_version": SCHEMA_VERSION,
        "build_id_before": before.get("recommended_build_id"),
        "build_id_after": after.get("recommended_build_id"),
        "build_id_changed": before.get("recommended_build_id") != after.get("recommended_build_id"),
        "modules_added": added,
        "modules_removed": removed,
        "power_topology_before": before.get("power_topology"),
        "power_topology_after": after.get("power_topology"),
        "graph_mode_before": before.get("graph_mode"),
        "graph_mode_after": after.get("graph_mode"),
        "ready_before": (before.get("gap_analysis") or {}).get("ready_to_compile"),
        "ready_after": (after.get("gap_analysis") or {}).get("ready_to_compile"),
    }


def apply_salvage_edits(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None,
    edits: List[Mapping[str, Any]],
    project_name: str | None = None,
    base_package: Mapping[str, Any] | None = None,
    budget: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Apply edit ops then rebuild salvage package. Ops: add_part, remove_part, add_module, remove_module."""
    from .salvage_bridge import build_intake_salvage_package

    parts_copy = [dict(p) for p in parts]
    extra_modules: List[Dict[str, Any]] = []
    drop_module_ids: Set[str] = set()

    for edit in edits:
        op = str(edit.get("op") or "").strip().lower()
        if op == "add_part":
            part = dict(edit.get("part") or {})
            if part.get("name"):
                parts_copy.append(part)
        elif op == "remove_part":
            name = str(edit.get("name") or "").strip().lower()
            parts_copy = [p for p in parts_copy if str(p.get("name") or "").strip().lower() != name]
        elif op == "add_module":
            mid = str(edit.get("module_id") or "").strip()
            if mid:
                extra_modules.append({"module_id": mid, "role": edit.get("role") or "user", "source": "edit"})
        elif op == "remove_module":
            mid = str(edit.get("module_id") or "").strip()
            if mid:
                drop_module_ids.add(mid)

    before = dict(base_package) if base_package else None
    after = build_intake_salvage_package(
        goal=goal,
        parts=parts_copy,
        constraints=dict(constraints or {}),
        project_name=project_name,
        budget=budget,
    )

    if drop_module_ids or extra_modules:
        merged = [dict(r) for r in after.get("resolved_modules") or []]
        merged = [r for r in merged if str(r.get("module_id") or "") not in drop_module_ids]
        existing = _module_ids(merged)
        for row in extra_modules:
            if row["module_id"] not in existing:
                merged.append(row)
        from .salvage_intelligence import analyze_salvage_gaps, build_bringup_card

        after["resolved_modules"] = merged
        after["gap_analysis"] = analyze_salvage_gaps(
            goal=goal,
            parts=parts_copy,
            resolved_modules=merged,
            constraints=constraints,
            power_topology=after.get("power_topology"),
        )
        after["bringup_card"] = build_bringup_card(
            goal=goal,
            resolved_modules=merged,
            module_overrides=after.get("module_overrides") or {},
            power_topology=after.get("power_topology"),
            graph_input=after.get("graph_input"),
        )

    from .firmware_scaffold import generate_firmware_from_salvage
    from .salvage_bom_estimate import build_salvage_bom_estimate

    merged_final = list(after.get("resolved_modules") or [])
    after["bom_estimate"] = build_salvage_bom_estimate(
        resolved_modules=merged_final,
        gap_analysis=after.get("gap_analysis"),
        budget=budget,
    )
    module_id_list = [str(r.get("module_id") or "") for r in merged_final if r.get("module_id")]
    after["firmware_scaffold"] = generate_firmware_from_salvage(
        build_id=str(after.get("recommended_build_id") or "salvage_build"),
        bringup_card=dict(after.get("bringup_card") or {}),
        module_ids=module_id_list,
        goal=goal,
    )
    revision = {
        "schema_version": SCHEMA_VERSION,
        "edits": list(edits),
        "parts_after": parts_copy,
        "package": after,
    }
    if before:
        revision["diff"] = diff_salvage_packages(before, after)
    return revision
