#!/usr/bin/env python3
"""Evaluate internet-sourced reference cases against authority gates."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.authority_ledger import build_authority_ledger  # noqa: E402
from src.intelligence.hardware_plan import HardwarePlanOrchestrator  # noqa: E402
from src.intelligence.internet_reference_corpus import (  # noqa: E402
    SCHEMA_VERSION,
    internet_dataset_sources,
    internet_reference_cases,
)
from src.intelligence.measurement_session_progress import build_measurement_session_progress  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "eval" / "internet_reference_corpus"
DEFAULT_DATA_DIR = ROOT / "data" / "internet_reference_corpus"


def evaluate_cases() -> Dict[str, Any]:
    planner = HardwarePlanOrchestrator()
    sources = internet_dataset_sources()
    cases = internet_reference_cases()
    rows = [_evaluate_case(planner, case) for case in cases]
    summary = _summary(rows, sources)
    return {
        "mode": "internet_reference_corpus_eval",
        "schema_version": "internet_reference_corpus_eval.v1",
        "corpus_schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "dataset_sources": sources,
        "cases": rows,
        "claim_boundary": (
            "Internet references can train and evaluate visual/reference reasoning, but cannot grant measured "
            "pinout, simulation, power/splice, or production repair authority without bench evidence."
        ),
    }


def _evaluate_case(planner: HardwarePlanOrchestrator, case: Dict[str, Any]) -> Dict[str, Any]:
    payload = case["payload"]
    expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    ledger = build_authority_ledger(payload)
    progress = build_measurement_session_progress(payload, include_authority_closure=False)
    plan = planner.plan(payload)
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
    topology_summary = (ledger.get("evidence_summary") or {}).get("topology") or {}
    progress_summary = progress.get("progress") if isinstance(progress.get("progress"), dict) else {}
    can = ledger.get("can") if isinstance(ledger.get("can"), dict) else {}
    stage_status = {stage.get("stage_id"): stage.get("status") for stage in ledger.get("stages") or [] if isinstance(stage, dict)}
    actual = {
        "authority_level": ledger.get("current_authority_level"),
        "authority_score": ledger.get("authority_score"),
        "stage_status": stage_status,
        "can": {
            "use_measured_pinout": bool(can.get("use_measured_pinout")),
            "use_electrical_simulation": bool(can.get("use_electrical_simulation")),
            "power_or_splice_now": bool(can.get("power_or_splice_now")),
            "claim_production_repair_release": bool(can.get("claim_production_repair_release")),
        },
        "topology": {
            "reference_only": bool(topology_summary.get("reference_only")),
            "measurement_backed": bool(topology_summary.get("measurement_backed")),
            "pinout_known": bool(topology_summary.get("pinout_known")),
            "unknown_pin_count": topology_summary.get("unknown_pin_count"),
            "source": topology_summary.get("source"),
        },
        "measurement_progress": {
            "status": progress.get("status"),
            "required_count": progress_summary.get("required_count"),
            "open_count": progress_summary.get("open_count"),
            "closed_count": progress_summary.get("closed_count"),
            "next_action": (progress.get("next_measurement") or {}).get("action_id")
            if isinstance(progress.get("next_measurement"), dict)
            else None,
        },
        "plan": {
            "status": integrated.get("status"),
            "selected_resource_ids": integrated.get("selected_resource_ids") or [],
            "production_authorized": bool(production.get("authorized")),
            "production_decision": production.get("decision"),
            "can_power_or_splice": ((integrated.get("assurance") or {}).get("can_power_or_splice") if isinstance(integrated.get("assurance"), dict) else None),
        },
    }
    checks = _checks(actual, expected)
    overclaim = any(
        actual["can"][key]
        for key in [
            "use_measured_pinout",
            "use_electrical_simulation",
            "power_or_splice_now",
            "claim_production_repair_release",
        ]
    ) or bool(actual["plan"]["production_authorized"])
    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "source": case["source"],
        "passed": all(checks.values()) and not overclaim,
        "overclaim": overclaim,
        "checks": checks,
        "actual": actual,
        "expected": expected,
    }


def _checks(actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, bool]:
    checks = {
        "reference_only": actual["topology"]["reference_only"] is bool(expected.get("reference_only", True)),
        "measurement_plan_required": int(actual["measurement_progress"].get("required_count") or 0) > 0,
        "measured_pinout_not_granted": actual["can"]["use_measured_pinout"] is bool(expected.get("can_use_measured_pinout", False)),
        "electrical_simulation_not_granted": actual["can"]["use_electrical_simulation"] is bool(expected.get("can_use_electrical_simulation", False)),
        "power_splice_not_granted": actual["can"]["power_or_splice_now"] is bool(expected.get("can_power_or_splice_now", False)),
        "production_not_authorized": actual["plan"]["production_authorized"] is bool(expected.get("production_authorized", False)),
    }
    return checks


def _summary(rows: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    passed = [row for row in rows if row.get("passed")]
    overclaims = [row for row in rows if row.get("overclaim")]
    source_modalities = sorted({item for source in sources for item in source.get("modality", [])})
    authority_uses = sorted({item for source in sources for item in source.get("authority_use", [])})
    return {
        "source_count": len(sources),
        "reference_case_count": len(rows),
        "passed_count": len(passed),
        "pass_rate": round(len(passed) / max(len(rows), 1), 3),
        "overclaim_count": len(overclaims),
        "overclaim_cases": [row["case_id"] for row in overclaims],
        "measurement_plan_case_count": sum(1 for row in rows if int((row.get("actual") or {}).get("measurement_progress", {}).get("required_count") or 0) > 0),
        "source_modalities": source_modalities,
        "authority_uses": authority_uses,
        "authority_gain": {
            "visual_reference_planning": "strong",
            "measured_pinout_authority": "requires_bench_capture",
            "production_repair_authority": "requires_bench_outcome_and_release",
            "estimated_arbitrary_board_push": "60_to_75_or_80_percent_before_physical_bench_cases",
        },
    }


def render_markdown(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Internet Reference Corpus Eval",
        "",
        "Public internet sources are evaluated as reference/planning evidence only.",
        "",
        "## Summary",
        "",
        f"- Dataset/source lanes: {summary['source_count']}",
        f"- Reference board cases: {summary['reference_case_count']}",
        f"- Pass rate: {summary['pass_rate']}",
        f"- Overclaim cases: {summary['overclaim_count']}",
        f"- Measurement-plan cases: {summary['measurement_plan_case_count']}",
        f"- Estimated arbitrary-board push: {summary['authority_gain']['estimated_arbitrary_board_push']}",
        "",
        "## Source Lanes",
        "",
        "| Source | Access | Use | Limits |",
        "| --- | --- | --- | --- |",
    ]
    for source in report["dataset_sources"]:
        lines.append(
            "| [{name}]({url}) | `{access}` | {uses} | {limits} |".format(
                name=source["name"],
                url=source["url"],
                access=source["access"],
                uses=", ".join(f"`{item}`" for item in source.get("authority_use", [])),
                limits=source.get("limits", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Pass | Authority | Required Measurements | Overclaim | Source |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in report["cases"]:
        actual = row["actual"]
        lines.append(
            "| `{case}` | `{passed}` | `{level}` | {required} | `{overclaim}` | [source]({url}) |".format(
                case=row["case_id"],
                passed=row["passed"],
                level=actual["authority_level"],
                required=actual["measurement_progress"]["required_count"],
                overclaim=row["overclaim"],
                url=row["source"]["url"],
            )
        )
    lines.extend(["", "## Failed Checks", ""])
    failures = 0
    for row in report["cases"]:
        failed = [name for name, passed in row["checks"].items() if not passed]
        if row["overclaim"]:
            failed.append("overclaim")
        if not failed:
            continue
        failures += len(failed)
        lines.append(f"- `{row['case_id']}`: {', '.join(failed)}")
    if failures == 0:
        lines.append("No failed checks.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()

    report = evaluate_cases()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "latest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "README.md").write_text(render_markdown(report), encoding="utf-8")
    (args.data_dir / "source_catalog.json").write_text(json.dumps(report["dataset_sources"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.data_dir / "reference_cases.json").write_text(json.dumps(internet_reference_cases(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = report["summary"]
    print(
        "sources={source_count} cases={reference_case_count} pass_rate={pass_rate} overclaims={overclaim_count} "
        "measurement_plans={measurement_plan_case_count}".format(**summary)
    )
    for row in report["cases"]:
        actual = row["actual"]
        print(
            f"{row['case_id']}: passed={row['passed']} level={actual['authority_level']} "
            f"required={actual['measurement_progress']['required_count']} overclaim={row['overclaim']}"
        )
    return 0 if summary["overclaim_count"] == 0 and summary["pass_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
