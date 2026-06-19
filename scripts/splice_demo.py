#!/usr/bin/env python3
"""Canonical splice demo: donor PCB dissection → splice plan → carrier board compile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.splice_manifest import (
    evaluate_splice_case,
    get_splice_case,
    load_splice_manifest,
    run_splice_case,
)
from hardware_splicer.project_intake import load_project_intake


def _block_lines(blocks: List[Dict[str, Any]], limit: int = 8) -> List[str]:
    lines: List[str] = []
    for block in blocks[:limit]:
        if not isinstance(block, dict):
            continue
        extractability = block.get("extractability") or {}
        extraction_class = extractability.get("class") or block.get("extraction_action") or "unknown"
        caps = ", ".join(block.get("capabilities") or [])
        lines.append(
            f"- **{block.get('name') or block.get('block_id')}** "
            f"(`{extraction_class}`) — {caps or 'no capabilities listed'}"
        )
    return lines


def _write_story(
    out_dir: Path,
    *,
    intake: Dict[str, Any],
    metrics: Dict[str, Any],
    evaluation: Dict[str, Any],
    case: Dict[str, Any] | None,
) -> Path:
    splice_plan = metrics.get("splice_plan") or {}
    reusable_blocks = list(splice_plan.get("reusable_blocks") or [])
    circuit_blocks = [row for row in reusable_blocks if row.get("source") == "circuit_functional_salvage"]
    functional_reuse = splice_plan.get("functional_reuse_plan") or {}
    wiring_steps = list(splice_plan.get("wiring_steps") or [])[:6]
    measurements = list(splice_plan.get("required_measurements") or [])[:6]

    story = [
        "# Splice demo story",
        "",
        "## Product thesis",
        "",
        "Hardware-Splicer **dissects donor hardware**, identifies reusable functional blocks,",
        "plans safe splice contracts, and compiles a **carrier board** that mates with what you kept.",
        "",
    ]
    if case:
        story.extend(
            [
                f"## Case: `{case.get('case_id')}`",
                "",
                str(case.get("product_story") or case.get("title") or ""),
                "",
            ]
        )

    story.extend(
        [
            "## This run",
            "",
            f"- **Goal:** {intake.get('goal')}",
            f"- **Target build:** `{metrics.get('build_id')}`",
            f"- **Salvage verdict:** `{metrics.get('verdict')}`",
            f"- **Graph mode:** `{metrics.get('graph_mode')}`",
            f"- **DRC pass:** `{metrics.get('drc_pass')}`",
            f"- **Manifest check:** `{'PASS' if evaluation.get('passed') else 'FAIL'}`",
            "",
            "## Donor blocks (functional dissection)",
            "",
        ]
    )
    if circuit_blocks:
        story.extend(_block_lines(circuit_blocks))
        story.extend(
            [
                "",
                f"Circuit-backed blocks: **{len(circuit_blocks)}** "
                f"(readiness: `{metrics.get('splice_readiness') or functional_reuse.get('splice_readiness', 'n/a')}`)",
                f"Extractability classes: `{', '.join(metrics.get('extractability_classes') or [])}`",
            ]
        )
    else:
        story.extend(_block_lines(reusable_blocks) or ["- (no reusable blocks recorded)"])

    story.extend(["", "## Splice plan highlights", ""])
    if measurements:
        story.append("**Measure before you cut or power:**")
        story.extend(f"- {row}" for row in measurements)
        story.append("")
    if wiring_steps:
        story.append("**Wiring / integration steps:**")
        story.extend(f"- {row}" for row in wiring_steps)
        story.append("")

    do_not = list(splice_plan.get("do_not_connect_until") or [])[:5]
    if do_not:
        story.append("**Do not connect until:**")
        story.extend(f"- {row}" for row in do_not)
        story.append("")

    if evaluation.get("failures"):
        story.extend(["## Manifest failures", ""])
        story.extend(f"- {row}" for row in evaluation["failures"])
        story.append("")

    story.extend(
        [
            "## Artifacts",
            "",
            "- `SPLICE_PLAN.json` — full splice + salvage package",
            "- `build_compilation/main_ctrl_build.kicad_pcb` — carrier board (not the donor PCB)",
            "- `BRINGUP_CARD.md` — bench bring-up checklist",
            "- `SPLICE_DEMO_RESULT.json` — machine-readable pass/fail metrics",
            "",
            "## What this proves",
            "",
            "1. Donor PCB → **functional blocks** with extractability classes",
            "2. Splice contracts → **graph_input** → KiCad compile",
            "3. Honest gate — KiCad DRC truth on the carrier board",
            "",
            "See `docs/SPLICE_PRODUCT.md` for maturity tiers and roadmap.",
            "",
        ]
    )

    path = out_dir / "SPLICE_DEMO_STORY.md"
    path.write_text("\n".join(story), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical splice-and-build demo")
    parser.add_argument("--manifest", type=Path, default=ROOT / "examples" / "splice" / "manifest.json")
    parser.add_argument("--case", default="robot_drive_from_rc_toy", help="case_id from manifest (default: robot)")
    parser.add_argument("--intake", type=Path, default=None, help="Override intake path (legacy single-demo mode)")
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_splice_demo"))
    parser.add_argument("--export-gerber", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    case: Dict[str, Any] | None = None
    if args.intake is not None:
        intake = load_project_intake(args.intake)
        args.out.mkdir(parents=True, exist_ok=True)
        from hardware_splicer.project_intake import splice_and_build_from_intake

        result = splice_and_build_from_intake(intake, out_dir=args.out.resolve(), export_gerber=bool(args.export_gerber))
        salvage = result.get("salvage_package") or {}
        splice_plan = salvage.get("splice_plan") or {}
        circuit_blocks = [row for row in (splice_plan.get("reusable_blocks") or []) if row.get("source") == "circuit_functional_salvage"]
        quality = (result.get("build_compilation") or {}).get("design_quality") or {}
        metrics = {
            "build_id": result.get("build_id"),
            "verdict": salvage.get("verdict"),
            "graph_mode": salvage.get("graph_mode"),
            "drc_pass": quality.get("drc_pass"),
            "circuit_backed_block_count": len(circuit_blocks),
            "extractability_classes": [],
            "splice_plan": splice_plan,
            "splice_readiness": (splice_plan.get("functional_reuse_plan") or {}).get("splice_readiness"),
            "artifacts": result.get("artifacts") or {},
        }
        evaluation = {"passed": bool(result.get("ok")), "failures": [] if result.get("ok") else ["result_ok=false"]}
    else:
        manifest = load_splice_manifest(args.manifest)
        case = get_splice_case(manifest, args.case)
        args.out.mkdir(parents=True, exist_ok=True)
        metrics = run_splice_case(case, out_dir=args.out.resolve(), export_gerber=bool(args.export_gerber))
        evaluation = evaluate_splice_case(metrics, case)
        intake = load_project_intake(REPO_ROOT / str(case["intake"]))

    result_path = args.out.resolve() / "SPLICE_DEMO_RESULT.json"
    result_path.write_text(
        json.dumps(
            {
                "schema_version": "hardware_splicer.splice_demo_result.v1",
                "case_id": (case or {}).get("case_id"),
                "evaluation": evaluation,
                "metrics": {k: metrics[k] for k in metrics if k not in {"raw_result", "splice_plan"}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    story_path = _write_story(args.out.resolve(), intake=intake, metrics=metrics, evaluation=evaluation, case=case)

    if args.json:
        print(
            json.dumps(
                {
                    "evaluation": evaluation,
                    "metrics": metrics,
                    "splice_demo_story": str(story_path),
                    "splice_demo_result": str(result_path),
                },
                indent=2,
                default=str,
            )
        )
        return 0 if evaluation.get("passed") else 1

    print("Hardware-Splicer — splice demo")
    if case:
        print(f"  case: {case.get('case_id')}")
    print(f"  goal: {intake.get('goal')}")
    print(f"  build_id: {metrics.get('build_id')}")
    print(f"  verdict: {metrics.get('verdict')}")
    print(f"  circuit_backed_blocks: {metrics.get('circuit_backed_block_count')}")
    print(f"  drc_pass: {metrics.get('drc_pass')}")
    print(f"  manifest: {'PASS' if evaluation.get('passed') else 'FAIL'}")
    print(f"  out_dir: {args.out.resolve()}")
    print(f"  story: {story_path}")
    print(f"  result: {result_path}")
    if evaluation.get("failures"):
        for failure in evaluation["failures"]:
            print(f"  failure: {failure}")

    return 0 if evaluation.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
