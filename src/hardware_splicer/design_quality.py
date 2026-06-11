from __future__ import annotations

from typing import Any, Dict, Mapping


SCHEMA_VERSION = "hardware_splicer.design_quality_gate.v1"


def build_design_quality_gate(
    design_quality: Mapping[str, Any] | None,
    *,
    engineering: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    body = dict(design_quality or {})
    engineering = dict(engineering or {})
    analysis = dict(engineering.get("analysis") or {})
    circuit = dict(analysis.get("circuit") or {})
    readiness = str(circuit.get("readiness_level") or circuit.get("readiness") or body.get("circuit_readiness") or "unknown")

    build_ready = bool(body.get("build_ready"))
    drc_pass = bool(body.get("drc_pass"))
    electrical_pass = bool(body.get("electrical_safety_pass"))
    gerber_ready = bool(body.get("gerber_ready"))
    electrical_warnings = int(body.get("electrical_warnings") or 0)
    bom_ready = bool(body.get("bom_ready"))

    blockers = []
    if not body.get("build_graph_compiled"):
        blockers.append("Catalog build graph did not compile.")
    if not electrical_pass:
        blockers.append("Electrical safety checks failed on the compiled build graph.")
    if drc_pass and electrical_pass and electrical_warnings > 0:
        blockers.append(f"Electrical safety has {electrical_warnings} warning(s) — resolve before fabrication.")
    if not drc_pass:
        blockers.append(f"DRC failed with {body.get('drc_errors', 0)} error(s).")
    compiler_verified = bool(body.get("compiler_verified")) or (
        drc_pass and electrical_pass and bool(body.get("build_graph_compiled"))
    )
    if readiness == "draft" and build_ready and not compiler_verified:
        blockers.append("Circuit engineering readiness is still draft while build graph claims readiness.")

    fabrication_blockers = list(blockers)
    if not gerber_ready:
        fabrication_blockers.append("Gerber export is not ready.")
    if not bom_ready:
        fabrication_blockers.append("BOM is missing or empty.")

    score = 0.0
    if body.get("build_graph_compiled"):
        score += 0.25
    if electrical_pass:
        score += 0.25
    if drc_pass:
        score += 0.30
    if build_ready:
        score += 0.10
    if gerber_ready:
        score += 0.05
    if bom_ready:
        score += 0.05

    strict_build_ready = build_ready and not blockers
    fabrication_ready = bool(body.get("fabrication_ready")) and gerber_ready and bom_ready and not fabrication_blockers

    return {
        "schema_version": SCHEMA_VERSION,
        "design_quality_score": round(min(score, 1.0), 3),
        "build_ready": strict_build_ready,
        "fabrication_ready": fabrication_ready,
        "compiler_verified": compiler_verified,
        "circuit_readiness": "build_ready" if compiler_verified else readiness,
        "drc_pass": drc_pass,
        "electrical_safety_pass": electrical_pass,
        "gerber_ready": gerber_ready,
        "blockers": blockers,
        "summary": body,
    }
