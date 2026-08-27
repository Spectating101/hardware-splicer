"""Unified LLM-aware electrical build: goal (+ optional parts) → compile → trust → JARVIS narrative."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .build_compiler import compile_from_netlist
from .design_quality import build_design_quality_gate
from .env_local import load_env_local
from .integrations.qwen_jarvis_narrative import (
    attach_jarvis_narrative_to_trust_report,
    generate_jarvis_narrative,
    jarvis_narrative_enabled,
)
from .integrations.qwen_netlist_compose import compose_netlist_from_goal, semantic_module_proposal_from_goal
from .integrations.qwen_compose_retry import call_qwen_compose_retry, compose_retry_enabled
from .integrations.llm_workshop import (
    run_open_workshop,
    run_salvage_workshop,
    workshop_trace_enabled,
    write_workshop_trace,
)
from .project_intake import splice_and_build_from_intake
from .scratch_pipeline import compile_scratch_build
from .runtime import scratch_path

SCHEMA = "hardware_splicer.jarvis_build.v1"


def apply_engine_defaults() -> None:
    load_env_local()
    os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
    os.environ.setdefault("HARDWARE_SPLICER_JLC_ENRICH", "0")
    os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    os.environ.setdefault("HARDWARE_SPLICER_SIMULATE", "1")
    scratch = scratch_path("tmp")
    os.environ.setdefault("TMPDIR", str(scratch))
    os.environ.setdefault("TEMP", str(scratch))
    os.environ.setdefault("TMP", str(scratch))


def llm_first_enabled() -> bool:
    default = os.environ.get("HARDWARE_SPLICER_QWEN_COMPOSE", "1")
    return os.environ.get("HARDWARE_SPLICER_LLM_FIRST", default).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _enrich_trust(
    build_dir: Path,
    *,
    goal: str,
    compose_mode: str | None,
    design_quality: Mapping[str, Any],
) -> Dict[str, Any]:
    trust_path = build_dir / "TRUST_REPORT.json"
    if not trust_path.is_file():
        return {"ok": False, "error": "missing_trust_report"}
    trust = _load_json(trust_path)
    narrative = generate_jarvis_narrative(
        goal=goal,
        trust_report=trust,
        design_quality=design_quality,
        compose_mode=compose_mode,
    )
    if narrative.get("ok"):
        attach_jarvis_narrative_to_trust_report(str(trust_path), narrative, goal=goal)
    return narrative


def _semantic_review_result(
    proposal: Mapping[str, Any],
    *,
    qwen_usage: Any = None,
    compile_result: Any = None,
    fallback: str | None = None,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "compose_mode": str(proposal.get("compose_mode") or "semantic_module_proposal"),
        "qwen_usage": qwen_usage,
        "module_ids": list(proposal.get("module_ids") or []),
        "compile_result": compile_result,
        "error": proposal.get("error") or "semantic_module_review_required",
        "requires_human_review": True,
        "semantic_intent": proposal.get("semantic_intent"),
        "semantic_candidate_set": proposal.get("semantic_candidate_set"),
        "semantic_selection": proposal.get("semantic_selection"),
        "authority_effect": "none",
        "automatic_execution": False,
        "fallback": fallback,
    }


def _open_compose_llm_first(
    goal: str,
    target: Path,
    *,
    constraints: Mapping[str, Any] | None,
    export_gerber: bool,
    allow_qwen: bool,
) -> Dict[str, Any]:
    """Model-first compose without silently falling back to semantic script brain.

    A valid model netlist may be compiled as the requested software preview. If model
    netlist generation or deterministic compile proof fails, a typed module selection
    may be returned for review, but it is never auto-wired here. Explicit offline mode
    uses ``_open_compose_scratch_only`` instead.
    """

    planned = compose_netlist_from_goal(goal, constraints=constraints, allow_qwen=allow_qwen)
    compose_mode = str(planned.get("compose_mode") or "unknown")
    qwen_usage = planned.get("usage")

    if planned.get("requires_human_review"):
        return _semantic_review_result(planned, qwen_usage=qwen_usage)

    if planned.get("netlist"):
        result = compile_from_netlist(planned["netlist"], target, export_gerber=export_gerber)
        quality = dict(result.design_quality or {})
        gate = build_design_quality_gate(quality)
        if result.ok and gate.get("build_ready"):
            return {
                "ok": True,
                "compose_mode": compose_mode,
                "qwen_usage": qwen_usage,
                "erc": planned.get("erc"),
                "module_ids": planned.get("module_ids"),
                "compile_result": result,
                "requires_human_review": False,
            }
        if (
            compose_mode == "qwen_netlist"
            and allow_qwen
            and compose_retry_enabled()
            and planned.get("netlist")
        ):
            retry = call_qwen_compose_retry(
                goal,
                constraints=constraints,
                prior_netlist=planned.get("netlist"),
                design_quality=quality,
                erc=planned.get("erc"),
            )
            if retry.get("netlist"):
                retry_result = compile_from_netlist(retry["netlist"], target, export_gerber=export_gerber)
                retry_quality = dict(retry_result.design_quality or {})
                retry_gate = build_design_quality_gate(retry_quality)
                if retry_result.ok and retry_gate.get("build_ready"):
                    return {
                        "ok": True,
                        "compose_mode": str(retry.get("compose_mode") or "qwen_compose_retry"),
                        "qwen_usage": retry.get("usage") or qwen_usage,
                        "erc": retry.get("erc"),
                        "module_ids": retry.get("module_ids"),
                        "compile_result": retry_result,
                        "fallback": "qwen_compose_retry",
                        "requires_human_review": False,
                    }

        # Do not convert a failed model design into a hidden regex-selected build. The
        # failed compile result is preserved, and a separate semantic proposal may be
        # reviewed before another execution attempt.
        if allow_qwen:
            proposal = semantic_module_proposal_from_goal(goal, constraints=constraints)
            if proposal.get("requires_human_review"):
                return _semantic_review_result(
                    proposal,
                    qwen_usage=qwen_usage,
                    compile_result=result,
                    fallback="semantic_module_proposal_after_qwen_compile_failure",
                )
        return {
            "ok": False,
            "compose_mode": compose_mode,
            "qwen_usage": qwen_usage,
            "module_ids": planned.get("module_ids") or [],
            "compile_result": result,
            "error": "llm_netlist_compile_failed",
            "requires_human_review": True,
            "authority_effect": "none",
            "automatic_execution": False,
        }

    # LLM-first means exactly that. If no model-backed netlist or review proposal can be
    # produced, stay blocked rather than quietly switching to the offline regex picker.
    return {
        "ok": False,
        "compose_mode": compose_mode,
        "qwen_usage": qwen_usage,
        "module_ids": list(planned.get("module_ids") or []),
        "compile_result": None,
        "error": planned.get("error") or "llm_compose_unresolved",
        "requires_human_review": True,
        "authority_effect": "none",
        "automatic_execution": False,
    }


def jarvis_build(
    goal: str,
    *,
    parts: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
    project_name: str | None = None,
    out_dir: str | Path | None = None,
    export_gerber: bool = False,
    allow_qwen: bool = True,
) -> Dict[str, Any]:
    """Primary electrical path: NL goal (+ optional salvage parts) → compile → trust → JARVIS narrative."""
    load_env_local()
    apply_engine_defaults()
    target = Path(out_dir) if out_dir else Path(os.environ.get("TMPDIR", "/tmp")) / "hardware_splicer_jarvis"
    target.mkdir(parents=True, exist_ok=True)
    constraints_map = dict(constraints or {})
    requires_human_review = False
    semantic_intent = None
    semantic_candidate_set = None
    semantic_selection = None
    open_error = None

    if parts:
        intake = {
            "goal": goal,
            "available_parts": list(parts),
            "constraints": constraints_map,
            "salvage_mode": True,
            "project_name": project_name or "jarvis_salvage",
        }
        splice = splice_and_build_from_intake(intake, out_dir=target, export_gerber=export_gerber)
        build_dir = target / "build_compilation"
        quality = _load_json(build_dir / "DESIGN_QUALITY.json")
        gate = build_design_quality_gate(quality)
        compose_mode = "salvage_intake"
        ok = bool(splice.get("ok") and gate.get("build_ready"))
        module_ids = list((splice.get("salvage_package") or {}).get("compose_module_ids") or [])
        build_id = splice.get("build_id")
        compile_result = None
    else:
        if llm_first_enabled() and allow_qwen:
            open_result = _open_compose_llm_first(
                goal,
                target,
                constraints=constraints_map,
                export_gerber=export_gerber,
                allow_qwen=allow_qwen,
            )
        else:
            open_result = _open_compose_scratch_only(
                goal,
                target,
                constraints_map,
                export_gerber,
                allow_qwen=allow_qwen,
            )
        compile_result = open_result.get("compile_result")
        quality = dict(compile_result.design_quality if compile_result else {})
        gate = build_design_quality_gate(quality)
        ok = bool(open_result.get("ok") and gate.get("build_ready"))
        compose_mode = str(open_result.get("compose_mode") or "unknown")
        module_ids = list(open_result.get("module_ids") or [])
        build_id = getattr(compile_result, "build_id", None) if compile_result else None
        requires_human_review = bool(open_result.get("requires_human_review"))
        semantic_intent = open_result.get("semantic_intent")
        semantic_candidate_set = open_result.get("semantic_candidate_set")
        semantic_selection = open_result.get("semantic_selection")
        open_error = open_result.get("error")
        splice = None

    build_dir = target / "build_compilation"
    narrative = _enrich_trust(
        build_dir,
        goal=goal,
        compose_mode=compose_mode,
        design_quality=quality,
    )

    trust = _load_json(build_dir / "TRUST_REPORT.json")
    simulation = _load_json(build_dir / "ELECTRICAL_SIMULATION.json")

    workshop_trace = None
    if workshop_trace_enabled():
        if parts:
            workshop_trace = run_salvage_workshop(
                goal=goal,
                parts=list(parts),
                constraints=constraints_map,
                compile_probe=False,
            )
        else:
            workshop_trace = run_open_workshop(goal=goal, constraints=constraints_map)
        write_workshop_trace(workshop_trace, target)

    return {
        "schema_version": SCHEMA,
        "ok": ok,
        "goal": goal,
        "mode": "salvage" if parts else "open",
        "compose_mode": compose_mode,
        "build_id": build_id,
        "module_ids": module_ids,
        "out_dir": str(target),
        "design_quality": quality,
        "design_quality_gate": gate,
        "trust_report": trust,
        "electrical_simulation": simulation,
        "jarvis": narrative,
        "jarvis_enabled": jarvis_narrative_enabled(),
        "llm_first": llm_first_enabled() and allow_qwen and not parts,
        "requires_human_review": requires_human_review,
        "semantic_intent": semantic_intent,
        "semantic_candidate_set": semantic_candidate_set,
        "semantic_selection": semantic_selection,
        "authority_effect": "none" if requires_human_review else None,
        "automatic_execution": False if requires_human_review else None,
        "artifacts": {
            "trust_report": str(build_dir / "TRUST_REPORT.json") if (build_dir / "TRUST_REPORT.json").is_file() else None,
            "trust_report_md": str(build_dir / "TRUST_REPORT.md") if (build_dir / "TRUST_REPORT.md").is_file() else None,
            "kicad_pcb": str(compile_result.kicad_pcb_file) if compile_result and compile_result.kicad_pcb_file else (
                str(build_dir / "main_ctrl_build.kicad_pcb") if (build_dir / "main_ctrl_build.kicad_pcb").is_file() else None
            ),
            "bom": str(build_dir / "BOM.json") if (build_dir / "BOM.json").is_file() else None,
            "firmware_dir": str(build_dir / "firmware") if (build_dir / "firmware").is_dir() else None,
        },
        "salvage_package": (splice or {}).get("salvage_package"),
        "workshop_trace": workshop_trace,
        "error": None if ok else (open_error or quality.get("drc_violations") or trust.get("blockers")),
    }


def _open_compose_scratch_only(
    goal: str,
    target: Path,
    constraints: Mapping[str, Any],
    export_gerber: bool,
    *,
    allow_qwen: bool = False,
) -> Dict[str, Any]:
    planned = compose_netlist_from_goal(goal, constraints=constraints, allow_qwen=allow_qwen)
    if planned.get("netlist"):
        result = compile_from_netlist(planned["netlist"], target, export_gerber=export_gerber)
        quality = dict(result.design_quality or {})
        gate = build_design_quality_gate(quality)
        if result.ok and gate.get("build_ready"):
            return {
                "ok": True,
                "compose_mode": planned.get("compose_mode"),
                "qwen_usage": planned.get("usage"),
                "module_ids": planned.get("module_ids") or [],
                "compile_result": result,
                "requires_human_review": False,
            }

    scratch = compile_scratch_build(
        out_dir=str(target),
        goal=goal,
        export_gerber=export_gerber,
        constraints=constraints,
    )
    compile_result = scratch.compile_result
    quality = dict(compile_result.design_quality if compile_result else {})
    gate = build_design_quality_gate(quality)
    return {
        "ok": bool(scratch.ok and gate.get("build_ready")),
        "compose_mode": "scratch_pipeline",
        "module_ids": scratch.module_ids,
        "attempts": scratch.attempts,
        "compile_result": compile_result,
        "error": scratch.error,
        "requires_human_review": False,
    }
