"""Compile build_graph.json → geometry, DRC, KiCad, design quality (Python engine)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from ..catalog import CATALOG_BUILD_IDS
from ..compile_casefile import write_compile_casefile
from ..integrations.freerouting_bridge import run_freerouting_pipeline, summarize_freerouting_for_quality
from .build_to_geometry import build_graph_to_geometry
from .drc import run_drc
from .kicad_cli_drc import run_kicad_cli_drc, summarize_for_quality
from .kicad_serializer import serialize_build_to_kicad_pcb
from .safety_rules import analyze_build


def _autoroute_enabled() -> bool:
    """FreeRouting is opt-in (heavy: Java). Default uses cosmetic segments only."""
    return os.environ.get("HARDWARE_SPLICER_AUTOROUTE", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def compile_graph_to_artifacts(
    build_id: str,
    out_dir: str | Path,
    graph: Mapping[str, Any],
    *,
    notes: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    effective_build_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Mirror scripts/compile_geometry.cjs compileGraph()."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    notes = list(notes or [])
    warnings = list(warnings or [])
    resolved_build_id = effective_build_id or build_id

    electrical = analyze_build(dict(graph))
    electrical_errors = [w for w in electrical if w.get("level") == "error"]
    electrical_warnings = [w for w in electrical if w.get("level") == "warn"]

    geometry: Dict[str, Any] = {}
    drc: Dict[str, Any] = {"pass": False, "violations": [], "summary": {"errors": 1, "warnings": 0, "byRule": {"empty": 1}}}
    kicad_text = ""

    nodes = graph.get("nodes") or []
    if nodes:
        geometry = build_graph_to_geometry(dict(graph))
        drc = run_drc(geometry)
        kicad_text = serialize_build_to_kicad_pcb(dict(graph), geometry)
    else:
        drc = {
            "pass": False,
            "violations": [{"rule": "trace-short", "severity": "error", "message": "Empty build graph"}],
            "summary": {"errors": 1, "warnings": 0, "byRule": {"empty": 1}},
        }

    drc_errors = sum(1 for v in drc.get("violations") or [] if v.get("severity") == "error")
    build_ready = (
        bool(nodes)
        and not electrical_errors
        and drc.get("pass") is True
        and kicad_text.startswith("(kicad_pcb")
    )
    fabrication_ready = (
        bool(nodes)
        and not electrical_errors
        and not electrical_warnings
        and drc.get("pass") is True
        and kicad_text.startswith("(kicad_pcb")
    )

    build_graph_path = out / "build_graph.json"
    kicad_path = out / "main_ctrl_build.kicad_pcb"
    quality_path = out / "DESIGN_QUALITY.json"

    build_graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    kicad_drc: Dict[str, Any] = {"skipped": True, "pass": None}
    freerouting_report: Dict[str, Any] = {"skipped": True}
    if kicad_text:
        kicad_path.write_text(kicad_text, encoding="utf-8")

        if _autoroute_enabled():
            freerouting_report = run_freerouting_pipeline(kicad_path, out_dir=out / "freerouting")
            if freerouting_report.get("ok") and freerouting_report.get("routed_pcb_path"):
                routed = Path(str(freerouting_report["routed_pcb_path"]))
                if routed.is_file():
                    shutil.copyfile(routed, kicad_path)
                    fr_meta = out / "freerouting" / "report.json"
                    fr_meta.write_text(json.dumps(freerouting_report, indent=2), encoding="utf-8")

        kicad_drc = run_kicad_cli_drc(kicad_path, out_dir=out)
        kicad_drc_path = out / "KICAD_DRC.json"
        if kicad_drc.get("report_path"):
            kicad_drc_path.write_text(
                json.dumps(
                    {
                        "pass": kicad_drc.get("pass"),
                        "errors": kicad_drc.get("errors"),
                        "warnings": kicad_drc.get("warnings"),
                        "violations": kicad_drc.get("violations"),
                        "kicad_version": kicad_drc.get("kicad_version"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        if int(kicad_drc.get("errors") or 0) > 0:
            write_compile_casefile(
                out,
                build_id=resolved_build_id,
                error="kicad_drc_failed",
                graph=dict(graph),
                quality={"kicad_drc_errors": kicad_drc.get("errors")},
            )

    bbox = (geometry.get("board") or {}).get("bbox_mm") or {}
    board_outline = None
    if geometry:
        board_outline = {
            "width_mm": bbox.get("width") or (geometry.get("board") or {}).get("width_mm"),
            "height_mm": bbox.get("height") or (geometry.get("board") or {}).get("height_mm"),
            "bbox_mm": bbox,
            "footprint_count": len(geometry.get("footprints") or []),
            "trace_segments": len(geometry.get("segments") or []),
            "via_count": len(geometry.get("vias") or []),
        }

    quality = {
        "schema_version": "hardware_splicer.design_quality.v1",
        "build_id": resolved_build_id,
        "build_ready": build_ready,
        "fabrication_ready": fabrication_ready,
        "build_graph_compiled": bool(nodes),
        "electrical_safety_pass": not electrical_errors,
        "drc_pass": drc.get("pass") is True,
        "drc_errors": drc_errors,
        "drc_warnings": (drc.get("summary") or {}).get("warnings", 0),
        "electrical_errors": len(electrical_errors),
        "electrical_warnings": len(electrical_warnings),
        "circuit_readiness": "build_ready" if build_ready else "blocked",
        "gerber_ready": False,
        "kicad_pcb_path": str(kicad_path) if kicad_text else None,
        "board_outline": board_outline,
        "module_count": len(nodes),
        "wire_count": len(graph.get("wires") or []),
        "notes": notes,
        "warnings": [*warnings, *[w.get("message", "") for w in electrical_warnings]],
        "electrical_issues": [
            {
                "level": w.get("level"),
                "message": w.get("message"),
                "wire_id": w.get("wireId"),
                "node_id": w.get("nodeId"),
            }
            for w in electrical
        ],
        "drc_violations": drc.get("violations") or [],
        "supported_build_ids": CATALOG_BUILD_IDS,
        "geometry_engine": "python_pcb_stack",
        "copper_preview_mode": "single_layer"
        if os.environ.get("HARDWARE_SPLICER_SINGLE_LAYER_PREVIEW", "0").strip().lower() in ("1", "true", "yes", "on")
        else "dual_layer",
        "copper_preview_notes": [
            "Preview copper is cosmetic — not fabrication routing.",
            "KiCad via_dangling warnings are expected until autoroute (HARDWARE_SPLICER_AUTOROUTE=1).",
        ],
        **({"material_mode": graph.get("material_mode")} if graph.get("material_mode") else {}),
        **summarize_for_quality(kicad_drc),
        **summarize_freerouting_for_quality(freerouting_report),
    }

    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")

    return {
        "ok": build_ready,
        "buildId": resolved_build_id,
        "outDir": str(out),
        "paths": {
            "build_graph": str(build_graph_path),
            "kicad_pcb": str(kicad_path) if kicad_text else None,
            "design_quality": str(quality_path),
            "freerouting_report": str(out / "freerouting" / "report.json")
            if (out / "freerouting" / "report.json").is_file()
            else None,
        },
        "quality": quality,
    }
