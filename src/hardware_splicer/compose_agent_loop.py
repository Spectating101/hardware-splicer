"""Agent-facing compose orchestration — manual DRC retry rounds on top of engine fix loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .build_files import read_design_quality_summary
from .compose_dispatch import compose_dispatch
from .material_modes import resolve_material_mode
from .pcb.drc_fix_loop import propose_fixup_hints

SCHEMA_VERSION = "hardware_splicer.compose_agent_loop.v1"


def _error_violations(build_dir: str | Path) -> List[Dict[str, Any]]:
    try:
        summary = read_design_quality_summary(build_dir)
    except (ValueError, OSError):
        return []
    return list(summary.get("violations") or [])


def _drc_errors_from_result(result: Mapping[str, Any]) -> int:
    quality = dict(result.get("design_quality") or {})
    errors = quality.get("kicad_drc_errors")
    if errors is not None:
        return int(errors)
    out_dir = result.get("out_dir")
    if out_dir:
        try:
            summary = read_design_quality_summary(out_dir)
            if summary.get("kicad_drc_errors") is not None:
                return int(summary["kicad_drc_errors"])
        except (ValueError, OSError):
            pass
    return 1


def compose_agent_loop(
    *,
    phrase: str | None = None,
    module_ids: list[str] | None = None,
    canvas_nodes: list[Dict[str, Any]] | None = None,
    canvas_wires: list[Dict[str, Any]] | None = None,
    netlist: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    material_mode: str | None = None,
    salvage_mode: bool = False,
    export_gerber: bool = False,
    wire_only: bool = False,
    allow_llm_first: bool = False,
    drc_fixup: Mapping[str, float] | None = None,
    out_dir: str | Path | None = None,
    request_id: str | None = None,
    max_manual_retries: int = 2,
    finalize_package: bool = False,
    goal: str | None = None,
    project_name: str | None = None,
) -> Dict[str, Any]:
    """Compose with bounded manual DRC fixup rounds — for MCP/HTTP agents and Design Studio."""
    if wire_only:
        raise ValueError("wire_only is not supported on agent-loop compose")

    constraints_map = dict(constraints or {})
    mode = material_mode or resolve_material_mode(
        constraints=constraints_map,
        salvage_mode=salvage_mode,
    )
    hints: Dict[str, float] = dict(drc_fixup or {})
    rounds: List[Dict[str, Any]] = []
    last_result: Dict[str, Any] = {}
    errors = 1

    limit = max(0, int(max_manual_retries))
    for round_idx in range(limit + 1):
        target = Path(out_dir) if out_dir and round_idx == 0 else None
        if round_idx > 0 and last_result.get("out_dir"):
            target = Path(str(last_result["out_dir"])).parent / f"retry-{round_idx}"
        if target is None and out_dir:
            target = Path(out_dir)
        if target is None:
            from .runtime import scratch_path
            import uuid

            target = scratch_path("compose_agent") / uuid.uuid4().hex[:12]

        last_result = compose_dispatch(
            out_dir=str(target),
            phrase=phrase,
            module_ids=module_ids,
            canvas_nodes=canvas_nodes,
            canvas_wires=canvas_wires,
            netlist=netlist,
            constraints=constraints_map,
            material_mode=mode,
            salvage_mode=salvage_mode,
            export_gerber=export_gerber,
            allow_llm_first=allow_llm_first,
            drc_fixup=hints or None,
            request_id=request_id,
        )
        errors = _drc_errors_from_result(last_result)
        violations = _error_violations(str(last_result.get("out_dir") or target))
        quality = dict(last_result.get("design_quality") or {})
        rounds.append(
            {
                "round": round_idx,
                "out_dir": last_result.get("out_dir"),
                "ok": bool(last_result.get("ok")),
                "mode": last_result.get("mode"),
                "kicad_drc_errors": errors,
                "kicad_drc_warnings": int(quality.get("kicad_drc_warnings") or 0),
                "drc_fixup": dict(hints),
                "engine_drc_fix_loop": quality.get("drc_fix_loop"),
                "violation_count": len(violations),
                "violation_types": sorted({str(v.get("type") or "unknown") for v in violations}),
            }
        )
        if errors == 0:
            break
        next_hints = propose_fixup_hints(violations, hints)
        if next_hints == hints:
            break
        hints = next_hints

    agent_loop = {
        "schema_version": SCHEMA_VERSION,
        "rounds": rounds,
        "manual_retries_used": max(0, len(rounds) - 1),
        "resolved": errors == 0,
        "final_kicad_drc_errors": errors,
        "final_drc_fixup": dict(hints),
        "copper_tier": (last_result.get("design_quality") or {}).get("copper_tier"),
        "fab_recommendation": (last_result.get("design_quality") or {}).get("fab_recommendation"),
    }

    payload: Dict[str, Any] = {**last_result, "agent_loop": agent_loop}
    if finalize_package and last_result.get("out_dir"):
        from .sdk import finalize_compose_job_result

        final = finalize_compose_job_result(
            last_result,
            goal=goal or phrase or project_name or "compose",
            project_name=project_name or phrase or Path(str(last_result["out_dir"])).name,
        )
        payload = {**final, "agent_loop": agent_loop}

    return payload
