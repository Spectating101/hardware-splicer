from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


SCHEMA_VERSION = "hardware_splicer.design_quality_gate.v1"
GOAL_NOT_COVERED_BLOCKER = "goal_not_covered_by_selected_design"

# Build-pick sources that carry real evidence the scaffold fits the goal: an explicit
# declaration, a model proposal, or a phrase match of the goal/parts against the catalog.
# The legacy DIY/splice planners instead return their best (even one-word) token overlap, or
# a default profile, so a pick that came only from them is a fallback, not a match.
_FALLBACK_PICK_SOURCES = {"legacy_diy_planner", "legacy_splice_planner"}


def assess_goal_coverage(
    build_selection: Mapping[str, Any] | None,
    *,
    build_id: str | None,
    graph_mode: str | None = None,
) -> Dict[str, Any]:
    """Say whether the selected catalog scaffold is evidenced to cover the stated goal.

    Deterministic, uses only the pick provenance already recorded by intake. It can only
    withhold coverage; a covered result does not by itself prove the design fits the goal.
    """
    selection = dict(build_selection or {})
    source = str(selection.get("source") or "")
    picked = str(selection.get("build_id") or "")
    selected = str(build_id or "")
    covered = True
    reason = f"pick source {source or 'unknown'} is not a fallback"
    if (
        selected
        and selected == picked
        and source in _FALLBACK_PICK_SOURCES
        and str(graph_mode or "").lower() != "scratch"
    ):
        covered = False
        reason = (
            f"scaffold {selected} was chosen only by the {source} fallback (no declared, model-proposed "
            "or phrase-matched architecture); nothing shows it covers the stated goal"
        )
    out: Dict[str, Any] = {
        "covered": covered,
        "selected_build_id": selected or None,
        "pick_source": source or None,
        "reason": reason,
    }
    if not covered:
        out["blocker"] = GOAL_NOT_COVERED_BLOCKER
    return out


def apply_goal_coverage(
    quality: Dict[str, Any],
    coverage: Mapping[str, Any] | None,
    *,
    quality_file: str | Path | None = None,
) -> Dict[str, Any]:
    """Record goal coverage on a DESIGN_QUALITY dict; an uncovered goal clears readiness.

    When ``quality_file`` names an existing DESIGN_QUALITY.json it is rewritten so the file
    on disk agrees with the in-memory payload.
    """
    if not coverage:
        return quality
    quality["goal_coverage"] = dict(coverage)
    if coverage.get("covered") is False:
        quality["goal_covered_by_selected_design"] = False
        quality["build_ready"] = False
        quality["fabrication_ready"] = False
        quality["compiler_verified"] = False
    if quality_file and Path(quality_file).is_file():
        Path(quality_file).write_text(json.dumps(quality, indent=2), encoding="utf-8")
    return quality


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
    kicad_failed = False
    # Explicit KiCad failures veto readiness. Unavailable KiCad is not a failure here
    # (the trust report records it as a missing receipt); absence never upgrades.
    if body.get("kicad_erc_pass") is False and not body.get("kicad_erc_skipped"):
        blockers.append(f"KiCad ERC failed with {int(body.get('kicad_erc_errors') or 0)} error(s).")
        kicad_failed = True
    if body.get("kicad_drc_pass") is False or int(body.get("kicad_drc_errors") or 0) > 0:
        blockers.append(f"KiCad DRC failed with {int(body.get('kicad_drc_errors') or 0)} error(s).")
        kicad_failed = True
    goal_uncovered = body.get("goal_covered_by_selected_design") is False
    if goal_uncovered:
        reason = str((body.get("goal_coverage") or {}).get("reason") or "").strip()
        blockers.append(f"{GOAL_NOT_COVERED_BLOCKER}: {reason}" if reason else GOAL_NOT_COVERED_BLOCKER)
    compiler_verified = not kicad_failed and not goal_uncovered and (
        bool(body.get("compiler_verified"))
        or (drc_pass and electrical_pass and bool(body.get("build_graph_compiled")))
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
