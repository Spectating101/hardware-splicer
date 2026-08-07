"""Unified compose dispatch — single spine for API, CLI, and SDK."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .auto_wire import compose_build_graph_from_module_ids
from .build_compiler import compile_catalog_build, compile_from_netlist, merge_fabrication_into_payload
from .canvas_compose import build_canvas_graph, compile_canvas_build
from .compose_failure import attach_compose_failure
from .design_quality import build_design_quality_gate
from .material_modes import material_mode_summary, resolve_material_mode
from .module_picker import pick_modules_for_goal
from .scratch_pipeline import compile_scratch_build

SCHEMA_VERSION = "hardware_splicer.compose_dispatch.v1"


def _finalize_payload(
    payload: Dict[str, Any],
    *,
    quality: Mapping[str, Any],
    request_id: str | None = None,
    compile_payload: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    gate = build_design_quality_gate(dict(quality))
    out = {
        "schema_version": SCHEMA_VERSION,
        **payload,
        "design_quality": dict(quality),
        "design_quality_gate": gate,
    }
    if request_id:
        out["request_id"] = request_id
    compile_ok = bool(payload.get("ok"))
    out["ok"] = bool(compile_ok and gate.get("build_ready"))
    out = merge_fabrication_into_payload(out, compile_payload=compile_payload)
    return attach_compose_failure(out)


def _semantic_review_payload(
    proposal: Mapping[str, Any],
    *,
    target: Path,
    mode: str,
    wire_only: bool,
    constraints: Mapping[str, Any],
    material_mode: str,
    request_id: str | None,
) -> Dict[str, Any]:
    return attach_compose_failure(
        {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "mode": mode,
            "wire_only": wire_only,
            "out_dir": str(target),
            "module_ids": list(proposal.get("module_ids") or []),
            "requires_human_review": True,
            "semantic_intent": proposal.get("semantic_intent"),
            "semantic_candidate_set": proposal.get("semantic_candidate_set"),
            "semantic_selection": proposal.get("semantic_selection"),
            "authority_effect": "none",
            "automatic_execution": False,
            "error": proposal.get("error") or "semantic_module_review_required",
            **material_mode_summary(material_mode=material_mode, constraints=constraints),  # type: ignore[arg-type]
            **({"request_id": request_id} if request_id else {}),
        }
    )


def compose_dispatch(
    *,
    out_dir: str | Path,
    phrase: str | None = None,
    module_ids: Sequence[str] | None = None,
    resolved_modules: Sequence[Mapping[str, Any]] | None = None,
    canvas_nodes: Sequence[Mapping[str, Any]] | None = None,
    canvas_wires: Sequence[Mapping[str, Any]] | None = None,
    netlist: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    material_mode: str | None = None,
    salvage_mode: bool = False,
    export_gerber: bool = False,
    wire_only: bool = False,
    allow_llm_first: bool = False,
    drc_fixup: Mapping[str, float] | None = None,
    request_id: str | None = None,
    build_id: str | None = None,
    splice_plan: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Route compose requests through one implementation.

    Model-first phrase interpretation may return a reviewable semantic proposal rather
    than silently executing a fallback selection. Explicit module IDs, canvas/netlist
    inputs, accepted tool actions, and offline compatibility paths remain deterministic.
    """
    constraints_map = dict(constraints or {})
    mode = material_mode or resolve_material_mode(
        constraints=constraints_map,
        salvage_mode=salvage_mode,
    )
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    if canvas_nodes is not None:
        if wire_only:
            graph = build_canvas_graph(
                nodes=list(canvas_nodes),
                wires=list(canvas_wires or []),
                constraints=constraints_map,
                salvage_mode=salvage_mode,
                material_mode=mode,
            )
            return attach_compose_failure(
                {
                    "ok": bool(graph.get("nodes")),
                    "mode": "canvas",
                    "wire_only": True,
                    "out_dir": str(target),
                    "graph": graph,
                    **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
                    **({"request_id": request_id} if request_id else {}),
                }
            )

        canvas = compile_canvas_build(
            out_dir=str(target),
            nodes=list(canvas_nodes),
            wires=list(canvas_wires or []),
            constraints=constraints_map,
            salvage_mode=salvage_mode,
            material_mode=mode,
            export_gerber=export_gerber,
            drc_fixup=drc_fixup,
        )
        quality = (canvas.compile_result.design_quality if canvas.compile_result else {}) or {}
        compile_payload = canvas.compile_result.to_dict() if canvas.compile_result else None
        return _finalize_payload(
            {
                "ok": canvas.ok,
                "mode": "canvas",
                "out_dir": str(target),
                **canvas.to_dict(),
                **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
            },
            quality=quality,
            request_id=request_id,
            compile_payload=compile_payload,
        )

    if netlist is not None:
        result = compile_from_netlist(
            netlist,
            target,
            build_id=build_id or "generic_low_voltage_build",
            export_gerber=export_gerber,
        )
        quality = result.design_quality or {}
        return _finalize_payload(
            {
                "ok": result.ok,
                "mode": "netlist",
                "out_dir": str(target),
                **result.to_dict(),
            },
            quality=quality,
            request_id=request_id,
            compile_payload=result.to_dict(),
        )

    if not phrase and not module_ids:
        raise ValueError("phrase, module_ids, canvas_nodes, or netlist is required")

    if wire_only:
        ids = list(module_ids or [])
        if not ids and phrase:
            if allow_llm_first:
                from .jarvis_build import llm_first_enabled

                if llm_first_enabled():
                    from .integrations.qwen_netlist_compose import semantic_module_proposal_from_goal

                    proposal = semantic_module_proposal_from_goal(phrase, constraints=constraints_map)
                    if proposal.get("requires_human_review"):
                        return _semantic_review_payload(
                            proposal,
                            target=target,
                            mode="semantic_module_proposal",
                            wire_only=True,
                            constraints=constraints_map,
                            material_mode=mode,
                            request_id=request_id,
                        )
            ids = list(pick_modules_for_goal(phrase).module_ids)
        if len(ids) < 2:
            raise ValueError(f"wire_only compose needs >=2 modules, got {ids}")
        composed = compose_build_graph_from_module_ids(ids)
        graph = composed.get("graph") or {}
        return attach_compose_failure(
            {
                "ok": bool(graph.get("nodes")),
                "mode": "scratch",
                "wire_only": True,
                "out_dir": str(target),
                "module_ids": ids,
                "graph": graph,
                "warnings": composed.get("warnings") or [],
                **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
                **({"request_id": request_id} if request_id else {}),
            }
        )

    if (
        allow_llm_first
        and phrase
        and not module_ids
        and not resolved_modules
        and not salvage_mode
    ):
        from .jarvis_build import _enrich_trust, _open_compose_llm_first, llm_first_enabled

        if llm_first_enabled():
            open_result = _open_compose_llm_first(
                phrase,
                target,
                constraints=constraints_map,
                export_gerber=export_gerber,
                allow_qwen=True,
            )
            compile_result = open_result.get("compile_result")
            quality = dict(compile_result.design_quality if compile_result else {})
            build_dir = target / "build_compilation"
            if compile_result:
                _enrich_trust(
                    build_dir,
                    goal=phrase,
                    compose_mode=str(open_result.get("compose_mode") or "unknown"),
                    design_quality=quality,
                )
            return _finalize_payload(
                {
                    "ok": bool(open_result.get("ok")),
                    "mode": "llm_first",
                    "compose_mode": open_result.get("compose_mode"),
                    "qwen_usage": open_result.get("qwen_usage"),
                    "out_dir": str(target),
                    "build_id": getattr(compile_result, "build_id", None) if compile_result else None,
                    "module_ids": open_result.get("module_ids") or [],
                    "attempts": open_result.get("attempts") or [],
                    "fallback": open_result.get("fallback"),
                    "error": open_result.get("error"),
                    "requires_human_review": bool(open_result.get("requires_human_review")),
                    "semantic_intent": open_result.get("semantic_intent"),
                    "semantic_candidate_set": open_result.get("semantic_candidate_set"),
                    "semantic_selection": open_result.get("semantic_selection"),
                    "authority_effect": open_result.get("authority_effect"),
                    "automatic_execution": open_result.get("automatic_execution"),
                    "artifacts": {
                        "build_graph": str(build_dir / "build_graph.json")
                        if (build_dir / "build_graph.json").is_file()
                        else None,
                        "circuit_netlist": str(build_dir / "circuit_netlist.json")
                        if (build_dir / "circuit_netlist.json").is_file()
                        else None,
                        "kicad_pcb": str(compile_result.kicad_pcb_file) if compile_result else None,
                        "trust_report": str(build_dir / "TRUST_REPORT.json")
                        if (build_dir / "TRUST_REPORT.json").is_file()
                        else None,
                    },
                    **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
                },
                quality=quality,
                request_id=request_id,
                compile_payload=compile_result.to_dict() if compile_result else None,
            )

    catalog_build_id = build_id or str(constraints_map.get("target_build_id") or constraints_map.get("build_id") or "").strip()
    if (
        catalog_build_id
        and splice_plan is not None
        and canvas_nodes is None
        and netlist is None
        and not wire_only
    ):
        result = compile_catalog_build(
            catalog_build_id,
            target,
            export_gerber=export_gerber,
            splice_plan=splice_plan,
            resolved_modules=list(resolved_modules) if resolved_modules else None,
        )
        quality = result.design_quality or {}
        return _finalize_payload(
            {
                "ok": result.ok,
                "mode": "salvage_catalog",
                "out_dir": str(target),
                "build_id": catalog_build_id,
                **result.to_dict(),
                **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
            },
            quality=quality,
            request_id=request_id,
            compile_payload=result.to_dict(),
        )

    # Explicit offline/default compatibility path. Normal model-first compose returns
    # above, including review-only semantic proposals; it does not reach this regex
    # picker-backed scratch path after a model failure.
    scratch = compile_scratch_build(
        out_dir=str(target),
        goal=phrase,
        module_ids=list(module_ids) if module_ids else None,
        resolved_modules=resolved_modules,
        export_gerber=export_gerber,
        constraints=constraints_map,
        salvage_mode=salvage_mode,
    )
    compile_result = scratch.compile_result
    quality = (compile_result.design_quality if compile_result else {}) or {}
    build_dir = target / "build_compilation"
    return _finalize_payload(
        {
            "ok": scratch.ok,
            "mode": "scratch",
            "out_dir": str(target),
            "build_id": scratch.build_id,
            "module_ids": scratch.module_ids,
            "attempts": scratch.attempts,
            "error": scratch.error,
            "compile_result": compile_result.to_dict() if compile_result else None,
            "compile_casefile": scratch.compile_casefile,
            "legacy_semantic_fallback": bool(phrase and not module_ids),
            "artifacts": {
                "build_graph": str(build_dir / "build_graph.json")
                if (build_dir / "build_graph.json").is_file()
                else None,
                "circuit_netlist": str(build_dir / "circuit_netlist.json")
                if (build_dir / "circuit_netlist.json").is_file()
                else None,
                "kicad_pcb": str(compile_result.kicad_pcb_file) if compile_result else None,
                "bom": str(build_dir / "BOM.json") if (build_dir / "BOM.json").is_file() else None,
                "firmware": str(build_dir / "firmware") if (build_dir / "firmware").is_dir() else None,
                "design_quality": str(build_dir / "DESIGN_QUALITY.json")
                if (build_dir / "DESIGN_QUALITY.json").is_file()
                else None,
                "compile_casefile": scratch.compile_casefile,
            },
            **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
        },
        quality=quality,
        request_id=request_id,
        compile_payload=compile_result.to_dict() if compile_result else None,
    )
