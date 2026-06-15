"""Salvage splice plan → BuildGraph translator (Python engine).

Recipes live in data/catalog_recipes.json (exported from plan-to-graph.ts).
Geometry/DRC/KiCad still run in Node until Phase 3.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple

from .inventory_topology import adapt_recipe_to_inventory
from .runtime import ROOT

DATA_FILE = Path(__file__).resolve().parent / "data" / "catalog_recipes.json"


@lru_cache(maxsize=1)
def load_catalog_data() -> Dict[str, Any]:
    if not DATA_FILE.is_file():
        raise FileNotFoundError(f"catalog recipes missing: {DATA_FILE} (run scripts/export_catalog_recipes.cjs)")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def supported_build_ids() -> List[str]:
    data = load_catalog_data()
    return list(data.get("supported_build_ids") or sorted((data.get("recipes") or {}).keys()))


def recipe_to_build_graph(recipe: Mapping[str, Any]) -> Dict[str, Any]:
    id_of: Dict[str, str] = {}
    nodes = []
    for i, m in enumerate(recipe.get("modules") or []):
        node_id = f"n{i + 1}"
        id_of[str(m.get("role"))] = node_id
        nodes.append({"id": node_id, "moduleId": m.get("moduleId")})

    wires = []
    for i, w in enumerate(recipe.get("wires") or []):
        from_role = w.get("from", {}).get("role")
        to_role = w.get("to", {}).get("role")
        from_id = id_of.get(str(from_role))
        to_id = id_of.get(str(to_role))
        if not from_id or not to_id:
            continue
        wires.append(
            {
                "id": f"w{i + 1}",
                "from": {"nodeId": from_id, "pinId": w.get("from", {}).get("pin")},
                "to": {"nodeId": to_id, "pinId": w.get("to", {}).get("pin")},
            }
        )
    return {"nodes": nodes, "wires": wires}


def splice_plan_to_build_graph(
    plan: Mapping[str, Any] | None,
) -> Tuple[Dict[str, Any], Optional[str], List[str], List[str]]:
    """Convert a salvage splice plan into a BuildGraph.

    Returns (graph, build_id, notes, warnings).
    """
    warnings: List[str] = []
    notes: List[str] = []
    data = load_catalog_data()
    recipes: Dict[str, Any] = data.get("recipes") or {}

    if not plan:
        warnings.append("Empty splice plan.")
        return {"nodes": [], "wires": []}, None, notes, warnings

    build_id = (
        (plan.get("target") or {}).get("recommended_build_id")
        or ((plan.get("build_candidates") or [{}])[0] or {}).get("id")
    )
    build_id = str(build_id).strip() if build_id else None

    if not build_id:
        warnings.append("Plan has no recommended_build_id (and no build_candidates).")
        return {"nodes": [], "wires": []}, None, notes, warnings

    custom_graph = plan.get("custom_graph") or {}
    if custom_graph.get("nodes"):
        notes.append("Using inventory-composed custom_graph from salvage bridge.")
        return dict(custom_graph), build_id, notes, warnings

    if plan.get("compose_from_inventory") and plan.get("resolved_modules"):
        from .auto_wire import compose_build_graph_from_module_ids

        ids = list(
            dict.fromkeys(
                str(r.get("module_id"))
                for r in plan.get("resolved_modules") or []
                if r.get("module_id")
            )
        )
        if len(ids) >= 2:
            composed = compose_build_graph_from_module_ids(ids)
            notes.append("Inventory-composed graph via Python auto-wire.")
            notes.extend(composed.get("notes") or [])
            warnings.extend(composed.get("warnings") or [])
            return (
                dict(composed.get("graph") or {"nodes": [], "wires": []}),
                build_id or composed.get("build_id"),
                notes,
                warnings,
            )

    overrides_preview = dict(plan.get("module_overrides") or {})
    recipe_key = build_id
    if build_id == "automatic_plant_watering":
        topo = str(plan.get("power_topology") or "")
        pwr = str(overrides_preview.get("pwr") or "")
        if topo == "usb_5v" or pwr == "usb-power-5v":
            recipe_key = "automatic_plant_watering_usb"
            notes.append("Power topology: USB 5V salvage path (no 12V barrel).")

    recipe = recipes.get(recipe_key)
    if not recipe:
        from .auto_wire import auto_wire_picked_modules, pick_modules_for_requirements

        caps = (data.get("build_catalog_capability_groups") or {}).get(build_id)
        if caps:
            picked = pick_modules_for_requirements(caps)
            if picked:
                auto = auto_wire_picked_modules(picked)
                notes.extend(auto.get("notes") or [])
                warnings.append(
                    f'No hand-curated recipe for "{build_id}" — auto-wired {len(picked)} module(s): '
                    f'{", ".join(str(m.get("id")) for m in picked)}.'
                )
                return recipe_to_build_graph(auto), build_id, notes, warnings
        warnings.append(f'No translator recipe and no capability fall-back for "{build_id}".')
        return {"nodes": [], "wires": []}, build_id, notes, warnings

    plan_with_overrides: Dict[str, Any] = {**dict(plan), "module_overrides": dict(overrides_preview)}
    for row in plan.get("resolved_modules") or []:
        role = row.get("role")
        module_id = row.get("module_id")
        if role and module_id and role not in plan_with_overrides["module_overrides"]:
            plan_with_overrides["module_overrides"][role] = module_id

    if plan_with_overrides.get("module_overrides"):
        notes.append(f"Module overrides applied: {json.dumps(plan_with_overrides['module_overrides'])}")

    adapted_recipe, topo_notes = adapt_recipe_to_inventory(dict(recipe), plan_with_overrides)
    notes.extend(topo_notes)
    orig_len = len(recipe.get("modules") or [])
    new_len = len(adapted_recipe.get("modules") or [])
    if new_len != orig_len:
        notes.append(f"Inventory topology: {new_len} modules (was {orig_len}).")

    id_of: Dict[str, str] = {}
    nodes = []
    for i, m in enumerate(adapted_recipe.get("modules") or []):
        node_id = f"n{i + 1}"
        id_of[str(m.get("role"))] = node_id
        nodes.append({"id": node_id, "moduleId": m.get("moduleId")})

    wires = []
    for i, w in enumerate(adapted_recipe.get("wires") or []):
        from_role = w.get("from", {}).get("role")
        to_role = w.get("to", {}).get("role")
        from_id = id_of.get(str(from_role))
        to_id = id_of.get(str(to_role))
        if not from_id or not to_id:
            warnings.append(f"Wire {i} drops unknown role: {from_role}/{to_role}.")
            continue
        wires.append(
            {
                "id": f"w{i + 1}",
                "from": {"nodeId": from_id, "pinId": w.get("from", {}).get("pin")},
                "to": {"nodeId": to_id, "pinId": w.get("to", {}).get("pin")},
            }
        )

    if adapted_recipe.get("notes"):
        notes.extend(adapted_recipe["notes"])

    reused = [b for b in (plan.get("reusable_blocks") or []) if b]
    if reused:
        names = [str(b.get("name") or b.get("id") or "") for b in reused[:8] if b.get("name") or b.get("id")]
        if names:
            notes.append(f"Harvest from inventory: {', '.join(names)}")

    return {"nodes": nodes, "wires": wires}, build_id, notes, warnings
