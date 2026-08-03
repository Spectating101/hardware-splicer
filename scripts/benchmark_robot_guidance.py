#!/usr/bin/env python3
"""Run robot build/modification guidance scenarios through Hardware Splicer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer.robot_guidance_benchmark import (  # noqa: E402
    evaluate_robot_guidance_suite,
    load_robot_guidance_scenario,
)

DEFAULT_CASE_DIR = ROOT / "examples" / "robotics_guidance"


def _markdown(report: dict) -> str:
    lines = [
        "# Robot Guidance Benchmark",
        "",
        "This is a planning and guidance coverage report, not a safety or physical-validation certificate.",
        "",
        "| Scenario | Mode | Archetype | Score | Verdict | Primary gaps |",
        "|---|---|---|---:|---|---|",
    ]
    for row in report.get("rows") or []:
        gaps = ", ".join((row.get("gaps") or [])[:5]) or "none"
        lines.append(
            "| {scenario} | {mode} | {expected} → {detected} | {score:.1f} | {verdict} | {gaps} |".format(
                scenario=row.get("scenario_id"),
                mode=row.get("mode"),
                expected=row.get("expected_archetype"),
                detected=row.get("detected_archetype"),
                score=float(row.get("guidance_score") or 0.0),
                verdict=row.get("verdict"),
                gaps=gaps.replace("|", "\\|"),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `guided_build_ready`: the structured plan covers all benchmark obligations; physical evidence is still required.",
            "- `useful_with_expert_fill`: substantial plan, but an experienced builder must fill important engineering gaps.",
            "- `planning_assistant_only`: useful for intake, architecture, and gates; not a complete build guide.",
            "- `reference_triage_only`: primarily organizes sources and requirements.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--out", type=Path, default=ROOT / ".artifacts" / "robot_guidance")
    args = parser.parse_args()

    cases = [load_robot_guidance_scenario(path) for path in sorted(args.case_dir.glob("*.json"))]
    if not cases:
        raise SystemExit(f"no robot guidance scenarios found in {args.case_dir}")

    report = evaluate_robot_guidance_suite(cases)
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "ROBOT_GUIDANCE_BENCHMARK.json"
    md_path = args.out / "ROBOT_GUIDANCE_BENCHMARK.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
