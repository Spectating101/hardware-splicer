#!/usr/bin/env python3
"""Replay cached Qwen responses as multi-observation board photo sets."""

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
from src.vision.qwen_board_vision import parse_qwen_board_response  # noqa: E402


DEFAULT_CACHE_DIR = ROOT / "eval" / "qwen_trial" / "cache"
DEFAULT_OUTPUT = ROOT / "eval" / "qwen_trial" / "multiview_pipeline_assessment.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cached_observations(cache_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for path in sorted(cache_dir.glob("*.json")):
        cache = load_json(path, {})
        response = cache.get("response") if isinstance(cache.get("response"), dict) else {}
        parsed = parse_qwen_board_response(response)
        evidence = parsed.get("board_evidence") if isinstance(parsed.get("board_evidence"), dict) else {}
        diagnostics = parsed.get("parse_diagnostics") if isinstance(parsed.get("parse_diagnostics"), dict) else {}
        if not evidence or not diagnostics.get("json_valid"):
            continue
        scenario = _scenario_from_cache(cache, path.stem)
        groups.setdefault(scenario, []).append(
            {
                "photo_id": path.stem,
                "view_hint": _view_hint(cache, scenario),
                "provider": "qwen",
                "parse_diagnostics": diagnostics,
                "qwen_board_vision": parsed,
                "board_evidence": evidence,
            }
        )
    return groups


def assess_group(planner: HardwarePlanOrchestrator, scenario: str, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {
        "goal": f"fuse Qwen observations for {scenario} and produce a safe repair, reuse, or splice plan",
        "target_authority_level": "production_repair",
        "strategy_mode": "constrained",
        "board_photo_set": {"photo_observations": observations},
        "use_reference_catalog": False,
    }
    plan = planner.plan(payload)
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    strategy = plan.get("resource_strategy") if isinstance(plan.get("resource_strategy"), dict) else {}
    trust = analysis.get("arbitrary_board_trust_assessment") if isinstance(analysis.get("arbitrary_board_trust_assessment"), dict) else {}
    function = analysis.get("board_function_inference") if isinstance(analysis.get("board_function_inference"), dict) else {}
    reconstruction = analysis.get("multiview_board_reconstruction") if isinstance(analysis.get("multiview_board_reconstruction"), dict) else {}
    coverage = reconstruction.get("capture_coverage") if isinstance(reconstruction.get("capture_coverage"), dict) else {}
    closure = analysis.get("active_evidence_closure_plan") if isinstance(analysis.get("active_evidence_closure_plan"), dict) else {}
    lanes = [lane for lane in closure.get("closure_lanes") or [] if isinstance(lane, dict)]
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
    return {
        "scenario": scenario,
        "observation_count": len(observations),
        "function": function.get("primary_function_id"),
        "function_confidence": function.get("confidence"),
        "status": integrated.get("status"),
        "selected_resources": [resource.get("resource_id") for resource in strategy.get("selected_resources") or []],
        "resource_coverage": (strategy.get("coverage") or {}).get("coverage_score"),
        "trust_level": trust.get("level"),
        "trust_score": trust.get("score"),
        "production_readiness_score": trust.get("production_readiness_score"),
        "production_authorized": bool(production.get("authorized")),
        "production_decision": production.get("decision"),
        "can_power_or_splice": (integrated.get("assurance") or {}).get("can_power_or_splice"),
        "capture_coverage": {
            "score": coverage.get("score"),
            "required_complete": bool(coverage.get("required_complete")),
            "open_required_lanes": coverage.get("open_required_lanes") or [],
            "recommended_open_lanes": coverage.get("recommended_open_lanes") or [],
        },
        "active_closure": {
            "current_stage": closure.get("current_stage"),
            "open_lane_count": len([lane for lane in lanes if lane.get("status") != "complete"]),
            "next_best_task_count": len(closure.get("next_best_tasks") or []),
        },
        "next_actions": (integrated.get("next_actions") or [])[:8],
    }


def summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "scenario_count": len(rows),
        "capture_complete_count": sum(1 for row in rows if (row.get("capture_coverage") or {}).get("required_complete")),
        "selected_resource_count": sum(1 for row in rows if row.get("selected_resources")),
        "production_authorized_count": sum(1 for row in rows if row.get("production_authorized")),
        "avg_capture_coverage_score": round(
            sum(float((row.get("capture_coverage") or {}).get("score") or 0.0) for row in rows) / max(len(rows), 1),
            3,
        ),
        "max_production_readiness_score": max([float(row.get("production_readiness_score") or 0.0) for row in rows] or [0.0]),
    }


def _scenario_from_cache(cache: Dict[str, Any], cache_key: str) -> str:
    preview = str(cache.get("request_preview") or "")
    name = Path(preview).name.replace(".preview.json", "") if preview else cache_key
    suffix = f"_{cache_key}"
    if name.endswith(suffix):
        name = name[: -len(suffix)]
    return _safe_id(name)


def _view_hint(cache: Dict[str, Any], scenario: str) -> str:
    preview = str(cache.get("request_preview") or "")
    text = " ".join([scenario, preview]).lower()
    if any(term in text for term in ["crop", "close", "marking"]):
        return "close-up qwen board observation"
    if any(term in text for term in ["back", "bottom", "solder"]):
        return "backside qwen board observation"
    return "qwen board observation"


def _safe_id(value: Any) -> str:
    safe = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "")).strip("_")
    return "_".join(part for part in safe.split("_") if part)[:90] or "qwen_multiview"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    groups = cached_observations(args.cache_dir)
    planner = HardwarePlanOrchestrator()
    rows = [assess_group(planner, scenario, observations) for scenario, observations in sorted(groups.items())]
    result = {
        "schema_version": "qwen_multiview_pipeline_assessment.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cache_dir": str(args.cache_dir.relative_to(ROOT) if args.cache_dir.is_relative_to(ROOT) else args.cache_dir),
        "summary": summary(rows),
        "rows": rows,
    }
    write_json(args.out, result)
    print(
        "scenarios={scenario_count} capture_complete={capture_complete_count} selected={selected_resource_count} authorized={production_authorized_count} avg_capture={avg_capture_coverage_score}".format(
            **result["summary"]
        )
    )
    for row in rows:
        coverage = row.get("capture_coverage") or {}
        print(
            f"{row['scenario']}: observations={row['observation_count']} function={row.get('function')} "
            f"capture={coverage.get('score')} status={row.get('status')} can_power={row.get('can_power_or_splice')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
