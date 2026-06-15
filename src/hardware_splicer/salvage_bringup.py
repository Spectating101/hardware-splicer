"""Salvage bring-up orchestration with evidence report."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from .design_quality import build_design_quality_gate
from .project_intake import splice_and_build_from_intake

SCHEMA_VERSION = "hardware_splicer.salvage_bringup.v1"


def run_salvage_bringup(
    intake: Mapping[str, Any],
    *,
    out_dir: str | Path,
    export_gerber: bool = False,
) -> Dict[str, Any]:
    """Junk-drawer intake → splice + compile → SALVAGE_BRINGUP_REPORT.json."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    os.environ.setdefault("HARDWARE_SPLICER_AUTOROUTE", "0")
    os.environ.setdefault("HARDWARE_SPLICER_JLC_ENRICH", "0")
    os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")

    result = splice_and_build_from_intake(intake, out_dir=out_path, export_gerber=export_gerber)
    build_dir = out_path / "build_compilation"
    quality_path = build_dir / "DESIGN_QUALITY.json"
    quality: Dict[str, Any] = {}
    if quality_path.is_file():
        quality = json.loads(quality_path.read_text(encoding="utf-8"))

    gate = build_design_quality_gate(quality)
    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_name": intake.get("project_name"),
        "goal": intake.get("goal"),
        "salvage_mode": bool(intake.get("salvage_mode")),
        "parts_count": len(intake.get("available_parts") or []),
        "ok": bool(result.get("ok")),
        "build_id": result.get("build_id"),
        "seconds": round(time.time() - t0, 2),
        "quality_summary": {
            "build_ready": quality.get("build_ready"),
            "material_mode": quality.get("material_mode"),
            "strategy_mode": quality.get("strategy_mode"),
            "copper_preview_mode": quality.get("copper_preview_mode"),
            "kicad_truth_pass": quality.get("kicad_truth_pass"),
            "kicad_drc_errors": quality.get("kicad_drc_errors"),
            "kicad_drc_warnings": quality.get("kicad_drc_warnings"),
            "copper_tier": quality.get("copper_tier"),
            "fab_recommendation": quality.get("fab_recommendation"),
            "drc_fix_resolved": (quality.get("drc_fix_loop") or {}).get("resolved"),
            "drc_fix_attempts": len((quality.get("drc_fix_loop") or {}).get("attempts") or []),
        },
        "design_quality_gate": gate,
        "artifacts": {
            "out_dir": str(out_path),
            "splice_plan": str(out_path / "SPLICE_PLAN.json") if (out_path / "SPLICE_PLAN.json").is_file() else None,
            "project_intake": str(out_path / "PROJECT_INTAKE.json") if (out_path / "PROJECT_INTAKE.json").is_file() else None,
            "build_graph": str(build_dir / "build_graph.json") if (build_dir / "build_graph.json").is_file() else None,
            "circuit_netlist": str(build_dir / "circuit_netlist.json") if (build_dir / "circuit_netlist.json").is_file() else None,
            "kicad_pcb": str(build_dir / "main_ctrl_build.kicad_pcb") if (build_dir / "main_ctrl_build.kicad_pcb").is_file() else None,
            "kicad_drc": str(build_dir / "KICAD_DRC.json") if (build_dir / "KICAD_DRC.json").is_file() else None,
            "design_quality": str(quality_path) if quality_path.is_file() else None,
            "drc_fix_loop": str(build_dir / "DRC_FIX_LOOP.json") if (build_dir / "DRC_FIX_LOOP.json").is_file() else None,
            "compiler_evidence": str(out_path / "COMPILER_EVIDENCE_PATCH.json")
            if (out_path / "COMPILER_EVIDENCE_PATCH.json").is_file()
            else None,
            "compile_casefile": str(build_dir / "COMPILE_CASEFILE.json")
            if (build_dir / "COMPILE_CASEFILE.json").is_file()
            else None,
            "functional_delivery": str(out_path / "FUNCTIONAL_DELIVERY.json")
            if (out_path / "FUNCTIONAL_DELIVERY.json").is_file()
            else None,
        },
        "review_checklist": [
            "Open KICAD_DRC.json — errors must be 0 for bring-up pass",
            "Check copper_tier is cosmetic_preview (autoroute not run)",
            "Confirm fab_recommendation is review_required_preview_copper",
            "Inspect circuit_netlist.json matches salvaged module IDs",
            "Read DRC_FIX_LOOP.json if KiCad needed geometry nudges",
        ],
    }
    report_path = out_path / "SALVAGE_BRINGUP_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
