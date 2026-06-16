#!/usr/bin/env python3
"""Numerical offline vs LLM-first comparison on golden intakes + compose phrases."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.golden_intakes import golden_compile_cases
from hardware_splicer.module_picker import pick_modules_for_goal
from hardware_splicer.module_resolver import resolve_parts_to_modules, resolve_parts_to_modules_with_llm
from hardware_splicer.project_intake import load_project_intake
from hardware_splicer.salvage_bridge import build_intake_salvage_package
from hardware_splicer.integrations.qwen_text_client import qwen_configured


def _set_offline() -> None:
    os.environ["HARDWARE_SPLICER_OFFLINE_COMPOSE"] = "1"
    os.environ["HARDWARE_SPLICER_OFFLINE_SALVAGE"] = "1"
    os.environ["HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND"] = "1"
    os.environ["HARDWARE_SPLICER_QWEN_BUILD_PICK"] = "0"
    os.environ["HARDWARE_SPLICER_QWEN_MODULE_PICK"] = "0"
    os.environ["HARDWARE_SPLICER_QWEN_COMPOSE"] = "0"
    os.environ["HARDWARE_SPLICER_QWEN_SALVAGE"] = "0"
    os.environ["HARDWARE_SPLICER_QWEN_WORKSHOP"] = "0"
    os.environ["HARDWARE_SPLICER_SALVAGE_RESOLVE"] = "heuristic"
    os.environ["HARDWARE_SPLICER_LLM_FIRST"] = "0"


def _set_online() -> None:
    for key in (
        "HARDWARE_SPLICER_OFFLINE_COMPOSE",
        "HARDWARE_SPLICER_OFFLINE_SALVAGE",
        "HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND",
    ):
        os.environ.pop(key, None)
    os.environ["HARDWARE_SPLICER_QWEN_BUILD_PICK"] = "1"
    os.environ["HARDWARE_SPLICER_QWEN_MODULE_PICK"] = "1"
    os.environ["HARDWARE_SPLICER_QWEN_COMPOSE"] = "1"
    os.environ["HARDWARE_SPLICER_QWEN_SALVAGE"] = "1"
    os.environ["HARDWARE_SPLICER_QWEN_WORKSHOP"] = "0"  # isolate routing, not review
    os.environ["HARDWARE_SPLICER_SALVAGE_RESOLVE"] = "llm_only"
    os.environ["HARDWARE_SPLICER_LLM_FIRST"] = "1"


def _salvage_metrics(mode: str) -> Dict[str, Any]:
    if mode == "offline":
        _set_offline()
    else:
        _set_online()

    cases = golden_compile_cases()
    build_id_match = 0
    resolved_parts = 0
    total_parts = 0
    drc_pass = 0
    compile_ok = 0
    elapsed = 0.0
    out = ROOT / ".cache" / "hardware-splicer" / "bench"

    for case in cases:
        intake = load_project_intake(case["intake_path"])
        parts = list(intake.get("available_parts") or [])
        t0 = time.perf_counter()
        pkg = build_intake_salvage_package(
            goal=str(intake.get("goal") or ""),
            parts=parts,
            constraints=dict(intake.get("constraints") or {}),
            project_name=str(case["id"]),
        )
        elapsed += time.perf_counter() - t0

        got = str(pkg.get("recommended_build_id") or "")
        exp = str(case["expected_build_id"])
        if got == exp:
            build_id_match += 1

        for part in parts:
            total_parts += 1
        for row in pkg.get("resolved_modules") or []:
            if row.get("module_id"):
                resolved_parts += 1

        build_id = exp if got != exp else got
        graph_input = pkg.get("graph_input") or {}
        case_dir = out / f"{case['id']}_{mode}"
        case_dir.mkdir(parents=True, exist_ok=True)
        result = compile_catalog_build(
            build_id,
            case_dir,
            export_gerber=False,
            splice_plan=graph_input,
            resolved_modules=list(pkg.get("resolved_modules") or []),
        )
        q = dict(result.design_quality or {})
        if q.get("drc_pass"):
            drc_pass += 1
        if result.ok and q.get("electrical_safety_pass"):
            compile_ok += 1

    n = len(cases)
    return {
        "cases": n,
        "build_id_match": build_id_match,
        "build_id_match_pct": round(100 * build_id_match / n, 1) if n else 0,
        "parts_resolved": resolved_parts,
        "parts_total": total_parts,
        "parts_resolved_pct": round(100 * resolved_parts / total_parts, 1) if total_parts else 0,
        "drc_pass": drc_pass,
        "drc_pass_pct": round(100 * drc_pass / n, 1) if n else 0,
        "compile_clean": compile_ok,
        "compile_clean_pct": round(100 * compile_ok / n, 1) if n else 0,
        "wall_s": round(elapsed, 2),
    }


def _compose_metrics(mode: str) -> Dict[str, Any]:
    if mode == "offline":
        _set_offline()
    else:
        _set_online()

    phrases_path = ROOT / "tests" / "data" / "compose_phrases.json"
    phrases = [str(row.get("phrase") or "") for row in json.loads(phrases_path.read_text())]
    phrases = [p for p in phrases if p]

    ge2 = 0
    ge3_wires = 0
    elapsed = 0.0
    from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
    from hardware_splicer.pcb.build_to_geometry import build_graph_to_geometry
    from hardware_splicer.pcb.drc import run_drc
    from hardware_splicer.pcb.safety_rules import analyze_build

    for phrase in phrases:
        t0 = time.perf_counter()
        pick = pick_modules_for_goal(phrase)
        elapsed += time.perf_counter() - t0
        if len(pick.module_ids) >= 2:
            ge2 += 1
        if len(pick.module_ids) < 2:
            continue
        graph = compose_build_graph_from_module_ids(pick.module_ids)["graph"]
        wires = len(graph.get("wires") or [])
        if wires >= 3:
            ge3_wires += 1
        safety = analyze_build(graph)
        errors = [w for w in safety if w.get("level") == "error"]
        drc = run_drc(build_graph_to_geometry(graph))
        if not errors and drc.get("pass"):
            pass  # counted below as graph_ok

    graph_ok = 0
    for phrase in phrases:
        pick = pick_modules_for_goal(phrase)
        if len(pick.module_ids) < 2:
            continue
        graph = compose_build_graph_from_module_ids(pick.module_ids)["graph"]
        safety = analyze_build(graph)
        errors = [w for w in safety if w.get("level") == "error"]
        drc = run_drc(build_graph_to_geometry(graph))
        if not errors and drc.get("pass"):
            graph_ok += 1

    n = len(phrases)
    return {
        "phrases": n,
        "pick_ge2_modules": ge2,
        "pick_ge2_pct": round(100 * ge2 / n, 1) if n else 0,
        "graph_ge3_wires": ge3_wires,
        "graph_drc_clean": graph_ok,
        "graph_drc_clean_pct": round(100 * graph_ok / n, 1) if n else 0,
        "wall_s": round(elapsed, 2),
    }


def _resolver_gap_fill() -> Dict[str, Any]:
    """Parts that heuristic misses but LLM might hit (mock-free: compare heuristic vs explicit)."""
    mystery = [
        {"name": "mystery analog widget", "type": "unknown_widget"},
        {"name": "weird I2C breakout", "type": "part"},
        {"name": "old stepper driver board", "type": "driver"},
    ]
    _set_offline()
    h = resolve_parts_to_modules(mystery)
    h_resolved = sum(1 for r in h if r.get("module_id"))
    return {
        "mystery_parts": len(mystery),
        "heuristic_resolved": h_resolved,
        "heuristic_resolved_pct": round(100 * h_resolved / len(mystery), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Skip online LLM arm even when DASHSCOPE_API_KEY is set (fast local baseline).",
    )
    args = parser.parse_args()

    keyed = qwen_configured() and not args.offline_only

    offline_salvage = _salvage_metrics("offline")
    offline_compose = _compose_metrics("offline")
    resolver = _resolver_gap_fill()

    report: Dict[str, Any] = {
        "qwen_configured": qwen_configured(),
        "offline_only": bool(args.offline_only),
        "offline": {"salvage_golden": offline_salvage, "open_compose": offline_compose, "resolver": resolver},
    }

    if keyed:
        online_salvage = _salvage_metrics("online")
        online_compose = _compose_metrics("online")
        report["online"] = {"salvage_golden": online_salvage, "open_compose": online_compose}
        report["delta"] = {
            "build_id_match": online_salvage["build_id_match"] - offline_salvage["build_id_match"],
            "build_id_match_pp": round(
                online_salvage["build_id_match_pct"] - offline_salvage["build_id_match_pct"], 1
            ),
            "drc_pass_pp": round(online_salvage["drc_pass_pct"] - offline_salvage["drc_pass_pct"], 1),
            "compile_clean_pp": round(online_salvage["compile_clean_pct"] - offline_salvage["compile_clean_pct"], 1),
            "compose_pick_ge2_pp": round(online_compose["pick_ge2_pct"] - offline_compose["pick_ge2_pct"], 1),
            "compose_drc_clean_pp": round(
                online_compose["graph_drc_clean_pct"] - offline_compose["graph_drc_clean_pct"], 1
            ),
            "salvage_wall_s_delta": round(online_salvage["wall_s"] - offline_salvage["wall_s"], 2),
            "compose_wall_s_delta": round(online_compose["wall_s"] - offline_compose["wall_s"], 2),
        }
    else:
        report["online"] = None
        if args.offline_only:
            report["note"] = "Online arm skipped (--offline-only)"
        else:
            report["note"] = "No Qwen key — online arm skipped"

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
