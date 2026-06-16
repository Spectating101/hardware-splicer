"""Structured compose failure payloads (gate 3.9)."""

from __future__ import annotations

from typing import Any, Dict, Mapping, MutableMapping, Sequence

SCHEMA_VERSION = "hardware_splicer.compose_failure.v1"


def infer_compose_failure_type(
    *,
    mode: str,
    error: str | None,
    design_quality: Mapping[str, Any] | None,
    design_quality_gate: Mapping[str, Any] | None,
) -> str:
    err = (error or "").lower()
    quality = dict(design_quality or {})
    gate = dict(design_quality_gate or {})

    if "need >=2 modules" in err or quality.get("circuit_readiness") == "module_pick_failed":
        return "module_pick_failed"
    if not quality.get("build_graph_compiled") and mode in {"scratch", "canvas", "netlist", "llm_first"}:
        return "graph_compile_failed"
    if quality.get("drc_pass") is False:
        return "drc_failed"
    if quality.get("electrical_safety_pass") is False:
        return "electrical_safety_failed"
    if gate.get("blockers") and not gate.get("build_ready"):
        return "design_quality_failed"
    if err:
        return "compile_failed"
    return "compose_failed"


def build_compose_failure(
    *,
    mode: str,
    stage: str | None = None,
    error: str | None = None,
    design_quality_gate: Mapping[str, Any] | None = None,
    design_quality: Mapping[str, Any] | None = None,
    casefile_path: str | None = None,
    attempts: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    gate = dict(design_quality_gate or {})
    blockers = [str(row) for row in (gate.get("blockers") or []) if row]
    if error and error not in blockers:
        blockers.insert(0, error)
    failure_type = infer_compose_failure_type(
        mode=mode,
        error=error,
        design_quality=design_quality,
        design_quality_gate=gate,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "type": failure_type,
        "stage": stage or mode,
        "blockers": blockers,
        "casefile_path": casefile_path,
        "attempts": list(attempts or []),
        "message": error or (blockers[0] if blockers else None),
    }


def attach_compose_failure(payload: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Attach stable failure block when compose did not reach build_ready."""
    if payload.get("ok"):
        return dict(payload)
    mode = str(payload.get("mode") or "compose")
    compile_result = payload.get("compile_result")
    casefile_path = payload.get("compile_casefile")
    if not casefile_path and isinstance(compile_result, Mapping):
        casefile_path = compile_result.get("compile_casefile")
    artifacts = payload.get("artifacts")
    if not casefile_path and isinstance(artifacts, Mapping):
        casefile_path = artifacts.get("compile_casefile")

    out = dict(payload)
    out["failure"] = build_compose_failure(
        mode=mode,
        stage=str(payload.get("stage") or mode),
        error=payload.get("error") if isinstance(payload.get("error"), str) else None,
        design_quality_gate=payload.get("design_quality_gate"),
        design_quality=payload.get("design_quality"),
        casefile_path=casefile_path,
        attempts=payload.get("attempts") if isinstance(payload.get("attempts"), list) else None,
    )
    return out
