"""Staged compile pipeline for catalog builds.

Python owns plan→graph, geometry/DRC/KiCad, and artifact stages (no Node).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .bom_generator import build_bom_from_graph, enrich_bom_with_jlcsearch, write_bom_artifacts
from .compile_casefile import write_compile_casefile
from .firmware_scaffold import write_firmware_scaffold
from .netlist.compile import compile_netlist_to_artifacts
from .netlist.lower import build_graph_to_netlist
from .netlist.quality_flags import finalize_launch_quality
from .pcb.geometry_compile import compile_graph_to_artifacts
from .plan_to_graph import splice_plan_to_build_graph


GRAPH_STAGE_CONTRACT_VERSION = "4"


@dataclass(frozen=True)
class GraphStagePaths:
    build_graph: Optional[str]
    kicad_pcb: Optional[str]
    design_quality: Optional[str]


@dataclass(frozen=True)
class GraphStageResult:
    ok: bool
    contract_version: str
    quality: Dict[str, Any]
    paths: GraphStagePaths
    error: Optional[str] = None


def _run_geometry_stage_python(
    build_id: str,
    build_dir: Path,
    *,
    graph: Mapping[str, Any],
    notes: List[str],
    warnings: List[str],
    effective_build_id: str,
    splice_plan: Mapping[str, Any] | None = None,
) -> GraphStageResult:
    """Run netlist ERC → geometry → DRC → KiCad in Python."""
    empty_paths = GraphStagePaths(build_graph=None, kicad_pcb=None, design_quality=None)
    try:
        netlist = build_graph_to_netlist(graph, source="build_graph")
        payload = compile_netlist_to_artifacts(
            netlist,
            build_id,
            build_dir,
            graph=dict(graph),
            notes=notes,
            warnings=warnings,
        )
        if payload.get("quality"):
            payload["quality"]["effective_build_id"] = effective_build_id
    except Exception as exc:
        write_compile_casefile(
            build_dir,
            build_id=effective_build_id,
            error=str(exc),
            graph=dict(graph),
            splice_plan=splice_plan,
        )
        return GraphStageResult(
            ok=False,
            contract_version=GRAPH_STAGE_CONTRACT_VERSION,
            quality={"build_ready": False, "circuit_readiness": "compile_failed"},
            paths=empty_paths,
            error=str(exc),
        )

    paths_raw = dict(payload.get("paths") or {})
    paths = GraphStagePaths(
        build_graph=paths_raw.get("build_graph"),
        kicad_pcb=paths_raw.get("kicad_pcb"),
        design_quality=paths_raw.get("design_quality"),
    )
    quality = dict(payload.get("quality") or {})
    if splice_plan:
        quality.update(
            {
                k: splice_plan[k]
                for k in ("material_mode", "strategy_mode", "allowed_purchases", "editor_scratch_unified")
                if splice_plan.get(k) is not None
            }
        )
        payload["quality"] = quality
    ok = bool(payload.get("ok"))
    error = None if ok else str(payload.get("error") or "compile_failed")
    if not ok:
        write_compile_casefile(
            build_dir,
            build_id=effective_build_id,
            error=error or "compile_failed",
            graph=dict(graph),
            netlist=netlist.to_dict(),
            erc=payload.get("erc"),
            quality=quality,
            splice_plan=splice_plan,
        )
    return GraphStageResult(
        ok=ok,
        contract_version=GRAPH_STAGE_CONTRACT_VERSION,
        quality=quality,
        paths=paths,
        error=error,
    )


def run_graph_stage_node(
    build_id: str,
    build_dir: Path,
    *,
    splice_plan: Mapping[str, Any] | None = None,
    timeout_seconds: int = 120,
) -> GraphStageResult:
    """Python plan→graph, then Node geometry→DRC→KiCad."""
    build_dir.mkdir(parents=True, exist_ok=True)
    plan = dict(splice_plan) if splice_plan else {}
    target = dict(plan.get("target") or {})
    target.setdefault("recommended_build_id", build_id)
    plan = {**plan, "target": target}

    graph, effective_id, notes, warnings = splice_plan_to_build_graph(plan)
    effective_build_id = effective_id or build_id

    build_graph_path = build_dir / "build_graph.json"
    build_graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    if plan:
        for key in ("material_mode", "strategy_mode", "allowed_purchases", "editor_scratch_unified"):
            if plan.get(key) is not None:
                graph[key] = plan[key]
        build_graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    meta_path = build_dir / "build_graph_meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "build_id": effective_build_id,
                "notes": notes,
                "warnings": warnings,
                "graph_source": "python_plan_to_graph",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if not graph.get("nodes"):
        empty_paths = GraphStagePaths(
            build_graph=str(build_graph_path),
            kicad_pcb=None,
            design_quality=str(build_dir / "DESIGN_QUALITY.json"),
        )
        summary = "; ".join(warnings) or "empty build graph"
        write_compile_casefile(
            build_dir,
            build_id=effective_build_id,
            error=summary,
            graph=dict(graph),
            splice_plan=plan,
        )
        return GraphStageResult(
            ok=False,
            contract_version=GRAPH_STAGE_CONTRACT_VERSION,
            quality={
                "build_ready": False,
                "build_graph_compiled": False,
                "circuit_readiness": "empty_graph",
                "notes": notes,
                "warnings": warnings,
            },
            paths=empty_paths,
            error=summary,
        )

    return _run_geometry_stage_python(
        effective_build_id,
        build_dir,
        graph=graph,
        notes=notes,
        warnings=warnings,
        effective_build_id=effective_build_id,
        splice_plan=plan,
    )


def run_artifact_stage(
    *,
    build_id: str,
    build_dir: Path,
    graph_stage: GraphStageResult,
    resolved_modules: List[Mapping[str, Any]] | None = None,
    export_gerber: bool = True,
    export_gerber_fn: Any = None,
) -> Dict[str, Any]:
    """Python-owned BOM, firmware scaffold, Gerber, and quality file write-back."""
    quality = dict(graph_stage.quality)
    bom_paths: Dict[str, str] = {}
    gerber_dir: str | None = None

    build_graph_path = graph_stage.paths.build_graph
    if build_graph_path and Path(build_graph_path).is_file():
        graph = json.loads(Path(build_graph_path).read_text(encoding="utf-8"))
        bom = build_bom_from_graph(graph, resolved_modules=list(resolved_modules or []))
        bom = enrich_bom_with_jlcsearch(bom)
        bom_paths = write_bom_artifacts(bom, build_dir)
        quality["bom_ready"] = bool(bom.get("line_count"))
        quality["bom_jlc_enriched"] = bool(bom.get("jlc_enriched"))
        fw_path = write_firmware_scaffold(build_id=build_id, build_graph=graph, out_dir=build_dir)
        if fw_path:
            quality["firmware_scaffold_ready"] = True
            quality["firmware_scaffold_file"] = str(fw_path)

    kicad_path = graph_stage.paths.kicad_pcb
    if export_gerber and kicad_path and Path(kicad_path).is_file() and export_gerber_fn:
        gerber_dir = export_gerber_fn(Path(kicad_path), build_dir)
        if gerber_dir:
            quality["gerber_ready"] = True
            quality["gerber_package_dir"] = gerber_dir
        else:
            quality["gerber_ready"] = False

    quality_path = Path(graph_stage.paths.design_quality or build_dir / "DESIGN_QUALITY.json")
    quality = finalize_launch_quality(quality)
    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")
    quality["design_quality_file"] = str(quality_path)

    return {
        "quality": quality,
        "bom_paths": bom_paths,
        "gerber_dir": gerber_dir,
    }
