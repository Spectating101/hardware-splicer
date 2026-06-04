#!/usr/bin/env python3
"""Evaluate real-board corpus manifests through the backend authority pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.hardware_plan import HardwarePlanOrchestrator  # noqa: E402


DEFAULT_MANIFEST = ROOT / "data" / "real_board_corpus" / "manifest.example.json"
DEFAULT_OUTPUT = ROOT / "eval" / "real_board_corpus" / "latest.json"


def _load_manifest(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("Corpus manifest must be a JSON object.")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Corpus manifest must contain a non-empty cases[] array.")
    return manifest


def _evaluate_case(planner: HardwarePlanOrchestrator, case: Dict[str, Any]) -> Dict[str, Any]:
    payload = case.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"{case.get('case_id') or '<unknown>'}: payload must be an object.")
    plan = planner.plan(payload)
    analysis = plan.get("analysis") or {}
    integrated = plan.get("integrated_plan") or {}
    trust = analysis.get("arbitrary_board_trust_assessment") or {}
    summary = analysis.get("hardware_plan_summary") if isinstance(analysis.get("hardware_plan_summary"), dict) else {}
    production = (
        analysis.get("production_repair_authority")
        or integrated.get("production_repair_authority")
        or summary.get("production_repair_authority")
        or {}
    )
    bench = analysis.get("bench_protocol_pack") or {}
    closure = analysis.get("active_evidence_closure_plan") if isinstance(analysis.get("active_evidence_closure_plan"), dict) else {}
    lanes = [lane for lane in closure.get("closure_lanes") or [] if isinstance(lane, dict)]
    multiview = analysis.get("multiview_board_reconstruction") if isinstance(analysis.get("multiview_board_reconstruction"), dict) else {}
    capture_coverage = multiview.get("capture_coverage") if isinstance(multiview.get("capture_coverage"), dict) else {}
    expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    actual = {
        "function": (analysis.get("board_function_inference") or {}).get("primary_function_id"),
        "status": integrated.get("status"),
        "trust_level": trust.get("level"),
        "trust_score": trust.get("score"),
        "production_readiness_score": trust.get("production_readiness_score"),
        "can_power_or_splice": (integrated.get("assurance") or {}).get("can_power_or_splice"),
        "production_authorized": bool(production.get("authorized")),
        "production_decision": production.get("decision"),
        "bench_protocol": {
            "primary_function_id": bench.get("primary_function_id"),
            "title": bench.get("title"),
            "required_measurement_categories": bench.get("required_measurement_categories") or [],
            "step_count": bench.get("step_count"),
            "specialist_only": bool(bench.get("specialist_only")),
        },
        "blocking_gaps": trust.get("blocking_gaps") or [],
        "active_closure": {
            "available": bool(closure.get("available")),
            "current_stage": closure.get("current_stage"),
            "observability_score": closure.get("observability_score"),
            "authority_ceiling_if_next_batch_closes": closure.get("authority_ceiling_if_next_batch_closes"),
            "open_lane_count": len([lane for lane in lanes if lane.get("status") != "complete"]),
            "next_best_task_count": len(closure.get("next_best_tasks") or []),
            "can_claim_now": closure.get("can_claim_now") or [],
        },
        "multiview_capture_coverage": {
            "available": bool(capture_coverage),
            "score": capture_coverage.get("score"),
            "required_complete": bool(capture_coverage.get("required_complete")),
            "open_required_lanes": capture_coverage.get("open_required_lanes") or [],
            "recommended_open_lanes": capture_coverage.get("recommended_open_lanes") or [],
        },
    }
    checks = _checks(actual, expected)
    source = case.get("source") if isinstance(case.get("source"), dict) else {}
    return {
        "case_id": str(case.get("case_id") or "case"),
        "title": case.get("title"),
        "passed": all(checks.values()),
        "checks": checks,
        "actual": actual,
        "expected": expected,
        "source_quality": _source_quality(case, source),
    }


def _checks(actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, bool]:
    checks: Dict[str, bool] = {}
    for key in ["function", "status", "trust_level", "can_power_or_splice", "production_authorized"]:
        if key in expected:
            checks[key] = actual.get(key) == expected.get(key)
    if "min_production_readiness_score" in expected:
        checks["min_production_readiness_score"] = float(actual.get("production_readiness_score") or 0.0) >= float(
            expected.get("min_production_readiness_score") or 0.0
        )
    if "max_production_readiness_score" in expected:
        checks["max_production_readiness_score"] = float(actual.get("production_readiness_score") or 0.0) <= float(
            expected.get("max_production_readiness_score") or 1.0
        )
    required_categories = expected.get("required_bench_categories") or []
    if required_categories:
        actual_categories = set((actual.get("bench_protocol") or {}).get("required_measurement_categories") or [])
        checks["required_bench_categories"] = set(str(item) for item in required_categories).issubset(actual_categories)
    if "max_active_closure_open_lanes" in expected:
        checks["max_active_closure_open_lanes"] = int((actual.get("active_closure") or {}).get("open_lane_count") or 0) <= int(
            expected.get("max_active_closure_open_lanes") or 0
        )
    if "min_active_closure_observability_score" in expected:
        checks["min_active_closure_observability_score"] = float((actual.get("active_closure") or {}).get("observability_score") or 0.0) >= float(
            expected.get("min_active_closure_observability_score") or 0.0
        )
    if "min_multiview_capture_coverage_score" in expected:
        checks["min_multiview_capture_coverage_score"] = float((actual.get("multiview_capture_coverage") or {}).get("score") or 0.0) >= float(
            expected.get("min_multiview_capture_coverage_score") or 0.0
        )
    if "multiview_capture_required_complete" in expected:
        checks["multiview_capture_required_complete"] = bool((actual.get("multiview_capture_coverage") or {}).get("required_complete")) is bool(
            expected.get("multiview_capture_required_complete")
        )
    return checks or {"has_backend_result": bool(actual.get("function"))}


def _source_quality(case: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    payload = case.get("payload") if isinstance(case.get("payload"), dict) else {}
    board_evidence = payload.get("board_evidence") if isinstance(payload.get("board_evidence"), dict) else {}
    photo_set = payload.get("board_photo_set") if isinstance(payload.get("board_photo_set"), dict) else {}
    photo_observations = photo_set.get("photo_observations") if isinstance(photo_set.get("photo_observations"), list) else []
    bench_capture = payload.get("bench_topology_capture") if isinstance(payload.get("bench_topology_capture"), dict) else {}
    return {
        "photo_ref_count": len(source.get("photo_uris") or board_evidence.get("photos") or board_evidence.get("images") or photo_observations or []),
        "has_board_evidence": bool(payload.get("board_evidence") or photo_observations),
        "has_topology_evidence": bool(payload.get("topology_evidence") or bench_capture),
        "has_measurements": bool(payload.get("measurements") or payload.get("topology_evidence") or bench_capture),
        "has_terminal_outcome": bool(payload.get("outcome_history") or payload.get("outcome")),
        "has_release_manifest": bool(payload.get("production_release") or payload.get("release_manifest")),
        "is_example_seed": bool(source.get("example_seed")),
    }


def _summary(rows: List[Dict[str, Any]], manifest: Dict[str, Any]) -> Dict[str, Any]:
    passed = sum(1 for row in rows if row.get("passed"))
    qualities = [row.get("source_quality") or {} for row in rows]
    return {
        "schema_version": "real_board_corpus_eval.v1",
        "manifest_schema_version": manifest.get("schema_version"),
        "case_count": len(rows),
        "passed": passed,
        "pass_rate": round(passed / max(len(rows), 1), 3),
        "cases_with_photo_refs": sum(1 for quality in qualities if quality.get("photo_ref_count")),
        "cases_with_topology": sum(1 for quality in qualities if quality.get("has_topology_evidence")),
        "cases_with_terminal_outcome": sum(1 for quality in qualities if quality.get("has_terminal_outcome")),
        "cases_with_release_manifest": sum(1 for quality in qualities if quality.get("has_release_manifest")),
        "example_seed_cases": sum(1 for quality in qualities if quality.get("is_example_seed")),
        "cases_with_active_closure": sum(1 for row in rows if ((row.get("actual") or {}).get("active_closure") or {}).get("available")),
        "cases_with_closure_complete": sum(1 for row in rows if int(((row.get("actual") or {}).get("active_closure") or {}).get("open_lane_count") or 0) == 0),
        "avg_active_closure_open_lanes": round(
            sum(int(((row.get("actual") or {}).get("active_closure") or {}).get("open_lane_count") or 0) for row in rows) / max(len(rows), 1),
            3,
        ),
        "avg_multiview_capture_coverage_score": round(
            sum(float(((row.get("actual") or {}).get("multiview_capture_coverage") or {}).get("score") or 0.0) for row in rows) / max(len(rows), 1),
            3,
        ),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = _load_manifest(args.manifest)
    planner = HardwarePlanOrchestrator()
    rows = [_evaluate_case(planner, case) for case in manifest["cases"]]
    result = {"summary": _summary(rows, manifest), "cases": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    summary = result["summary"]
    print(f"cases={summary['case_count']} passed={summary['passed']} pass_rate={summary['pass_rate']:.3f}")
    for row in rows:
        print(f"{row['case_id']}: passed={row['passed']} actual={row['actual']}")
    return 0 if summary["passed"] == summary["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
