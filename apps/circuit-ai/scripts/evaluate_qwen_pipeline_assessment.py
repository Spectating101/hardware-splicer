#!/usr/bin/env python3
"""Replay cached Qwen vision responses through the hardware planning pipeline."""

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
from src.intelligence.vision_board_evidence import board_evidence_bridge  # noqa: E402
from src.vision.qwen_board_vision import parse_qwen_board_response  # noqa: E402


DEFAULT_REPORT = ROOT / "eval" / "qwen_trial" / "latest_report.json"
DEFAULT_CACHE_DIR = ROOT / "eval" / "qwen_trial" / "cache"
DEFAULT_OUTPUT = ROOT / "eval" / "qwen_trial" / "live_pipeline_assessment.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def assess_row(
    planner: HardwarePlanOrchestrator,
    row: Dict[str, Any],
    *,
    cache_dir: Path,
    target_authority_level: str,
) -> Dict[str, Any]:
    cache_key = str(row.get("cache_key") or "")
    cache = load_json(cache_dir / f"{cache_key}.json", {})
    parsed = parse_qwen_board_response(cache.get("response") if isinstance(cache.get("response"), dict) else {})
    evidence = parsed.get("board_evidence") if isinstance(parsed.get("board_evidence"), dict) else {}
    bridge = board_evidence_bridge(evidence)
    plan = planner.plan(
        {
            "goal": f"inspect {row.get('scenario')} board evidence and produce a safe salvage, repair, or reuse plan",
            "target_authority_level": target_authority_level,
            "strategy_mode": "constrained",
            "board_evidence": evidence,
            "use_reference_catalog": False,
        }
    )
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    trust = analysis.get("arbitrary_board_trust_assessment") if isinstance(analysis.get("arbitrary_board_trust_assessment"), dict) else {}
    function = analysis.get("board_function_inference") if isinstance(analysis.get("board_function_inference"), dict) else {}
    strategy = plan.get("resource_strategy") if isinstance(plan.get("resource_strategy"), dict) else {}
    return {
        "scenario": row.get("scenario"),
        "json_valid": (parsed.get("parse_diagnostics") or {}).get("json_valid"),
        "truncated": (parsed.get("parse_diagnostics") or {}).get("truncated"),
        "vision_components": len((bridge.get("board_evidence") or {}).get("components") or []),
        "vision_connectors": len((bridge.get("board_evidence") or {}).get("connectors") or []),
        "vision_resources": len(bridge.get("resource_candidates") or []),
        "vision_hazards": len((bridge.get("hazard_profile") or {}).get("hazards") or []),
        "required_capabilities": strategy.get("required_capabilities") or [],
        "function": function.get("primary_function_id"),
        "function_confidence": function.get("confidence"),
        "selected_resources": [resource.get("resource_id") for resource in strategy.get("selected_resources") or []],
        "coverage": (strategy.get("coverage") or {}).get("coverage_score"),
        "resource_readiness": (strategy.get("build_readiness") or {}).get("status"),
        "status": integrated.get("status"),
        "can_power_or_splice": (integrated.get("assurance") or {}).get("can_power_or_splice"),
        "trust_level": trust.get("level"),
        "trust_score": trust.get("score"),
        "production_readiness_score": trust.get("production_readiness_score"),
        "blocking_gap_count": len(trust.get("blocking_gaps") or []),
        "next_actions": (integrated.get("next_actions") or [])[:6],
    }


def summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "row_count": len(rows),
        "json_valid_count": sum(1 for row in rows if row.get("json_valid")),
        "rows_with_resources": sum(1 for row in rows if row.get("vision_resources")),
        "rows_with_selected_resources": sum(1 for row in rows if row.get("selected_resources")),
        "rows_with_full_coverage": sum(1 for row in rows if row.get("coverage") == 1.0),
        "rows_power_or_splice_authorized": sum(1 for row in rows if row.get("can_power_or_splice")),
        "max_production_readiness_score": max([float(row.get("production_readiness_score") or 0.0) for row in rows] or [0.0]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-authority-level", default="production_repair")
    args = parser.parse_args()

    report = load_json(args.report, {})
    input_rows = [row for row in report.get("rows") or [] if isinstance(row, dict)]
    planner = HardwarePlanOrchestrator()
    rows = [assess_row(planner, row, cache_dir=args.cache_dir, target_authority_level=args.target_authority_level) for row in input_rows]
    result = {
        "schema_version": "qwen_live_pipeline_assessment.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_report": str(args.report.relative_to(ROOT) if args.report.is_relative_to(ROOT) else args.report),
        "summary": summary(rows),
        "rows": rows,
    }
    write_json(args.out, result)
    print(
        "rows={row_count} json_valid={json_valid_count} selected={rows_with_selected_resources} full_coverage={rows_with_full_coverage} authorized={rows_power_or_splice_authorized}".format(
            **result["summary"]
        )
    )
    for row in rows:
        print(
            f"{row['scenario']}: function={row.get('function')} coverage={row.get('coverage')} status={row.get('status')} can_power={row.get('can_power_or_splice')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
