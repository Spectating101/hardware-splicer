"""Scratch compose pipeline: NL/parts → module merge → auto-wire → prove (+ retries)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .auto_wire import compose_build_graph_from_module_ids
from .material_modes import (
    MaterialMode,
    expand_module_ids_for_safety,
    material_mode_summary,
    resolve_material_mode,
)
from .build_compiler import BuildCompileResult, compile_catalog_build
from .module_picker import pick_modules_for_goal, wants_module_composition
from .pcb.safety_rules import analyze_build
from .pcb.build_to_geometry import build_graph_to_geometry
from .pcb.drc import run_drc


NAMED_CATALOG_BUILD_IDS = {
    "automatic_plant_watering",
    "robot_drive_base",
    "usb_fume_extractor",
    "room_display_station",
    "smart_relay_box",
    "sensor_logger",
    "inspection_motion_fixture",
    "low_voltage_motor_test_jig",
}


@dataclass
class ScratchCompileResult:
    ok: bool
    build_id: str
    module_ids: List[str]
    compile_result: Optional[BuildCompileResult] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    graph_mode: str = "scratch"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "build_id": self.build_id,
            "module_ids": self.module_ids,
            "graph_mode": self.graph_mode,
            "attempts": self.attempts,
            "error": self.error,
            "compile_result": self.compile_result.to_dict() if self.compile_result else None,
        }


def merge_goal_modules_with_inventory(
    goal: str,
    resolved_modules: Sequence[Mapping[str, Any]] | None,
    *,
    constrained: bool = False,
) -> List[Dict[str, Any]]:
    """Merge NL module picker output with inventory-resolved rows (inventory wins on id clash)."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in resolved_modules or []:
        module_id = str(row.get("module_id") or "").strip()
        if module_id:
            by_id[module_id] = dict(row)
    if constrained and by_id:
        return list(by_id.values())
    pick = pick_modules_for_goal(goal)
    for index, module_id in enumerate(pick.module_ids):
        if module_id not in by_id:
            by_id[module_id] = {
                "module_id": module_id,
                "role": f"g{index + 1}",
                "source": "goal_picker",
            }
    return list(by_id.values())


def module_ids_from_resolved(resolved_modules: Sequence[Mapping[str, Any]] | None) -> List[str]:
    return list(
        dict.fromkeys(
            str(row.get("module_id")).strip()
            for row in (resolved_modules or [])
            if isinstance(row, Mapping) and str(row.get("module_id") or "").strip()
        )
    )


def resolved_rows_for_module_ids(
    module_ids: Sequence[str],
    resolved_modules: Sequence[Mapping[str, Any]] | None,
) -> List[Dict[str, Any]]:
    """Preserve inventory metadata (part_name, source) when compiling a module-id list."""
    by_id = {
        str(row.get("module_id") or "").strip(): dict(row)
        for row in (resolved_modules or [])
        if isinstance(row, Mapping) and str(row.get("module_id") or "").strip()
    }
    rows: List[Dict[str, Any]] = []
    for module_id in module_ids:
        mid = str(module_id).strip()
        if not mid:
            continue
        rows.append(by_id.get(mid) or {"module_id": mid})
    return rows


def should_use_scratch_compose(
    *,
    goal: str,
    build_id: str | None,
    resolved_modules: Sequence[Mapping[str, Any]] | None,
    constraints: Mapping[str, Any] | None = None,
    strategy_mode: str | None = None,
) -> bool:
    constraints_map = dict(constraints or {})
    graph_mode = str(constraints_map.get("graph_mode") or "").strip().lower()
    if graph_mode in {"compose", "scratch"}:
        return True
    if constraints_map.get("compose_from_inventory") is True:
        return True

    catalog_id = str(build_id or "").strip()
    if catalog_id and catalog_id in NAMED_CATALOG_BUILD_IDS:
        return False

    merged_ids = module_ids_from_resolved(merge_goal_modules_with_inventory(goal, resolved_modules))
    if len(merged_ids) < 2:
        return False

    if wants_module_composition(goal):
        return True
    if strategy_mode == "constrained" and catalog_id in {"", "generic_low_voltage_build"}:
        return True
    if not catalog_id or catalog_id == "generic_low_voltage_build":
        return wants_module_composition(goal) or len(module_ids_from_resolved(resolved_modules)) >= 2
    return False


def build_scratch_splice_plan(
    *,
    goal: str,
    resolved_modules: Sequence[Mapping[str, Any]] | None,
    build_id: str | None = None,
    constraints: Mapping[str, Any] | None = None,
    salvage_mode: bool = False,
) -> Dict[str, Any]:
    constraints_map = dict(constraints or {})
    constrained = (
        str(constraints_map.get("strategy_mode") or "") == "constrained"
        or constraints_map.get("compose_from_inventory") is True
    )
    merged = merge_goal_modules_with_inventory(goal, resolved_modules, constrained=constrained)
    ids = module_ids_from_resolved(merged)
    mode = resolve_material_mode(constraints=constraints, salvage_mode=salvage_mode)
    return {
        "target": {"recommended_build_id": build_id or "generic_low_voltage_build"},
        "resolved_modules": merged,
        "compose_from_inventory": True,
        "compose_module_ids": ids,
        "graph_mode": "scratch",
        **material_mode_summary(material_mode=mode, constraints=constraints),
    }


def _graph_quality(graph: Mapping[str, Any]) -> Dict[str, Any]:
    safety = analyze_build(dict(graph))
    safety_errors = [w for w in safety if w.get("level") == "error"]
    drc = run_drc(build_graph_to_geometry(dict(graph)))
    return {
        "safety_errors": len(safety_errors),
        "safety_error_messages": [w.get("message") for w in safety_errors],
        "drc_pass": bool(drc.get("pass")),
        "drc_errors": sum(1 for v in drc.get("violations") or [] if v.get("severity") == "error"),
    }


def _deterministic_fixup(
    module_ids: List[str],
    quality: Mapping[str, Any],
    attempt: int,
    *,
    material_mode: MaterialMode = "scratch",
) -> List[str]:
    ids = list(dict.fromkeys(module_ids))
    messages = " ".join(str(m) for m in quality.get("safety_error_messages") or []).lower()

    if attempt == 0:
        if "hc-sr04" in ids and "level-shifter-4ch" not in ids and material_mode == "scratch":
            ids.append("level-shifter-4ch")
    if attempt == 1:
        if any(mid in ids for mid in ("water_pump_5v", "cooling_fan_5v", "mini-pump-5v")) and "mosfet-irlz44n" not in ids:
            ids.append("mosfet-irlz44n")
    if attempt == 2:
        if "dht22" in ids and "bme280" in ids:
            ids = [mid for mid in ids if mid != "dht22"]
    if attempt == 3 and ("5v" in messages or "level" in messages):
        if "esp32-devkit" in ids and "usb-power-5v" not in ids:
            ids.insert(0, "usb-power-5v")
    return list(dict.fromkeys(ids))


def _llm_enabled() -> bool:
    return os.environ.get("HARDWARE_SPLICER_LLM_COMPOSE", "").strip().lower() in {"1", "true", "yes"}


def _llm_adjust_modules(goal: str, module_ids: List[str], quality: Mapping[str, Any]) -> Optional[List[str]]:
    from .integrations.llm_policy import qwen_llm_first
    from .integrations.qwen_module_pick import call_qwen_module_pick

    if not qwen_llm_first():
        return None

    messages = "; ".join(str(m) for m in quality.get("safety_error_messages") or [])
    picked = call_qwen_module_pick(
        f"{goal} — fix electrical issues: {messages}",
        constraints={"prior_module_ids": module_ids, "design_quality": dict(quality)},
    )
    if picked.get("ok") and len(picked.get("module_ids") or []) >= 2:
        return [str(mid) for mid in picked["module_ids"]]
    return None


def compile_scratch_build(
    *,
    out_dir: str,
    goal: str | None = None,
    module_ids: Sequence[str] | None = None,
    resolved_modules: Sequence[Mapping[str, Any]] | None = None,
    export_gerber: bool = True,
    max_retries: int = 4,
    constraints: Mapping[str, Any] | None = None,
    salvage_mode: bool = False,
) -> ScratchCompileResult:
    """Compose + compile with deterministic (and optional LLM) retries on prove failures."""
    constraints_map = dict(constraints or {})
    material_mode: MaterialMode = resolve_material_mode(constraints=constraints_map, salvage_mode=salvage_mode)
    if module_ids:
        ids = list(dict.fromkeys(str(mid) for mid in module_ids if str(mid).strip()))
    elif goal:
        constrained = (
            str(constraints_map.get("strategy_mode") or "") == "constrained"
            or constraints_map.get("compose_from_inventory") is True
        )
        merged = merge_goal_modules_with_inventory(goal, resolved_modules, constrained=constrained)
        ids = module_ids_from_resolved(merged)
        resolved_modules = merged
    else:
        return ScratchCompileResult(ok=False, build_id="generic_low_voltage_build", module_ids=[], error="goal or module_ids required")

    if len(ids) < 2:
        return ScratchCompileResult(
            ok=False,
            build_id="generic_low_voltage_build",
            module_ids=ids,
            error=f"need >=2 modules, got {ids}",
        )

    build_id = "generic_low_voltage_build"
    attempts: List[Dict[str, Any]] = []
    last_result: Optional[BuildCompileResult] = None
    last_quality: Dict[str, Any] = {}

    for attempt in range(max_retries + 1):
        inventory_rows = resolved_rows_for_module_ids(ids, resolved_modules)
        splice_plan = build_scratch_splice_plan(
            goal=goal or "",
            resolved_modules=inventory_rows,
            constraints=constraints_map,
            salvage_mode=salvage_mode,
        )
        last_result = compile_catalog_build(
            build_id,
            out_dir,
            export_gerber=export_gerber,
            splice_plan=splice_plan,
            resolved_modules=inventory_rows,
        )
        quality = dict(last_result.design_quality or {})
        last_quality = quality
        attempts.append(
            {
                "attempt": attempt,
                "module_ids": list(ids),
                "ok": last_result.ok,
                "drc_pass": quality.get("drc_pass"),
                "electrical_errors": quality.get("electrical_errors"),
            }
        )
        if last_result.ok and quality.get("drc_pass") and quality.get("build_ready"):
            return ScratchCompileResult(
                ok=True,
                build_id=build_id,
                module_ids=ids,
                compile_result=last_result,
                attempts=attempts,
            )

        preview = compose_build_graph_from_module_ids(ids).get("graph") or {}
        graph_q = _graph_quality(preview)
        if graph_q.get("drc_pass") and not graph_q.get("safety_errors") and not last_result.ok:
            # Graph is fine but artifact stage failed — stop retrying modules.
            break

        if goal:
            alt = _llm_adjust_modules(goal, ids, {**quality, **graph_q})
            if alt and alt != ids:
                ids = alt
                continue

        next_ids = _deterministic_fixup(ids, {**quality, **graph_q}, attempt, material_mode=material_mode)
        if next_ids != ids:
            ids = next_ids
            continue
        next_ids = expand_module_ids_for_safety(
            ids,
            safety_messages=quality.get("safety_error_messages") or graph_q.get("safety_error_messages") or [],
            material_mode=material_mode,
            inventory_ids=module_ids_from_resolved(resolved_modules) if resolved_modules else ids,
            constraints=constraints_map,
        )
        if next_ids != ids:
            ids = next_ids
            continue
        break

    if goal:
        alt = _llm_adjust_modules(goal, ids, last_quality)
        if alt and alt != ids:
            ids = alt
            inventory_rows = resolved_rows_for_module_ids(ids, resolved_modules)
            splice_plan = build_scratch_splice_plan(
                goal=goal,
                resolved_modules=inventory_rows,
                constraints=constraints_map,
                salvage_mode=salvage_mode,
            )
            last_result = compile_catalog_build(
                build_id,
                out_dir,
                export_gerber=export_gerber,
                splice_plan=splice_plan,
                resolved_modules=inventory_rows,
            )
            quality = dict(last_result.design_quality or {})
            attempts.append(
                {
                    "attempt": "llm",
                    "module_ids": list(ids),
                    "ok": last_result.ok,
                    "drc_pass": quality.get("drc_pass"),
                }
            )
            if last_result.ok and quality.get("drc_pass"):
                return ScratchCompileResult(
                    ok=True,
                    build_id=build_id,
                    module_ids=ids,
                    compile_result=last_result,
                    attempts=attempts,
                )

    return ScratchCompileResult(
        ok=bool(last_result and last_result.ok),
        build_id=build_id,
        module_ids=ids,
        compile_result=last_result,
        attempts=attempts,
        error=None if last_result and last_result.ok else (last_result.error if last_result else "compile failed"),
    )


def prove_module_ids(module_ids: Sequence[str]) -> Dict[str, Any]:
    """Quick prove-only check without full artifact stage."""
    composed = compose_build_graph_from_module_ids(list(module_ids))
    graph = composed.get("graph") or {}
    quality = _graph_quality(graph)
    return {
        "module_ids": list(module_ids),
        "nodes": len(graph.get("nodes") or []),
        "wires": len(graph.get("wires") or []),
        "graph_quality": quality,
        "ok": bool(
            graph.get("nodes")
            and not quality.get("safety_errors")
            and quality.get("drc_pass")
        ),
    }
