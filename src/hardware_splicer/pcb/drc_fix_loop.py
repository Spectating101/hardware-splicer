"""KiCad DRC violation → structured geometry fixups → recompile (neurosymbolic hook)."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional

SCHEMA_VERSION = "hardware_splicer.drc_fix_loop.v1"

CompileFn = Callable[..., Dict[str, Any]]


def _fix_loop_enabled() -> bool:
    return os.environ.get("HARDWARE_SPLICER_DRC_FIX_LOOP", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _max_attempts() -> int:
    try:
        return max(0, int(os.environ.get("HARDWARE_SPLICER_DRC_FIX_MAX", "4")))
    except ValueError:
        return 4


def classify_violation(violation: Mapping[str, Any]) -> str:
    """Map KiCad DRC JSON row to a fix strategy bucket."""
    vtype = str(violation.get("type") or "").lower()
    desc = str(violation.get("description") or "").lower()
    if "edge" in vtype or "edge" in desc:
        return "edge_clearance"
    if "clearance" in vtype or "clearance" in desc:
        return "clearance"
    if "short" in vtype or "short" in desc:
        return "shorting"
    if "overlap" in vtype or "courtyard" in desc:
        return "courtyard"
    return "generic"


def propose_fixup_hints(
    violations: List[Mapping[str, Any]],
    current: Mapping[str, Any] | None = None,
) -> Dict[str, float]:
    """Turn KiCad error violations into incremental geometry hint deltas."""
    hints = dict(current or {})
    errors = [v for v in violations if str(v.get("severity") or "").lower() == "error"]
    if not errors:
        return hints

    buckets = {classify_violation(v) for v in errors}
    if "edge_clearance" in buckets or "generic" in buckets:
        hints["edge_pad_extra_mm"] = float(hints.get("edge_pad_extra_mm") or 0) + 0.35
    if "clearance" in buckets or "generic" in buckets:
        hints["via_clearance_mm"] = max(float(hints.get("via_clearance_mm") or 0.21), 0.21) + 0.06
    if "shorting" in buckets or "courtyard" in buckets:
        hints["module_gap_extra_mm"] = float(hints.get("module_gap_extra_mm") or 0) + 4.0
    if not buckets - {"generic"} and "generic" in buckets:
        hints["edge_pad_extra_mm"] = float(hints.get("edge_pad_extra_mm") or 0) + 0.25
        hints["via_clearance_mm"] = max(float(hints.get("via_clearance_mm") or 0.21), 0.21) + 0.04

    return hints


def apply_fixup_to_graph(graph: MutableMapping[str, Any], hints: Mapping[str, float]) -> None:
    graph["drc_fixup"] = {k: round(float(v), 4) for k, v in hints.items()}


def _violations_from_quality(quality: Mapping[str, Any], out_dir: Path) -> List[Dict[str, Any]]:
    report_path = quality.get("kicad_drc_report_path")
    if report_path and Path(str(report_path)).is_file():
        payload = json.loads(Path(str(report_path)).read_text(encoding="utf-8"))
        return list(payload.get("violations") or [])
    fallback = out_dir / "KICAD_DRC.json"
    if fallback.is_file():
        payload = json.loads(fallback.read_text(encoding="utf-8"))
        return list(payload.get("violations") or [])
    return []


def compile_with_drc_fixup_loop(
    compile_fn: CompileFn,
    build_id: str,
    out_dir: str | Path,
    graph: Mapping[str, Any],
    *,
    compile_kwargs: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compile, propose fixups from KiCad DRC errors, recompile until clean or budget exhausted."""
    out = Path(out_dir)
    compile_kwargs = dict(compile_kwargs or {})
    working = copy.deepcopy(dict(graph))
    hints: Dict[str, float] = dict(working.get("drc_fixup") or {})
    attempts: List[Dict[str, Any]] = []
    last_payload: Dict[str, Any] = {}

    if not _fix_loop_enabled():
        return compile_fn(build_id, out, working, **compile_kwargs)

    limit = _max_attempts()
    for attempt in range(limit + 1):
        apply_fixup_to_graph(working, hints)
        last_payload = compile_fn(build_id, out, working, **compile_kwargs)
        quality = dict(last_payload.get("quality") or {})
        kicad_errors = int(quality.get("kicad_drc_errors") or 0)
        violations = _violations_from_quality(quality, out)
        error_violations = [v for v in violations if str(v.get("severity") or "").lower() == "error"]
        attempts.append(
            {
                "attempt": attempt,
                "kicad_drc_errors": kicad_errors,
                "kicad_drc_warnings": int(quality.get("kicad_drc_warnings") or 0),
                "drc_fixup": dict(hints),
                "fix_buckets": sorted({classify_violation(v) for v in error_violations}),
                "violation_types": sorted({str(v.get("type") or "unknown") for v in error_violations}),
            }
        )
        if kicad_errors == 0:
            break
        next_hints = propose_fixup_hints(error_violations, hints)
        if next_hints == hints:
            break
        hints = next_hints

    loop_report = {
        "schema_version": SCHEMA_VERSION,
        "enabled": True,
        "attempts": attempts,
        "final_kicad_drc_errors": attempts[-1]["kicad_drc_errors"] if attempts else None,
        "resolved": bool(attempts and attempts[-1]["kicad_drc_errors"] == 0),
    }
    quality = dict(last_payload.get("quality") or {})
    quality["drc_fix_loop"] = loop_report
    last_payload["quality"] = quality
    quality_path = out / "DESIGN_QUALITY.json"
    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")
    (out / "DRC_FIX_LOOP.json").write_text(json.dumps(loop_report, indent=2), encoding="utf-8")
    return last_payload
