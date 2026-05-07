#!/usr/bin/env python3
"""Compare Circuit-AI board dossiers against explicit truth-case expectations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.intelligence.board_session_store import BoardSessionStore


def _flatten_text(value: Any) -> str:
    parts: List[str] = []

    def visit(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, dict):
            for key, nested in item.items():
                parts.append(str(key))
                visit(nested)
            return
        if isinstance(item, list):
            for nested in item:
                visit(nested)
            return
        parts.append(str(item))

    visit(value)
    return " ".join(parts).lower()


def _matches(assertion: Dict[str, Any], dossier_text: str) -> Dict[str, Any]:
    must_contain = [str(item).lower() for item in assertion.get("must_contain") or []]
    one_of = [str(item).lower() for item in assertion.get("one_of") or []]
    missing = [term for term in must_contain if term not in dossier_text]
    matched_one_of = [term for term in one_of if term in dossier_text]
    one_of_passed = bool(matched_one_of) if one_of else True
    passed = not missing and one_of_passed
    return {
        "id": assertion.get("id"),
        "description": assertion.get("description"),
        "passed": passed,
        "weight": float(assertion.get("weight", 1.0) or 1.0),
        "missing_terms": missing,
        "matched_one_of": matched_one_of,
    }


def _score(assertion_results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    results = list(assertion_results)
    total = sum(float(result.get("weight", 1.0)) for result in results)
    earned = sum(float(result.get("weight", 1.0)) for result in results if result.get("passed"))
    score = earned / total if total else 0.0
    if score >= 0.85:
        verdict = "aligned_with_truth"
    elif score >= 0.55:
        verdict = "partially_aligned"
    else:
        verdict = "missed_truth"
    return {
        "passed": sum(1 for result in results if result.get("passed")),
        "total": len(results),
        "weighted_score": round(score, 3),
        "verdict": verdict,
    }


def _case_summary(case: Dict[str, Any], dossier: Dict[str, Any], assertion_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    open_tasks = dossier.get("open_tasks") if isinstance(dossier.get("open_tasks"), list) else []
    return {
        "case_id": case.get("case_id"),
        "source_type": "board_session_dossier",
        "session_id": case.get("session_id"),
        "title": case.get("title"),
        "truth_strength": case.get("truth_strength") or "outcome_grounded_session",
        "truth_basis": case.get("why_this_is_a_good_first_truth_case"),
        "assistant_oracle_deduction": case.get("assistant_oracle_deduction"),
        "system_dossier_summary": {
            "status": dossier.get("status"),
            "executive_summary": dossier.get("executive_summary"),
            "known": dossier.get("known", [])[:8],
            "uncertain": dossier.get("uncertain", [])[:8],
            "next_actions": dossier.get("next_actions", [])[:8],
            "repair_reuse": dossier.get("repair_reuse", {}),
            "confirmed_findings": dossier.get("confirmed_findings", [])[:8],
            "open_task_count": len(open_tasks),
        },
        "assertions": assertion_results,
        "score": _score(assertion_results),
    }


def _repair_eval_case_summary(case: Dict[str, Any], payload: Dict[str, Any], assertion_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "source_type": "repair_eval_case",
        "title": case.get("title") or payload.get("title"),
        "truth_strength": case.get("truth_strength") or "reference_workflow_alignment",
        "truth_basis": case.get("why_this_is_a_good_first_truth_case"),
        "assistant_oracle_deduction": case.get("assistant_oracle_deduction"),
        "system_case_summary": {
            "expected_lane": payload.get("expected_lane"),
            "verdict": payload.get("verdict"),
            "workflow_score": payload.get("workflow_score"),
            "coverage": payload.get("coverage", {}),
            "repair_guide": payload.get("repair_guide", {}),
            "playbook": payload.get("playbook", {}),
            "board_session": payload.get("board_session", {}),
            "blockers": payload.get("blockers", []),
        },
        "assertions": assertion_results,
        "score": _score(assertion_results),
    }


def _write_markdown(report: Dict[str, Any], path: Path) -> None:
    lines = [
        "# Truth Deduction Benchmark",
        "",
        f"Cases: {report['summary']['case_count']}",
        f"Average score: {report['summary']['average_weighted_score']}",
        f"Aligned cases: {report['summary']['aligned_case_count']}",
        f"Outcome-grounded sessions: {report['summary']['source_counts'].get('board_session_dossier', 0)}",
        f"Reference workflow checks: {report['summary']['source_counts'].get('repair_eval_case', 0)}",
        "",
    ]
    for case in report["cases"]:
        score = case["score"]
        lines.extend(
            [
                f"## {case['case_id']}",
                "",
                f"Verdict: `{score['verdict']}` ({score['weighted_score']}, {score['passed']}/{score['total']} assertions)",
                f"Truth strength: `{case.get('truth_strength')}`",
                "",
                "Assistant/oracle deduction:",
                f"- Device family: {case['assistant_oracle_deduction'].get('device_family')}",
                f"- Most likely fault: {case['assistant_oracle_deduction'].get('most_likely_fault')}",
                f"- Correct action: {case['assistant_oracle_deduction'].get('correct_action')}",
                "",
                "Circuit-AI dossier:",
                f"- Status: {case.get('system_dossier_summary', {}).get('status', case.get('system_case_summary', {}).get('verdict'))}",
                f"- Top fault: {case.get('system_dossier_summary', {}).get('repair_reuse', {}).get('top_fault') or case.get('system_case_summary', {}).get('repair_guide', {}).get('top_fault_name')}",
                f"- Summary: {case.get('system_dossier_summary', {}).get('executive_summary') or 'repair/reference case workflow evaluation'}",
                "",
                "Assertion results:",
            ]
        )
        for assertion in case["assertions"]:
            marker = "PASS" if assertion["passed"] else "FAIL"
            detail = ""
            if assertion.get("missing_terms"):
                detail = f" missing={assertion['missing_terms']}"
            lines.append(f"- {marker}: {assertion['description']}{detail}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("eval/truth_deduction/cases.json"))
    parser.add_argument("--store", type=Path, default=Path("data/board_sessions/sessions.json"))
    parser.add_argument("--output", type=Path, default=Path("eval/truth_deduction/latest.json"))
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    store = BoardSessionStore(args.store)
    repair_eval_cache: Dict[str, Dict[str, Any]] = {}
    results = []
    for case in cases:
        source = case.get("system_source") if isinstance(case.get("system_source"), dict) else {}
        if source.get("type") == "repair_eval_case":
            report_path = str(source.get("report") or "eval/real_repair_cases/real_repair_case_eval.json")
            if report_path not in repair_eval_cache:
                repair_eval_cache[report_path] = json.loads(Path(report_path).read_text(encoding="utf-8"))
            report = repair_eval_cache[report_path]
            payload = next((row for row in report.get("cases", []) if row.get("case_id") == source.get("case_id")), {})
            if not payload:
                results.append(
                    {
                        "case_id": case.get("case_id"),
                        "error": f"repair eval case not found: {source.get('case_id')}",
                        "score": {"passed": 0, "total": len(case.get("assertions") or []), "weighted_score": 0.0, "verdict": "missing_case"},
                    }
                )
                continue
            payload_text = _flatten_text(payload)
            assertion_results = [_matches(assertion, payload_text) for assertion in case.get("assertions") or []]
            results.append(_repair_eval_case_summary(case, payload, assertion_results))
        else:
            session_id = str(case["session_id"])
            dossier = store.dossier(session_id)
            if dossier.get("error"):
                results.append(
                    {
                        "case_id": case.get("case_id"),
                        "session_id": session_id,
                        "error": dossier["error"],
                        "score": {"passed": 0, "total": len(case.get("assertions") or []), "weighted_score": 0.0, "verdict": "missing_session"},
                    }
                )
                continue
            dossier_text = _flatten_text(dossier)
            assertion_results = [_matches(assertion, dossier_text) for assertion in case.get("assertions") or []]
            results.append(_case_summary(case, dossier, assertion_results))

    average = sum(case["score"]["weighted_score"] for case in results) / len(results) if results else 0.0
    source_counts: Dict[str, int] = {}
    for case in results:
        source_type = str(case.get("source_type") or "unknown")
        source_counts[source_type] = source_counts.get(source_type, 0) + 1
    report = {
        "mode": "truth_deduction_benchmark",
        "summary": {
            "case_count": len(results),
            "average_weighted_score": round(average, 3),
            "aligned_case_count": sum(1 for case in results if case["score"]["verdict"] == "aligned_with_truth"),
            "source_counts": source_counts,
        },
        "cases": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report, args.output.with_suffix(".md"))
    print(f"Wrote {args.output}")
    print(json.dumps(report["summary"], indent=2))
    for case in results:
        print(f"{case['case_id']}: {case['score']['verdict']} ({case['score']['weighted_score']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
