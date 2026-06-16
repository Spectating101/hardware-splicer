"""Step-by-step LLM workshop trace — compare heuristic vs Qwen at each stage."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..build_compiler import compile_catalog_build
from ..design_quality import build_design_quality_gate
from ..module_resolver import (
    fill_salvage_gaps,
    resolve_parts_to_modules,
    resolve_parts_to_modules_with_llm,
)
from ..module_picker import pick_modules_for_goal
from ..salvage_bridge import build_intake_salvage_package
from .qwen_compose_retry import call_qwen_compose_retry, compose_retry_enabled
from .qwen_netlist_compose import call_qwen_netlist_compose, compose_netlist_from_goal
from .qwen_text_client import qwen_configured
from .qwen_workshop_review import (
    apply_workshop_review,
    call_qwen_workshop_review,
    workshop_review_enabled,
)

SCHEMA_VERSION = "hardware_splicer.llm_workshop.v1"


@dataclass
class WorkshopStep:
    id: str
    label: str
    llm_used: bool
    ok: bool
    summary: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "llm_used": self.llm_used,
            "ok": self.ok,
            "summary": self.summary,
            "detail": self.detail,
        }


def workshop_trace_enabled() -> bool:
    return os.environ.get("HARDWARE_SPLICER_LLM_WORKSHOP", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _module_id_set(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    return sorted(
        {
            str(row.get("module_id") or "").strip()
            for row in rows
            if str(row.get("module_id") or "").strip()
        }
    )


def run_salvage_workshop(
    *,
    goal: str,
    parts: List[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
    compile_probe: bool = False,
    out_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Walk salvage intake stages; record where Qwen changes outcomes vs heuristics."""
    steps: List[WorkshopStep] = []
    constraints_map = dict(constraints or {})

    heuristic = resolve_parts_to_modules(parts)
    steps.append(
        WorkshopStep(
            id="heuristic_resolve",
            label="Regex fallback resolve (offline)",
            llm_used=False,
            ok=bool(_module_id_set(heuristic)),
            summary=f"{len(_module_id_set(heuristic))} module(s) resolved, "
            f"{sum(1 for r in heuristic if not r.get('module_id'))} still unresolved",
            detail={"module_ids": _module_id_set(heuristic), "rows": heuristic},
        )
    )

    with_llm, salvage_meta = resolve_parts_to_modules_with_llm(parts, goal=goal)
    resolve_mode = str(salvage_meta.get("resolve_mode") or "unknown")
    qwen_delta = sorted(set(_module_id_set(with_llm)) - set(_module_id_set(heuristic)))
    steps.append(
        WorkshopStep(
            id="qwen_salvage_resolve",
            label=f"Qwen intake map ({resolve_mode})",
            llm_used=bool(salvage_meta.get("qwen", {}).get("used")),
            ok=bool(_module_id_set(with_llm)),
            summary=(
                (str(salvage_meta.get("qwen", {}).get("reasoning") or "")[:180])
                or (
                    f"Qwen delta: {', '.join(qwen_delta) or 'none'}"
                    if salvage_meta.get("qwen", {}).get("used")
                    else str(salvage_meta.get("qwen", {}).get("reason") or "skipped")
                )
            ),
            detail={"meta": salvage_meta, "module_ids": _module_id_set(with_llm)},
        )
    )

    resolved = list(with_llm)
    gap = fill_salvage_gaps(resolved, parts=parts)
    gap_added = sorted(set(_module_id_set(gap)) - set(_module_id_set(resolved)))
    steps.append(
        WorkshopStep(
            id="deterministic_gap_fill",
            label="Deterministic gap-fill (driver, etc.)",
            llm_used=False,
            ok=True,
            summary=f"Added: {', '.join(gap_added) or 'none'}",
            detail={"module_ids": _module_id_set(gap)},
        )
    )
    resolved = gap

    baseline_pkg = build_intake_salvage_package(
        goal=goal,
        parts=parts,
        constraints=constraints_map,
    )
    steps.append(
        WorkshopStep(
            id="salvage_package_baseline",
            label="Salvage package (current pipeline)",
            llm_used=bool((baseline_pkg.get("salvage_resolution") or {}).get("qwen", {}).get("used")),
            ok=bool(baseline_pkg.get("recommended_build_id")),
            summary=(
                f"build={baseline_pkg.get('recommended_build_id')} "
                f"modules={len(baseline_pkg.get('compose_module_ids') or []) or len(_module_id_set(baseline_pkg.get('resolved_modules') or []))}"
            ),
            detail={
                "recommended_build_id": baseline_pkg.get("recommended_build_id"),
                "power_topology": baseline_pkg.get("power_topology"),
                "module_ids": _module_id_set(baseline_pkg.get("resolved_modules") or []),
                "graph_mode": baseline_pkg.get("graph_mode"),
            },
        )
    )

    review: Dict[str, Any] = {"ok": False, "skipped": True}
    reviewed_modules = list(resolved)
    if workshop_review_enabled():
        review = call_qwen_workshop_review(
            goal=goal,
            parts=parts,
            resolved_modules=resolved,
            constraints=constraints_map,
            recommended_build_id=str(baseline_pkg.get("recommended_build_id") or ""),
        )
        if review.get("ok"):
            reviewed_modules = apply_workshop_review(resolved, review)
        review_added = sorted(set(_module_id_set(reviewed_modules)) - set(_module_id_set(resolved)))
        steps.append(
            WorkshopStep(
                id="qwen_workshop_review",
                label="Qwen workshop review (optional)",
                llm_used=True,
                ok=bool(review.get("ok")),
                summary=(review.get("reasoning") or "")[:240]
                + (f" | added: {', '.join(review_added)}" if review_added else ""),
                detail={
                    "review": {k: review.get(k) for k in review if k != "usage"},
                    "module_ids_after": _module_id_set(reviewed_modules),
                },
            )
        )
    else:
        steps.append(
            WorkshopStep(
                id="qwen_workshop_review",
                label="Qwen workshop review (optional)",
                llm_used=False,
                ok=True,
                summary="Skipped (set QWEN_WORKSHOP=0 to disable default-on review)",
                detail={},
            )
        )

    compile_step: Optional[WorkshopStep] = None
    if compile_probe and out_dir:
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        graph_input = baseline_pkg.get("graph_input") or {}
        build_id = str(baseline_pkg.get("recommended_build_id") or "")
        if build_id:
            result = compile_catalog_build(
                build_id,
                target,
                export_gerber=False,
                splice_plan=graph_input,
                resolved_modules=list(baseline_pkg.get("resolved_modules") or []),
            )
            gate = build_design_quality_gate(dict(result.design_quality or {}))
            compile_step = WorkshopStep(
                id="compile_probe",
                label="Compile + DRC probe",
                llm_used=False,
                ok=bool(result.ok and gate.get("build_ready")),
                summary=f"drc_pass={gate.get('build_ready')} nodes={len(json.loads(Path(result.build_graph_file).read_text()).get('nodes') or []) if result.build_graph_file else 0}",
                detail={
                    "drc_pass": (result.design_quality or {}).get("drc_pass"),
                    "kicad_drc_errors": (result.design_quality or {}).get("kicad_drc_errors"),
                },
            )
            steps.append(compile_step)

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "salvage",
        "goal": goal,
        "qwen_configured": qwen_configured(),
        "workshop_review_enabled": workshop_review_enabled(),
        "steps": [s.to_dict() for s in steps],
        "recommendation": _salvage_recommendation(steps),
    }


def run_open_workshop(
    *,
    goal: str,
    constraints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Walk open-compose stages: picker vs Qwen vs retry."""
    steps: List[WorkshopStep] = []
    constraints_map = dict(constraints or {})

    pick = pick_modules_for_goal(goal)
    steps.append(
        WorkshopStep(
            id="module_picker",
            label="Deterministic module picker",
            llm_used=False,
            ok=len(pick.module_ids) >= 2,
            summary=f"{len(pick.module_ids)} modules: {', '.join(pick.module_ids[:6])}",
            detail={"module_ids": list(pick.module_ids), "hints": list(pick.hints)},
        )
    )

    det = compose_netlist_from_goal(goal, constraints=constraints_map, allow_qwen=False)
    steps.append(
        WorkshopStep(
            id="deterministic_compose",
            label="Compose without Qwen",
            llm_used=False,
            ok=bool(det.get("ok")),
            summary=str(det.get("compose_mode") or det.get("error") or "unknown"),
            detail={
                "compose_mode": det.get("compose_mode"),
                "module_ids": det.get("module_ids"),
                "erc_pass": (det.get("erc") or {}).get("pass"),
            },
        )
    )

    qwen = call_qwen_netlist_compose(goal, constraints=constraints_map)
    steps.append(
        WorkshopStep(
            id="qwen_compose",
            label="Qwen netlist compose",
            llm_used=bool(qwen.get("ok")),
            ok=bool(qwen.get("ok")),
            summary=(
                f"model={qwen.get('model')} erc_pass={(qwen.get('erc') or {}).get('pass')}"
                if qwen.get("ok")
                else str(qwen.get("error") or "failed")
            ),
            detail={
                "model": qwen.get("model"),
                "module_ids": qwen.get("module_ids"),
                "erc": qwen.get("erc"),
            },
        )
    )

    if qwen.get("netlist") and compose_retry_enabled() and not qwen.get("ok"):
        retry = call_qwen_compose_retry(
            goal,
            constraints=constraints_map,
            prior_netlist=qwen.get("netlist"),
            design_quality={"safety_error_messages": ["probe: simulate DRC fail path"]},
            erc=qwen.get("erc"),
        )
        steps.append(
            WorkshopStep(
                id="qwen_compose_retry_probe",
                label="Qwen compose retry (dry probe)",
                llm_used=bool(retry.get("ok")),
                ok=bool(retry.get("ok")),
                summary=str(retry.get("compose_mode") or retry.get("error") or retry.get("reason") or "skipped"),
                detail={"model": retry.get("model"), "erc_pass": (retry.get("erc") or {}).get("pass")},
            )
        )
    else:
        steps.append(
            WorkshopStep(
                id="qwen_compose_retry_probe",
                label="Qwen compose retry",
                llm_used=False,
                ok=True,
                summary="Skipped (no prior netlist or retry disabled)",
                detail={},
            )
        )

    improved = bool(qwen.get("ok")) and not bool(det.get("ok"))
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "open",
        "goal": goal,
        "qwen_configured": qwen_configured(),
        "steps": [s.to_dict() for s in steps],
        "recommendation": (
            "Qwen compose passed ERC where deterministic path did not — worth LLM-first for this goal."
            if improved
            else "Try compile probe; use Qwen for narrative and salvage gaps first."
        ),
    }


def _salvage_recommendation(steps: List[WorkshopStep]) -> str:
    by_id = {s.id: s for s in steps}
    salvage = by_id.get("qwen_salvage_resolve")
    review = by_id.get("qwen_workshop_review")
    if salvage and salvage.detail.get("meta", {}).get("qwen", {}).get("used"):
        return "Qwen intake mapping ran (llm_first) — check reasoning in salvage_resolution."
    if salvage and salvage.detail.get("meta", {}).get("resolve_mode") == "heuristic":
        return "Offline heuristic mode — set SALVAGE_RESOLVE=llm_first when Qwen is keyed for better junk-drawer reads."
    if review and review.llm_used and (review.detail.get("review", {}).get("add_modules") or review.summary):
        return "Workshop review suggested changes — HARDWARE_SPLICER_QWEN_WORKSHOP=1 applies them in salvage builds."
    if by_id.get("heuristic_resolve") and by_id["heuristic_resolve"].ok:
        return "Heuristics sufficient for this intake — save Qwen quota for narrative and edge cases."
    return "Unresolved parts remain — run with Qwen salvage or workshop review enabled."


def write_workshop_trace(payload: Mapping[str, Any], out_dir: str | Path) -> Path:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / "LLM_WORKSHOP_TRACE.json"
    path.write_text(json.dumps(dict(payload), indent=2), encoding="utf-8")
    md = target / "LLM_WORKSHOP_TRACE.md"
    lines = [
        "# LLM workshop trace",
        "",
        f"**Mode:** {payload.get('mode')}",
        f"**Goal:** {payload.get('goal')}",
        "",
        f"**Recommendation:** {payload.get('recommendation')}",
        "",
        "## Steps",
        "",
    ]
    for step in payload.get("steps") or []:
        llm = "Qwen" if step.get("llm_used") else "deterministic"
        lines.append(f"### {step.get('id')} ({llm})")
        lines.append(f"- **OK:** {step.get('ok')}")
        lines.append(f"- {step.get('summary')}")
        lines.append("")
    md.write_text("\n".join(lines), encoding="utf-8")
    return path
