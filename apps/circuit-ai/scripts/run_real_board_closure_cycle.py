#!/usr/bin/env python3
"""Run a before/after evidence closure cycle for one real-board payload.

This is the repeatable loop for moving a board from visual/intake candidate to
measured authority: run the backend on the current payload, merge a new evidence
batch, run it again, and write the readiness delta plus remaining closure tasks.
"""

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


DEFAULT_OUTPUT_ROOT = ROOT / "eval" / "real_board_closure_cycles"


def run_closure_cycle_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    baseline_payload = _load_payload(args)
    evidence_batch = _load_evidence_batch(args)
    planner = HardwarePlanOrchestrator()
    before = planner.plan(baseline_payload)
    after_payload = _merge_payload_evidence(baseline_payload, evidence_batch)
    after = planner.plan(after_payload)
    report = _closure_report(
        cycle_id=_safe_id(args.cycle_id or _default_cycle_id(args)),
        baseline_payload=baseline_payload,
        evidence_batch=evidence_batch,
        after_payload=after_payload,
        before=before,
        after=after,
        notes=args.notes or "",
    )
    output_dir = Path(args.output_root) / report["cycle_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "before_plan.json", before)
    _write_json(output_dir / "after_payload.json", after_payload)
    _write_json(output_dir / "after_plan.json", after)
    _write_json(output_dir / "closure_cycle_report.json", report)
    report["artifacts"] = {
        "before_plan": str(_relative_to_root(output_dir / "before_plan.json")),
        "after_payload": str(_relative_to_root(output_dir / "after_payload.json")),
        "after_plan": str(_relative_to_root(output_dir / "after_plan.json")),
        "closure_cycle_report": str(_relative_to_root(output_dir / "closure_cycle_report.json")),
    }
    _write_json(output_dir / "closure_cycle_report.json", report)
    return report


def _load_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.payload_json:
        data = _load_json(Path(args.payload_json))
        return data.get("payload") if isinstance(data.get("payload"), dict) else data
    if args.case_json:
        case = _load_json(Path(args.case_json))
        payload = case.get("payload") if isinstance(case.get("payload"), dict) else {}
        if not payload:
            raise ValueError(f"Case JSON does not contain payload object: {args.case_json}")
        return payload
    raise ValueError("Pass --payload-json or --case-json.")


def _load_evidence_batch(args: argparse.Namespace) -> Dict[str, Any]:
    batch: Dict[str, Any] = {
        "schema_version": "real_board_evidence_batch.v1",
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "sources": {},
    }
    if args.board_evidence_json:
        batch["board_evidence"] = _load_json(Path(args.board_evidence_json))
        batch["sources"]["board_evidence_json"] = str(args.board_evidence_json)
    if args.reference_topology_json:
        batch["reference_topology"] = _load_json(Path(args.reference_topology_json))
        batch["sources"]["reference_topology_json"] = str(args.reference_topology_json)
    if args.bench_capture_json:
        batch["bench_topology_capture"] = _load_json(Path(args.bench_capture_json))
        batch["sources"]["bench_capture_json"] = str(args.bench_capture_json)
    if args.outcome_json:
        batch["outcome_history"] = _load_optional_rows(Path(args.outcome_json))
        batch["sources"]["outcome_json"] = str(args.outcome_json)
    if args.production_release_json:
        batch["production_release"] = _load_json(Path(args.production_release_json))
        batch["sources"]["production_release_json"] = str(args.production_release_json)
    if args.notes:
        batch["notes"] = args.notes
    return batch


def _merge_payload_evidence(payload: Dict[str, Any], evidence_batch: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(payload or {})
    for key in ["board_evidence", "reference_topology", "bench_topology_capture", "production_release"]:
        if isinstance(evidence_batch.get(key), dict) and evidence_batch[key]:
            merged[key] = evidence_batch[key]
    if evidence_batch.get("outcome_history"):
        existing = merged.get("outcome_history") if isinstance(merged.get("outcome_history"), list) else []
        merged["outcome_history"] = [
            *[row for row in existing if isinstance(row, dict)],
            *[row for row in evidence_batch["outcome_history"] if isinstance(row, dict)],
        ]
    return merged


def _closure_report(
    *,
    cycle_id: str,
    baseline_payload: Dict[str, Any],
    evidence_batch: Dict[str, Any],
    after_payload: Dict[str, Any],
    before: Dict[str, Any],
    after: Dict[str, Any],
    notes: str,
) -> Dict[str, Any]:
    before_summary = _plan_summary(before)
    after_summary = _plan_summary(after)
    before_closure = _closure_summary(before)
    after_closure = _closure_summary(after)
    return {
        "schema_version": "real_board_closure_cycle.v1",
        "cycle_id": cycle_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
        "baseline_source_quality": _source_quality(baseline_payload),
        "evidence_batch_quality": _source_quality(evidence_batch),
        "after_source_quality": _source_quality(after_payload),
        "before": before_summary,
        "after": after_summary,
        "closure_before": before_closure,
        "closure_after": after_closure,
        "delta": {
            "trust_score": _delta(before_summary.get("trust_score"), after_summary.get("trust_score")),
            "production_readiness_score": _delta(before_summary.get("production_readiness_score"), after_summary.get("production_readiness_score")),
            "observability_score": _delta(before_closure.get("observability_score"), after_closure.get("observability_score")),
            "authority_ceiling": _delta(before_closure.get("authority_ceiling_if_next_batch_closes"), after_closure.get("authority_ceiling_if_next_batch_closes")),
            "open_lane_count": int(after_closure.get("open_lane_count") or 0) - int(before_closure.get("open_lane_count") or 0),
            "next_best_task_count": int(after_closure.get("next_best_task_count") or 0) - int(before_closure.get("next_best_task_count") or 0),
            "production_authorized_changed": bool(before_summary.get("production_authorized")) != bool(after_summary.get("production_authorized")),
            "can_power_or_splice_changed": bool(before_summary.get("can_power_or_splice")) != bool(after_summary.get("can_power_or_splice")),
        },
        "closed_loop": {
            "status": _cycle_status(before_summary, after_summary, after_closure),
            "authority_gained": bool(after_summary.get("production_authorized")) and not bool(before_summary.get("production_authorized")),
            "controlled_reuse_gained": bool(after_summary.get("can_power_or_splice")) and not bool(before_summary.get("can_power_or_splice")),
            "remaining_tasks": after_closure.get("next_best_tasks") or [],
            "remaining_claim_limits": after_closure.get("cannot_claim_yet") or [],
        },
    }


def _plan_summary(plan: Dict[str, Any]) -> Dict[str, Any]:
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    trust = analysis.get("arbitrary_board_trust_assessment") if isinstance(analysis.get("arbitrary_board_trust_assessment"), dict) else {}
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
    completion = integrated.get("completion_contract") if isinstance(integrated.get("completion_contract"), dict) else {}
    casefile = production.get("authority_casefile") if isinstance(production.get("authority_casefile"), dict) else {}
    return {
        "function": (analysis.get("board_function_inference") or {}).get("primary_function_id"),
        "status": integrated.get("status"),
        "trust_level": trust.get("level"),
        "trust_score": trust.get("score"),
        "production_readiness_score": trust.get("production_readiness_score"),
        "can_power_or_splice": (integrated.get("assurance") or {}).get("can_power_or_splice"),
        "completion_state": completion.get("state"),
        "workflow_done": bool(completion.get("workflow_done")),
        "production_authorized": bool(production.get("authorized")),
        "production_decision": production.get("decision"),
        "production_casefile_status": casefile.get("status"),
        "production_blockers": production.get("blockers") or [],
        "production_requirements": production.get("requirements") or [],
        "selected_resource_ids": integrated.get("selected_resource_ids") or [],
        "next_actions": integrated.get("next_actions") or [],
    }


def _closure_summary(plan: Dict[str, Any]) -> Dict[str, Any]:
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    closure = analysis.get("active_evidence_closure_plan") if isinstance(analysis.get("active_evidence_closure_plan"), dict) else {}
    lanes = [lane for lane in closure.get("closure_lanes") or [] if isinstance(lane, dict)]
    return {
        "available": bool(closure.get("available")),
        "current_stage": closure.get("current_stage"),
        "observability_score": closure.get("observability_score"),
        "authority_ceiling_if_next_batch_closes": closure.get("authority_ceiling_if_next_batch_closes"),
        "lane_statuses": {str(lane.get("lane_id")): lane.get("status") for lane in lanes if lane.get("lane_id")},
        "open_lane_count": len([lane for lane in lanes if lane.get("status") != "complete"]),
        "next_best_task_count": len(closure.get("next_best_tasks") or []),
        "next_best_tasks": closure.get("next_best_tasks") or [],
        "can_claim_now": closure.get("can_claim_now") or [],
        "cannot_claim_yet": closure.get("cannot_claim_yet") or [],
    }


def _cycle_status(before: Dict[str, Any], after: Dict[str, Any], after_closure: Dict[str, Any]) -> str:
    if after.get("production_authorized"):
        return "production_authority_closed"
    if after.get("can_power_or_splice"):
        return "controlled_reuse_ready"
    if (after_closure.get("open_lane_count") or 0) < 1 and after_closure.get("available"):
        return "closure_complete_without_release_authority"
    if after.get("status") != before.get("status") or after.get("trust_score") != before.get("trust_score"):
        return "evidence_improved"
    return "still_open"


def _source_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    photo_set = payload.get("board_photo_set") if isinstance(payload.get("board_photo_set"), dict) else {}
    photo_observations = photo_set.get("photo_observations") if isinstance(photo_set.get("photo_observations"), list) else []
    return {
        "has_board_evidence": bool(payload.get("board_evidence") or photo_observations),
        "has_reference_topology": bool(payload.get("reference_topology")),
        "has_bench_capture": bool(payload.get("bench_topology_capture")),
        "has_outcome_history": bool(payload.get("outcome_history")),
        "has_release_manifest": bool(payload.get("production_release") or payload.get("release_manifest")),
        "photo_observation_count": len(photo_observations),
    }


def _delta(before: Any, after: Any) -> float | None:
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return None
    return round(float(after) - float(before), 3)


def _load_optional_rows(path: Path) -> List[Dict[str, Any]]:
    data = _load_any_json(path)
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict) and isinstance(data.get("outcome_history"), list):
        return [row for row in data["outcome_history"] if isinstance(row, dict)]
    return [data] if isinstance(data, dict) else []


def _load_json(path: Path) -> Dict[str, Any]:
    data = _load_any_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _load_any_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _relative_to_root(path: Path) -> Path | str:
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError:
        return path


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "closure_cycle"


def _default_cycle_id(args: argparse.Namespace) -> str:
    if args.case_json:
        return Path(args.case_json).stem
    if args.payload_json:
        return Path(args.payload_json).stem
    return "closure_cycle"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycle-id", default="")
    parser.add_argument("--case-json", default="", help="Real-board case JSON containing payload.")
    parser.add_argument("--payload-json", default="", help="Raw payload JSON or object with payload.")
    parser.add_argument("--board-evidence-json", default="")
    parser.add_argument("--reference-topology-json", default="")
    parser.add_argument("--bench-capture-json", default="")
    parser.add_argument("--outcome-json", default="")
    parser.add_argument("--production-release-json", default="")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--notes", default="")
    return parser


def main() -> int:
    report = run_closure_cycle_from_args(build_parser().parse_args())
    before = report["before"]
    after = report["after"]
    closure = report["closure_after"]
    print(f"cycle_id={report['cycle_id']} status={report['closed_loop']['status']}")
    print(
        "before="
        f"{before.get('status')} authorized={before.get('production_authorized')} "
        f"can_splice={before.get('can_power_or_splice')} trust={before.get('trust_score')}"
    )
    print(
        "after="
        f"{after.get('status')} authorized={after.get('production_authorized')} "
        f"can_splice={after.get('can_power_or_splice')} trust={after.get('trust_score')}"
    )
    print(
        f"closure_stage={closure.get('current_stage')} open_lanes={closure.get('open_lane_count')} "
        f"next_tasks={closure.get('next_best_task_count')}"
    )
    print(f"report={report['artifacts']['closure_cycle_report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
