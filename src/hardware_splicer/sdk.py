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
from .module_resolver import infer_power_topology, resolve_parts_to_modules_with_llm
from .env_local import load_env_local
from .runtime import ROOT, runtime_status, scratch_path
from .integrations.llm_policy import llm_policy_summary
from .testing_mode import testing_mode_enabled
from .salvage_bridge import build_intake_salvage_package
from .integrations.qwen_netlist_compose import compose_netlist_from_goal
from .salvage_bringup import run_salvage_bringup
from .compose_dispatch import compose_dispatch
from .scratch_pipeline import compile_scratch_build

SCHEMA_VERSION = "hardware_splicer.sdk.v1"


def apply_engine_defaults() -> None:
    """Safe defaults for agent-driven compiles (headless, no Java autoroute)."""
    load_env_local()
    os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    os.environ.setdefault("HARDWARE_SPLICER_JLC_ENRICH", "0")
    os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    os.environ.setdefault("HARDWARE_SPLICER_SIMULATE", "1")
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
    testing_mode = testing_mode_enabled()
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(status.get("ok")),
        "demo_ready": status.get("demo_ready"),
        "fab_export_ready": status.get("fab_export_ready"),
        "testing_mode": testing_mode,
        "testing_mode_blocker": status.get("testing_mode_blocker"),
        "dependencies": status.get("dependencies"),
        "app_roots": status.get("app_roots"),
        "engine_defaults": {
            "autoroute": os.environ.get("HARDWARE_SPLICER_AUTOROUTE", "0"),
            "jlc_enrich": os.environ.get("HARDWARE_SPLICER_JLC_ENRICH", "0"),
            "drc_fix_loop": os.environ.get("HARDWARE_SPLICER_DRC_FIX_LOOP", "1"),
        },
        "llm_policy": llm_policy_summary(),
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


def resolve_inventory_parts(parts: Sequence[Mapping[str, Any]], *, goal: str = "") -> Dict[str, Any]:
    """Map junk-drawer / inventory part rows to module-library IDs."""
    apply_engine_defaults()
    resolved, meta = resolve_parts_to_modules_with_llm(list(parts), goal=goal)
    topology = infer_power_topology(list(parts), resolved)
    return {
        "schema_version": SCHEMA_VERSION,
        "power_topology": topology,
        "resolved_modules": resolved,
        "module_ids": [str(r.get("module_id")) for r in resolved if r.get("module_id")],
        "salvage_resolution": meta,
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
    return compose_dispatch(
        out_dir=target,
        phrase=phrase,
        module_ids=list(module_ids) if module_ids else None,
        resolved_modules=resolved_modules,
        canvas_nodes=list(canvas_nodes) if canvas_nodes else None,
        canvas_wires=list(canvas_wires or []),
        constraints=constraints_map,
        material_mode=mode,
        salvage_mode=salvage_mode,
        export_gerber=export_gerber,
        allow_llm_first=True,
    )


def jarvis_build(
    goal: str,
    *,
    parts: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
    project_name: str | None = None,
    out_dir: str | Path | None = None,
    export_gerber: bool = False,
    allow_qwen: bool = True,
) -> Dict[str, Any]:
    """LLM-aware electrical build: goal (+ optional parts) → compile → trust → JARVIS narrative."""
    from .jarvis_build import jarvis_build as _jarvis_build

    return _jarvis_build(
        goal,
        parts=parts,
        constraints=constraints,
        project_name=project_name,
        out_dir=out_dir,
        export_gerber=export_gerber,
        allow_qwen=allow_qwen,
    )


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


def splice_build(
    intake: Mapping[str, Any] | str | Path,
    *,
    out_dir: str | Path | None = None,
    export_gerber: bool = False,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Primary splice path: donor intake → splice plan → carrier KiCad compile → bench session."""
    from .project_intake import load_project_intake, splice_and_build_from_intake

    apply_engine_defaults()
    body = load_project_intake(intake) if not isinstance(intake, Mapping) else dict(intake)
    target = Path(out_dir) if out_dir else _out_dir("splice")
    result = splice_and_build_from_intake(
        body,
        out_dir=target,
        export_gerber=export_gerber,
        request_id=request_id,
    )
    return {"schema_version": SCHEMA_VERSION, **result}


def splice_bench_open(build_dir: str | Path, *, force: bool = False) -> Dict[str, Any]:
    """Open or reload SPLICE_BENCH_SESSION.json for a splice build directory."""
    from .splice_bench import open_bench_session

    apply_engine_defaults()
    session = open_bench_session(build_dir, force=force)
    return {"schema_version": SCHEMA_VERSION, **session}


def splice_bench_status(build_dir: str | Path) -> Dict[str, Any]:
    """Return bench gate status; opens a session if missing."""
    from .splice_bench import bench_status

    apply_engine_defaults()
    session = bench_status(build_dir)
    return {"schema_version": SCHEMA_VERSION, **session}


def splice_bench_submit(
    build_dir: str | Path,
    measurements: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Record bench measurements and close matching evidence gates."""
    from .splice_bench import submit_bench_measurements

    apply_engine_defaults()
    session = submit_bench_measurements(build_dir, measurements)
    return {"schema_version": SCHEMA_VERSION, **session}


def splice_bench_submit_capture(
    build_dir: str | Path,
    capture_packet: Mapping[str, Any],
) -> Dict[str, Any]:
    """Submit bench_topology_capture.v1 observations to close splice bench gates."""
    from .bench_capture_bridge import submit_bench_capture

    apply_engine_defaults()
    result = submit_bench_capture(str(build_dir), capture_packet)
    return result


def splice_bench_capture_template(build_dir: str | Path) -> Dict[str, Any]:
    """Return (and refresh) BENCH_CAPTURE_TEMPLATE.json for open splice gates."""
    from .bench_capture_bridge import sync_bench_session_template

    apply_engine_defaults()
    payload = sync_bench_session_template(build_dir)
    return {"schema_version": SCHEMA_VERSION, **payload}


def splice_golden_loop(
    intake: Mapping[str, Any] | str | Path,
    *,
    out_dir: str | Path | None = None,
    export_gerber: bool = False,
    simulate_bench: bool = True,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """End-to-end splice loop: build → bench template → capture submit → gate closure."""
    from .golden_loop import run_splice_golden_loop
    from .project_intake import load_project_intake

    apply_engine_defaults()
    body = load_project_intake(intake) if not isinstance(intake, Mapping) else dict(intake)
    target = Path(out_dir) if out_dir else _out_dir("splice_golden")
    report = run_splice_golden_loop(
        body,
        out_dir=target,
        export_gerber=export_gerber,
        simulate_bench=simulate_bench,
        request_id=request_id,
    )
    return {"schema_version": SCHEMA_VERSION, **report}


def splice_golden_real(
    intake: Mapping[str, Any] | str | Path,
    *,
    out_dir: str | Path | None = None,
    capture_path: str | Path | None = None,
    export_gerber: bool = False,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Golden real S3: build then submit committed manual bench capture (not simulator)."""
    from .golden_real_bench import run_splice_golden_real
    from .project_intake import load_project_intake

    apply_engine_defaults()
    body = load_project_intake(intake) if not isinstance(intake, Mapping) else dict(intake)
    target = Path(out_dir) if out_dir else _out_dir("splice_golden_real")
    report = run_splice_golden_real(
        body,
        out_dir=target,
        capture_path=capture_path,
        export_gerber=export_gerber,
        request_id=request_id,
    )
    return {"schema_version": SCHEMA_VERSION, **report}


def donor_board_vision_enrich(intake: Mapping[str, Any]) -> Dict[str, Any]:
    """Run donor board photo / board_evidence → functional_salvage on intake."""
    from .board_vision_salvage import enrich_intake_with_donor_board_vision

    apply_engine_defaults()
    body, report = enrich_intake_with_donor_board_vision(dict(intake))
    return {"schema_version": SCHEMA_VERSION, "intake": body, "donor_board_vision_report": report}


def vision_enrich_intake(
    intake: Mapping[str, Any],
    *,
    apply: bool | None = None,
    live: bool | None = None,
) -> Dict[str, Any]:
    """Run vision + evidence extraction on intake attachments (Qwen/Gemini when configured)."""
    from .evidence_extractor import enrich_intake_with_extracted_evidence
    from .vision_evidence_assistant import build_vision_evidence_report, enrich_intake_with_vision_assistance

    apply_engine_defaults()
    body = dict(intake)
    if apply is not None or live is not None:
        cfg = dict(body.get("vision_assistance") or {})
        if apply is not None:
            cfg["apply"] = bool(apply)
            cfg["enabled"] = True
        if live is not None:
            cfg["live"] = bool(live)
            cfg["enabled"] = True
        body["vision_assistance"] = cfg
    body, extraction_report = enrich_intake_with_extracted_evidence(body)
    body, vision_report = enrich_intake_with_vision_assistance(body)
    return {
        "schema_version": SCHEMA_VERSION,
        "intake": body,
        "vision_evidence_report": vision_report,
        "evidence_extraction_report": extraction_report,
    }


def vision_capabilities() -> Dict[str, Any]:
    """Inventory of camera/vision/bench capture already in this repo."""
    root = ROOT
    return {
        "schema_version": SCHEMA_VERSION,
        "hardware_splicer": {
            "intake_vision": "vision_evidence_assistant.enrich_intake_with_vision_assistance",
            "offline_attachment_inventory": "vision_inventory.merge_attachment_inventory_into_intake",
            "evidence_notes_extractor": "evidence_extractor.enrich_intake_with_extracted_evidence",
            "splice_bench_gates": "splice_bench.submit_bench_measurements",
            "bench_capture_bridge": "bench_capture_bridge.submit_bench_capture",
            "sdk_entrypoints": [
                "donor_board_vision_enrich",
                "vision_enrich_intake",
                "splice_bench_submit_capture",
                "splice_golden_loop",
                "splice_build (donor board_evidence / photos → functional_salvage automatically)",
            ],
            "example_vision_splice_intake": "examples/intakes/splice_robot_drive_vision_brief.json",
            "cli": "scripts/hardware_splicer.py intake --vision-live --vision-apply",
        },
        "circuit_ai": {
            "qwen_board_vision": "apps/circuit-ai/src/vision/qwen_board_vision.py",
            "bench_topology_capture": "apps/circuit-ai/src/intelligence/bench_topology_capture.py",
            "measurement_session_progress": "apps/circuit-ai/src/intelligence/measurement_session_progress.py",
            "api_endpoints": [
                "POST /vision/qwen/board-evidence",
                "POST /hardware/topology-capture/template",
                "POST /hardware/topology-capture/convert",
            ],
            "dum_e_archive": "apps/circuit-ai/docs/archive/2026-01-27_root_docs/DUM_E_STATUS.md",
            "multi_view_capture": "apps/circuit-ai/scripts/multi_view_capture.py",
        },
        "policy": (
            "Vision and photos produce candidates and measurement queues — they do not close "
            "splice power-on gates without bench_topology_capture or splice_bench_submit rows."
        ),
    }


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


def inspect_fab_build_dir(build_dir: str | Path) -> Dict[str, Any]:
    """Inspect fabrication package on disk without recompiling."""
    from .fabrication_inspection import inspect_fabrication_package

    root = Path(build_dir)
    compilation_dir = root / "build_compilation" if (root / "build_compilation").is_dir() else root
    compilation_path = compilation_dir / "BUILD_COMPILATION.json"
    if not compilation_path.is_file():
        compilation_path = root / "BUILD_COMPILATION.json"
    build_compilation: Dict[str, Any] = {}
    if compilation_path.is_file():
        build_compilation = json.loads(compilation_path.read_text(encoding="utf-8"))
    if not build_compilation and (compilation_dir / "DESIGN_QUALITY.json").is_file():
        quality = json.loads((compilation_dir / "DESIGN_QUALITY.json").read_text(encoding="utf-8"))
        build_compilation = {
            "design_quality": quality,
            "build_graph_file": str(compilation_dir / "build_graph.json"),
            "kicad_pcb_file": str(compilation_dir / "main_ctrl_build.kicad_pcb"),
            "out_dir": str(root),
        }
    pcb_candidates = sorted(compilation_dir.glob("*.kicad_pcb"))
    artifacts = {
        "build_kicad_pcb": str(pcb_candidates[0]) if pcb_candidates else str(compilation_dir / "main_ctrl_build.kicad_pcb"),
        "fab_package_zip": str(compilation_dir / "fab_package.zip")
        if (compilation_dir / "fab_package.zip").is_file()
        else str(root / "fab_package.zip"),
        "bom": str(compilation_dir / "BOM.json"),
        "out_dir": str(root),
    }
    inspection = inspect_fabrication_package(build_compilation=build_compilation, artifacts=artifacts)
    return {
        "schema_version": SCHEMA_VERSION,
        "build_dir": str(root),
        **inspection,
    }


def sdk_info() -> Dict[str, Any]:
    """Capability card for agents choosing tools."""
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "Hardware-Splicer Engine",
        "repo_root": str(ROOT),
        "strengths": [
            "Donor splice: dissect boards → evidence gates → carrier KiCad compile (S2 demos)",
            "S3 bench sessions: close measurement gates before power-on (agent/MCP/API)",
            "Inventory-constrained salvage bring-up from junk-drawer parts",
            "NL phrase / module list / canvas graph → wired schematic + placed PCB",
            "KiCad ERC/DRC as external compile truth (not LLM self-grade)",
            "Honest quality flags: copper_tier, fab_recommendation, build_ready",
            "Scratch and salvage share one engine (material_mode = parts budget only)",
        ],
        "agent_handoff": {
            "doc": "docs/AGENT_HANDOFF.md",
            "recommended_flow": [
                "hs_sdk_info",
                "hs_vision_capabilities",
                "hs_donor_board_vision (photos/board_evidence → functional_salvage)",
                "hs_splice_build",
                "hs_splice_bench_capture_template",
                "fill template → hs_splice_bench_submit_capture",
                "hs_inspect_fab",
            ],
            "shortcut_flow": [
                "hs_splice_golden_loop (build + template + simulated bench closure for CI/demo)",
            ],
            "primary_tools": [
                "hs_splice_build",
                "hs_splice_golden_loop",
                "hs_donor_board_vision",
                "hs_vision_enrich_intake",
                "hs_splice_bench_capture_template",
                "hs_splice_bench_status",
                "hs_splice_bench_submit_capture",
                "hs_inspect_fab",
            ],
        },
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
            "compose_arbitrary() uses Qwen text (qwen-turbo by default) → netlist IR when API key set; "
            "falls back to module picker. Vision Qwen is separate (bench photos only)."
        ),
        "default_env": {
            "HARDWARE_SPLICER_AUTOROUTE": "0",
            "HARDWARE_SPLICER_JLC_ENRICH": "0",
            "HARDWARE_SPLICER_DRC_FIX_LOOP": "1",
        },
        "llm_policy": llm_policy_summary(),
        "http_api": "uvicorn hardware_splicer.api:app (see scripts/hardware_splicer.py serve)",
        "mcp": "python -m hardware_splicer.mcp_server",
    }
