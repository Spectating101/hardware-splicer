#!/usr/bin/env python3
"""Step-by-step LLM workshop probe — see where Qwen helps vs heuristics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.env_local import load_env_local
from hardware_splicer.integrations.llm_workshop import (
    run_open_workshop,
    run_salvage_workshop,
    write_workshop_trace,
)
from hardware_splicer.jarvis_build import apply_engine_defaults
from hardware_splicer.project_intake import load_project_intake


def main() -> int:
    load_env_local()
    apply_engine_defaults()

    parser = argparse.ArgumentParser(description="Probe LLM workshop steps (heuristic vs Qwen).")
    parser.add_argument("--goal", help="Open-mode NL goal")
    parser.add_argument("--intake", help="Path to intake JSON (salvage mode)")
    parser.add_argument("--out", default="/tmp/llm_workshop_probe", help="Output directory")
    parser.add_argument(
        "--workshop-review",
        action="store_true",
        help="Enable HARDWARE_SPLICER_QWEN_WORKSHOP=1 for salvage review step",
    )
    parser.add_argument("--compile-probe", action="store_true", help="Run DRC compile probe (salvage)")
    parser.add_argument("--json", action="store_true", help="Print trace JSON to stdout")
    args = parser.parse_args()

    if args.workshop_review:
        import os

        os.environ["HARDWARE_SPLICER_QWEN_WORKSHOP"] = "1"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.intake:
        intake = load_project_intake(args.intake)
        trace = run_salvage_workshop(
            goal=str(intake.get("goal") or ""),
            parts=list(intake.get("available_parts") or []),
            constraints=dict(intake.get("constraints") or {}),
            compile_probe=args.compile_probe,
            out_dir=out if args.compile_probe else None,
        )
    elif args.goal:
        trace = run_open_workshop(goal=args.goal, constraints={})
    else:
        parser.error("Provide --goal or --intake")

    trace_path = write_workshop_trace(trace, out)
    if args.json:
        print(json.dumps(trace, indent=2))
    else:
        print(f"mode={trace.get('mode')}")
        print(f"qwen_configured={trace.get('qwen_configured')}")
        print(f"recommendation={trace.get('recommendation')}")
        for step in trace.get("steps") or []:
            tag = "Qwen" if step.get("llm_used") else "det"
            print(f"  [{tag}] {step.get('id')}: {step.get('summary')}")
        print(f"trace={trace_path}")
        print(f"markdown={out / 'LLM_WORKSHOP_TRACE.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
