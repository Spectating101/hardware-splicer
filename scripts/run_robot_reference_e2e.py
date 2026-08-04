#!/usr/bin/env python3
"""Run the source-rich rover reference case through the full guided planner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_DIR = (ROOT / "scripts").resolve()
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() != SCRIPTS_DIR]

from hardware_splicer.robot_reference_e2e import (  # noqa: E402
    load_json,
    run_robot_reference_e2e,
)

DEFAULT_CATALOG = ROOT / "examples" / "robot_reference_corpus" / "robot_reference_catalog.json"
DEFAULT_CASE = ROOT / "examples" / "robot_reference_e2e" / "reference_rich_indoor_inspection_rover.json"
DEFAULT_OUT = ROOT / ".artifacts" / "robot_reference_e2e"


def _markdown(report: dict) -> str:
    summary = report.get("plan_summary") or {}
    selected = report.get("selected_evidence") or {}
    lines = [
        "# Robot Reference End-to-End Report",
        "",
        f"**Scenario:** `{report.get('scenario_id')}`",
        f"**Result:** `{'PASS' if report.get('passed') else 'FAIL'}`",
        "",
        "This report validates planning and evidence governance. It is not a fabrication, power-on, motion, or release certificate.",
        "",
        "## Corpus",
        "",
        f"- Families: {report.get('catalog', {}).get('family_count')}",
        f"- Sources: {report.get('catalog', {}).get('source_count')}",
        f"- Selected sources: {selected.get('source_count')}",
        f"- Selected video/observed sources: {selected.get('video_source_count')}",
        f"- Source types: {', '.join(selected.get('source_types') or [])}",
        "",
        "## Plan delivery",
        "",
        f"- Native genre: {summary.get('native_robot_genre')}",
        f"- Source graph: {summary.get('source_graph_source_count')} sources / {summary.get('source_graph_claim_count')} claims",
        f"- Topology: {summary.get('topology_link_count')} links / {summary.get('topology_joint_count')} joints / {summary.get('topology_actuator_count')} actuators",
        f"- Analysis findings: {summary.get('analysis_finding_count')} ({summary.get('analysis_blocking_count')} blocking)",
        f"- Manufacturing closure: {summary.get('manufacturing_closure_status')} ({summary.get('manufacturing_blocker_count')} blockers)",
        f"- Execution previews: {summary.get('execution_check_count')} checks / {summary.get('execution_unresolved_count')} unresolved",
        f"- Operator guide: {summary.get('operator_guide_step_count')} steps",
        f"- Engineering status: {summary.get('engineering_status')} / phase `{summary.get('engineering_phase')}`",
        f"- Next action: `{summary.get('next_action_id')}`",
        "",
        "## Acceptance checks",
        "",
        "| Check | Result | Observed | Expected |",
        "|---|---|---|---|",
    ]
    for row in report.get("checks") or []:
        observed = json.dumps(row.get("observed"), sort_keys=True).replace("|", "\\|")
        expected = json.dumps(row.get("expected"), sort_keys=True).replace("|", "\\|")
        lines.append(
            f"| {row.get('name')} | {'PASS' if row.get('passed') else 'FAIL'} | {observed} | {expected} |"
        )
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {value}" for value in report.get("limitations") or [])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = run_robot_reference_e2e(load_json(args.catalog), load_json(args.case))
    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "ROBOT_REFERENCE_E2E.json"
    md_path = args.out / "ROBOT_REFERENCE_E2E.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("scenario_id", "passed", "catalog", "selected_evidence", "plan_summary", "physical_authority")}, indent=2))
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    if args.strict and not report.get("passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
