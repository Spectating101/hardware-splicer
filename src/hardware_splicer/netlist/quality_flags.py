"""Honest launch labels for compile quality (copper tier, fab guidance)."""

from __future__ import annotations

from typing import Any, Dict, Mapping


def copper_tier(*, freerouting_ok: bool, track_count: int, segment_count: int) -> str:
    if freerouting_ok and track_count > 0:
        return "autorouted"
    if segment_count > 0:
        return "cosmetic_preview"
    return "placement_only"


def fab_recommendation(
    *,
    kicad_drc_pass: bool,
    kicad_drc_errors: int,
    kicad_erc_pass: bool,
    copper: str,
    gerber_ready: bool,
) -> str:
    if not kicad_drc_pass or kicad_drc_errors > 0:
        return "blocked_drc"
    if not kicad_erc_pass:
        return "blocked_erc"
    if copper != "autorouted":
        return "review_required_preview_copper"
    if not gerber_ready:
        return "review_required_no_gerbers"
    return "eligible_with_human_review"


def attach_launch_quality_flags(
    quality: Dict[str, Any],
    *,
    freerouting_report: Mapping[str, Any],
    kicad_drc: Mapping[str, Any],
    kicad_erc: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Merge honest launch fields into DESIGN_QUALITY payload."""
    board = quality.get("board_outline") or {}
    segments = int(board.get("trace_segments") or 0)
    fr_ok = bool(freerouting_report.get("ok"))
    tracks = int(freerouting_report.get("track_count") or 0)
    copper = copper_tier(freerouting_ok=fr_ok, track_count=tracks, segment_count=segments)

    kicad_drc_pass = bool(kicad_drc.get("pass"))
    kicad_drc_errors = int(kicad_drc.get("errors") or 0)
    kicad_erc_pass = True if kicad_erc is None else bool(kicad_erc.get("pass"))
    gerber_ready = bool(quality.get("gerber_ready"))

    quality["copper_tier"] = copper
    quality["kicad_truth_pass"] = kicad_drc_pass and kicad_drc_errors == 0 and kicad_erc_pass
    quality["fab_recommendation"] = fab_recommendation(
        kicad_drc_pass=kicad_drc_pass,
        kicad_drc_errors=kicad_drc_errors,
        kicad_erc_pass=kicad_erc_pass,
        copper=copper,
        gerber_ready=gerber_ready,
    )
    # Fabrication requires KiCad-clean + real copper path (autoroute not enabled in launch profile).
    quality["fabrication_ready"] = (
        bool(quality.get("build_ready"))
        and quality["kicad_truth_pass"]
        and copper == "autorouted"
        and gerber_ready
    )
    return quality


def finalize_launch_quality(quality: Dict[str, Any]) -> Dict[str, Any]:
    """Apply launch flags from fields already merged into DESIGN_QUALITY."""
    kicad_drc = {
        "pass": quality.get("kicad_drc_pass"),
        "errors": quality.get("kicad_drc_errors"),
        "warnings": quality.get("kicad_drc_warnings"),
    }
    kicad_erc = {
        "pass": quality.get("kicad_erc_pass"),
        "errors": quality.get("kicad_erc_errors"),
    }
    freerouting = {
        "ok": quality.get("freerouting_ok"),
        "track_count": quality.get("freerouting_track_count"),
    }
    return attach_launch_quality_flags(
        quality,
        freerouting_report=freerouting,
        kicad_drc=kicad_drc,
        kicad_erc=kicad_erc,
    )
