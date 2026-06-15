"""Programmatic agent SDK — compose, salvage, verify without HTTP.

Use from MCP servers, notebooks, or other agent runtimes. KiCad ERC/DRC is the
compile truth; cosmetic copper by default (no FreeRouting unless opted in).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .build_compiler import CATALOG_BUILD_IDS, compile_catalog_build, compile_from_netlist
from .canvas_compose import compile_canvas_build
from .design_quality import build_design_quality_gate
from .material_modes import material_mode_summary, resolve_material_mode
from .module_picker import pick_modules_for_goal
from .module_resolver import infer_power_topology, resolve_parts_to_modules
from .env_local import load_env_local
from .runtime import ROOT, runtime_status, scratch_path
from .salvage_bridge import build_intake_salvage_package
from .integrations.qwen_netlist_compose import compose_netlist_from_goal
from .salvage_bringup import run_salvage_bringup
from .scratch_pipeline import compile_scratch_build

SCHEMA_VERSION = "hardware_splicer.sdk.v1"


def apply_engine_defaults() -> None:
    """Safe defaults for agent-driven compiles (headless, no Java autoroute)."""
    load_env_local()
    os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    os.environ.setdefault("HARDWARE_SPLICER_JLC_ENRICH", "0")
    os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    scratch = scratch_path("tmp")
    os.environ.setdefault("TMPDIR", str(scratch))
    os.environ.setdefault("TEMP", str(scratch))
    os.environ.setdefault("TMP", str(scratch))


def apply_fab_profile(*, autoroute: bool = False, export_gerber: bool = True) -> Dict[str, str]:
    """Headless fab bundle: KiCad DRC + gerbers on preview copper (no FreeRouting by default)."""
    apply_engine_defaults()
    if autoroute:
        os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "1"
    if export_gerber:
        os.environ["HARDWARE_SPLICER_EXPORT_GERBER"] = "1"
    return {
        "HARDWARE_SPLICER_AUTOROUTE": os.environ.get("HARDWARE_SPLICER_AUTOROUTE", "0"),
        "HARDWARE_SPLICER_EXPORT_GERBER": os.environ.get("HARDWARE_SPLICER_EXPORT_GERBER", "0"),
        "TMPDIR": os.environ.get("TMPDIR", ""),
    }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


def _json(payload: Any) -> str:
    return dump_json(payload)


def _out_dir(name: str) -> Path:
    path = scratch_path("agent_sdk") / f"{name}-{uuid.uuid4().hex[:10]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def engine_doctor() -> Dict[str, Any]:
    """Runtime readiness: Python deps, app roots, KiCad/node paths."""
    apply_engine_defaults()
    status = dict(runtime_status())
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(status.get("ok")),
        "demo_ready": status.get("demo_ready"),
        "fab_export_ready": status.get("fab_export_ready"),
        "dependencies": status.get("dependencies"),
        "app_roots": status.get("app_roots"),
        "engine_defaults": {
            "autoroute": os.environ.get("HARDWARE_SPLICER_AUTOROUTE", "0"),
            "jlc_enrich": os.environ.get("HARDWARE_SPLICER_JLC_ENRICH", "0"),
            "drc_fix_loop": os.environ.get("HARDWARE_SPLICER_DRC_FIX_LOOP", "1"),
        },
        "capability_boundary": (
            "KiCad ERC/DRC is external truth. Default copper is cosmetic preview, not autorouted. "
            "Salvage and scratch share one engine; material_mode only changes the parts budget."
        ),
    }


def list_catalog_builds() -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "build_ids": list(CATALOG_BUILD_IDS),
        "count": len(CATALOG_BUILD_IDS),
    }


def resolve_inventory_parts(parts: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Map junk-drawer / inventory part rows to module-library IDs."""
    apply_engine_defaults()
    resolved = resolve_parts_to_modules(list(parts))
    topology = infer_power_topology(list(parts), resolved)
    return {
        "schema_version": SCHEMA_VERSION,
        "power_topology": topology,
        "resolved_modules": resolved,
        "module_ids": [str(r.get("module_id")) for r in resolved if r.get("module_id")],
    }


def suggest_modules(goal: str) -> Dict[str, Any]:
    """NL goal → starter module set (open catalog picker)."""
    pick = pick_modules_for_goal(goal)
    return {
        "schema_version": SCHEMA_VERSION,
        "goal": goal,
        "module_ids": list(pick.module_ids),
        "hints": list(pick.hints or []),
        "material_mode_hint": "scratch",
    }


def plan_salvage(
    *,
    goal: str,
    parts: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    project_name: str | None = None,
) -> Dict[str, Any]:
    """Plan salvage splice without running KiCad compile (~fast)."""
    apply_engine_defaults()
    package = build_intake_salvage_package(
        goal=goal,
        parts=list(parts),
        constraints=dict(constraints or {}),
        project_name=project_name,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "recommended_build_id": package.get("recommended_build_id"),
        "graph_mode": package.get("graph_mode"),
        "power_topology": package.get("power_topology"),
        "strategy_mode": package.get("strategy_mode"),
        "resolved_modules": package.get("resolved_modules"),
        "compose_module_ids": package.get("compose_module_ids"),
        "module_overrides": package.get("module_overrides"),
        "verdict": package.get("verdict"),
    }


def compose_arbitrary(
    goal: str,
    *,
    constraints: Mapping[str, Any] | None = None,
    out_dir: str | Path | None = None,
    fab_profile: bool = False,
    export_gerber: bool | None = None,
    allow_qwen: bool = True,
) -> Dict[str, Any]:
    """NL → netlist IR (Qwen text when keyed) → KiCad compile. Arbitrary vs module-only."""
    if fab_profile:
        apply_fab_profile(export_gerber=export_gerber if export_gerber is not None else True)
    else:
        apply_engine_defaults()
    planned = compose_netlist_from_goal(goal, constraints=constraints, allow_qwen=allow_qwen)
    if not planned.get("netlist"):
        return {"schema_version": SCHEMA_VERSION, **planned}
    do_gerber = export_gerber if export_gerber is not None else (
        os.environ.get("HARDWARE_SPLICER_EXPORT_GERBER", "0") == "1"
    )
    target = Path(out_dir) if out_dir else _out_dir("arbitrary")
    result = compile_from_netlist(planned["netlist"], target, export_gerber=do_gerber)
    if not result.ok and planned.get("compose_mode") == "qwen_netlist" and allow_qwen:
        planned = compose_netlist_from_goal(goal, constraints=constraints, allow_qwen=False)
        if planned.get("netlist"):
            result = compile_from_netlist(planned["netlist"], target, export_gerber=do_gerber)
    gate = build_design_quality_gate(result.design_quality)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(result.ok and gate.get("build_ready")),
        "mode": "arbitrary",
        "compose_mode": planned.get("compose_mode"),
        "qwen_usage": planned.get("usage"),
        "erc": planned.get("erc"),
        "out_dir": str(target),
        **result.to_dict(),
        "design_quality_gate": gate,
        "fab_recommendation": (result.design_quality or {}).get("fab_recommendation"),
        "fabrication_ready": (result.design_quality or {}).get("fabrication_ready"),
    }


def compose_design(
    *,
    phrase: str | None = None,
    module_ids: Sequence[str] | None = None,
    resolved_modules: Sequence[Mapping[str, Any]] | None = None,
    canvas_nodes: Sequence[Mapping[str, Any]] | None = None,
    canvas_wires: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
    material_mode: str | None = None,
    salvage_mode: bool = False,
    out_dir: str | Path | None = None,
    export_gerber: bool = False,
    fab_profile: bool = False,
    arbitrary: bool = False,
) -> Dict[str, Any]:
    """Compose NL phrase, module list, or canvas graph → KiCad artifacts."""
    if arbitrary and phrase:
        return compose_arbitrary(
            phrase,
            constraints=constraints,
            out_dir=out_dir,
            fab_profile=fab_profile,
            export_gerber=export_gerber,
        )
    if fab_profile:
        apply_fab_profile(export_gerber=export_gerber)
    else:
        apply_engine_defaults()
    constraints_map = dict(constraints or {})
    mode = material_mode or resolve_material_mode(constraints=constraints_map, salvage_mode=salvage_mode)
    target = Path(out_dir) if out_dir else _out_dir("compose")
    target.mkdir(parents=True, exist_ok=True)

    if canvas_nodes:
        result = compile_canvas_build(
            out_dir=str(target),
            nodes=list(canvas_nodes),
            wires=list(canvas_wires or []),
            constraints=constraints_map,
            salvage_mode=salvage_mode,
            material_mode=mode,  # type: ignore[arg-type]
            export_gerber=export_gerber,
        )
        quality = (result.compile_result.design_quality if result.compile_result else {}) or {}
        gate = build_design_quality_gate(quality)
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": bool(result.ok and gate.get("build_ready")),
            "mode": "canvas",
            "out_dir": str(target),
            **result.to_dict(),
            "design_quality_gate": gate,
            **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
        }

    if not phrase and not module_ids:
        raise ValueError("phrase, module_ids, or canvas_nodes is required")

    scratch = compile_scratch_build(
        out_dir=str(target),
        goal=phrase,
        module_ids=list(module_ids) if module_ids else None,
        resolved_modules=resolved_modules,
        export_gerber=export_gerber,
        constraints=constraints_map,
        salvage_mode=salvage_mode,
    )
    compile_result = scratch.compile_result
    quality = (compile_result.design_quality if compile_result else {}) or {}
    gate = build_design_quality_gate(quality)
    build_dir = target / "build_compilation"
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(scratch.ok and gate.get("build_ready")),
        "mode": "scratch",
        "out_dir": str(target),
        "build_id": scratch.build_id,
        "module_ids": scratch.module_ids,
        "attempts": scratch.attempts,
        "design_quality": quality,
        "design_quality_gate": gate,
        "artifacts": {
            "build_graph": str(build_dir / "build_graph.json") if (build_dir / "build_graph.json").is_file() else None,
            "circuit_netlist": str(build_dir / "circuit_netlist.json")
            if (build_dir / "circuit_netlist.json").is_file()
            else None,
            "kicad_pcb": str(compile_result.kicad_pcb_file) if compile_result else None,
            "bom": str(build_dir / "BOM.json") if (build_dir / "BOM.json").is_file() else None,
            "firmware": str(build_dir / "firmware") if (build_dir / "firmware").is_dir() else None,
            "design_quality": str(build_dir / "DESIGN_QUALITY.json")
            if (build_dir / "DESIGN_QUALITY.json").is_file()
            else None,
        },
        **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
        "error": scratch.error,
    }


def salvage_bringup(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path | None = None,
    export_gerber: bool = False,
) -> Dict[str, Any]:
    """Full salvage path: intake → splice → KiCad compile → evidence report."""
    apply_engine_defaults()
    target = Path(out_dir) if out_dir else _out_dir("salvage")
    return run_salvage_bringup(dict(intake), out_dir=target, export_gerber=export_gerber)


def verify_engine(
    *,
    build_ids: Sequence[str] | None = None,
    max_warnings: int = 500,
    out_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Run catalog KiCad DRC bar (slow — ~20s for full set)."""
    apply_engine_defaults()
    ids = list(build_ids or CATALOG_BUILD_IDS)
    root = Path(out_dir) if out_dir else _out_dir("verify")
    rows: List[Dict[str, Any]] = []
    for build_id in ids:
        out = root / build_id
        t0 = time.time()
        result = compile_catalog_build(build_id, str(out), export_gerber=False)
        q = result.design_quality or {}
        warn = int(q.get("kicad_drc_warnings") or 0)
        rows.append(
            {
                "build_id": build_id,
                "ok": bool(result.ok),
                "kicad_drc_errors": int(q.get("kicad_drc_errors") or 0),
                "kicad_drc_warnings": warn,
                "copper_tier": q.get("copper_tier"),
                "fab_recommendation": q.get("fab_recommendation"),
                "warnings_over_budget": warn > max_warnings,
                "seconds": round(time.time() - t0, 2),
                "error": result.error,
            }
        )
    clean = [r for r in rows if r.get("ok") and r.get("kicad_drc_errors", 1) == 0]
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": len(clean) == len(rows),
        "autoroute": False,
        "verified": len(clean),
        "total": len(rows),
        "out_dir": str(root),
        "rows": rows,
    }


def compile_netlist(
    netlist: Mapping[str, Any],
    *,
    out_dir: str | Path | None = None,
    export_gerber: bool = False,
) -> Dict[str, Any]:
    """Compile from circuit_netlist IR dict."""
    apply_engine_defaults()
    target = Path(out_dir) if out_dir else _out_dir("netlist")
    result = compile_from_netlist(dict(netlist), target, export_gerber=export_gerber)
    gate = build_design_quality_gate(result.design_quality)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(result.ok and gate.get("build_ready")),
        "out_dir": str(target),
        **result.to_dict(),
        "design_quality_gate": gate,
    }


def sdk_info() -> Dict[str, Any]:
    """Capability card for agents choosing tools."""
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "Hardware-Splicer Engine",
        "repo_root": str(ROOT),
        "strengths": [
            "Inventory-constrained salvage bring-up from junk-drawer parts",
            "NL phrase / module list / canvas graph → wired schematic + placed PCB",
            "KiCad ERC/DRC as external compile truth (not LLM self-grade)",
            "Honest quality flags: copper_tier, fab_recommendation, build_ready",
            "Scratch and salvage share one engine (material_mode = parts budget only)",
        ],
        "not_yet": [
            "Flux-class interactive editor and parts marketplace UX",
            "Guaranteed autoroute success on every topology (FreeRouting is opt-in/heavy)",
        ],
        "fab_review_path": (
            "fab_profile=True exports gerbers headlessly (kicad-cli) on preview copper — "
            "fab_recommendation review_required_preview_copper. "
            "Real autoroute is opt-in only: apply_fab_profile(autoroute=True) or HARDWARE_SPLICER_AUTOROUTE=1."
        ),
        "arbitrary_path": (
            "compose_arbitrary() uses Qwen text (qwen-plus) → netlist IR when API key set; "
            "falls back to module picker. Vision Qwen is separate (bench photos only)."
        ),
        "default_env": {
            "HARDWARE_SPLICER_AUTOROUTE": "0",
            "HARDWARE_SPLICER_JLC_ENRICH": "0",
            "HARDWARE_SPLICER_DRC_FIX_LOOP": "1",
        },
        "http_api": "uvicorn hardware_splicer.api:app (see scripts/hardware_splicer.py serve)",
        "mcp": "python -m hardware_splicer.mcp_server",
    }
