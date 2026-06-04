#!/usr/bin/env python3
"""Build a real-board corpus case from photos, board evidence, and bench capture.

This script is the repeatable intake step for a physical board session. It does
not invent measurements. If live Qwen is enabled it can create candidate visual
evidence from photos; production authority still requires explicit bench capture,
outcome, and release artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.intelligence.bench_topology_capture import build_bench_capture_template  # noqa: E402
from src.intelligence.hardware_plan import HardwarePlanOrchestrator  # noqa: E402
from src.intelligence.multiview_board_evidence import fuse_board_photo_set  # noqa: E402
from src.vision.qwen_board_vision import DEFAULT_MAX_TOKENS, analyze_board_image_with_qwen  # noqa: E402


DEFAULT_MANIFEST = ROOT / "data" / "real_board_corpus" / "manifest.local.json"
DEFAULT_OUTPUT_ROOT = ROOT / "data" / "real_board_corpus" / "cases"


def build_case_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    case_id = _safe_id(args.case_id)
    case_dir = Path(args.output_root) / case_id
    if case_dir.exists() and any(case_dir.iterdir()) and not args.force:
        raise FileExistsError(f"Case output already exists: {case_dir}. Pass --force to overwrite generated artifacts.")
    case_dir.mkdir(parents=True, exist_ok=True)

    photo_paths = [Path(path) for path in args.photo]
    board_evidence_paths = [Path(path) for path in args.board_evidence_json]
    reference_topology = _load_optional_json(args.reference_topology_json)
    bench_capture = _load_optional_json(args.bench_capture_json)
    outcome_history = _load_optional_rows(args.outcome_json)
    production_release = _load_optional_json(args.production_release_json)

    qwen_artifacts = _qwen_photo_artifacts(
        photo_paths,
        case_dir=case_dir,
        goal=args.goal,
        device_hint=args.device_hint,
        live=bool(args.live_qwen),
        max_tokens=args.max_tokens,
    )
    manual_evidence = [_load_json(path) for path in board_evidence_paths]
    photo_observations = _photo_observations(photo_paths, qwen_artifacts, manual_evidence)

    payload: Dict[str, Any] = {
        "goal": args.goal,
        "device_hint": args.device_hint,
        "strategy_mode": args.strategy_mode,
        "required_capabilities": args.required_capability,
        "use_reference_catalog": bool(args.use_reference_catalog),
    }
    if args.target_authority_level:
        payload["target_authority_level"] = args.target_authority_level
    if photo_observations:
        payload["board_photo_set"] = {"photo_observations": photo_observations}
    if reference_topology:
        payload["reference_topology"] = reference_topology
    if bench_capture:
        payload["bench_topology_capture"] = bench_capture
    if outcome_history:
        payload["outcome_history"] = outcome_history
    if production_release:
        payload["production_release"] = production_release

    reconstruction = fuse_board_photo_set(payload) if photo_observations else {}
    template = build_bench_capture_template(
        reference_topology=reference_topology or None,
        board_evidence=(reconstruction.get("board_evidence") if isinstance(reconstruction, dict) else None),
    )
    plan = HardwarePlanOrchestrator().plan(payload)
    actual = _actual_from_plan(plan)
    expected = _expected_from_actual(actual)
    generated_at = datetime.now(timezone.utc).isoformat()

    artifacts = {
        "payload": str(_relative_to_root(case_dir / "payload.json")),
        "hardware_plan": str(_relative_to_root(case_dir / "hardware_plan.json")),
        "bench_capture_template": str(_relative_to_root(case_dir / "bench_capture_template.json")),
        "multiview_reconstruction": str(_relative_to_root(case_dir / "multiview_reconstruction.json")),
        "qwen_results": [str(_relative_to_root(row["artifact_path"])) for row in qwen_artifacts if row.get("artifact_path")],
    }
    case = {
        "case_id": case_id,
        "title": args.title or case_id.replace("_", " "),
        "source": {
            "example_seed": False,
            "photo_uris": [str(_relative_to_root(path)) for path in photo_paths],
            "generated_by": "scripts/intake_real_board_case.py",
            "generated_at": generated_at,
            "artifacts": artifacts,
            "notes": args.notes or "",
        },
        "payload": payload,
        "expected": expected,
    }
    report = {
        "schema_version": "real_board_case_intake_report.v1",
        "generated_at": generated_at,
        "case_id": case_id,
        "case": case,
        "actual": actual,
        "capture_template_required": not bool(bench_capture),
        "qwen_live_used": bool(args.live_qwen),
        "qwen_artifact_count": len(qwen_artifacts),
        "claim_boundary": "Photos and Qwen evidence are candidate evidence only; production authority requires measured bench capture, terminal outcome, and release artifacts.",
    }

    _write_json(case_dir / "payload.json", payload)
    _write_json(case_dir / "hardware_plan.json", plan)
    _write_json(case_dir / "bench_capture_template.json", template)
    _write_json(case_dir / "multiview_reconstruction.json", reconstruction)
    _write_json(case_dir / "case.json", case)
    _write_json(case_dir / "intake_report.json", report)

    manifest_path = Path(args.manifest)
    if args.append_manifest:
        _upsert_manifest(manifest_path, case)
        report["manifest_updated"] = str(_relative_to_root(manifest_path))
    else:
        report["manifest_updated"] = ""
    _write_json(case_dir / "intake_report.json", report)
    return report


def _qwen_photo_artifacts(
    photo_paths: Sequence[Path],
    *,
    case_dir: Path,
    goal: str,
    device_hint: str,
    live: bool,
    max_tokens: int,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not live:
        return rows
    for index, path in enumerate(photo_paths, start=1):
        image_bytes = path.read_bytes()
        result = analyze_board_image_with_qwen(
            image_bytes,
            filename=path.name,
            goal=goal,
            device_hint=device_hint,
            live=True,
            max_tokens=max_tokens,
            ledger_path=case_dir / "qwen-spend-ledger.json",
        )
        artifact_path = case_dir / f"qwen_{index}_{_safe_id(path.stem)}.json"
        _write_json(artifact_path, result)
        rows.append({"photo_path": path, "artifact_path": artifact_path, "qwen_board_vision": result})
    return rows


def _photo_observations(
    photo_paths: Sequence[Path],
    qwen_artifacts: Sequence[Dict[str, Any]],
    manual_evidence: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    qwen_by_photo = {str(row.get("photo_path")): row for row in qwen_artifacts if row.get("photo_path")}
    max_count = max(len(photo_paths), len(manual_evidence), len(qwen_artifacts))
    for index in range(max_count):
        photo = photo_paths[index] if index < len(photo_paths) else None
        manual = manual_evidence[index] if index < len(manual_evidence) else {}
        qwen = qwen_by_photo.get(str(photo)) if photo else (qwen_artifacts[index] if index < len(qwen_artifacts) else {})
        evidence = _extract_board_evidence(manual) or _extract_board_evidence(qwen.get("qwen_board_vision") if isinstance(qwen, dict) else {})
        if not evidence:
            continue
        rows.append(
            {
                "photo_id": _safe_id(photo.stem if photo else f"evidence_{index + 1}"),
                "filename": str(_relative_to_root(photo)) if photo else "",
                "view_hint": _view_hint(photo, index),
                "provider": "qwen" if qwen else "manual",
                "qwen_board_vision": qwen.get("qwen_board_vision") if isinstance(qwen, dict) else {},
                "parse_diagnostics": (qwen.get("qwen_board_vision") or {}).get("parse_diagnostics") if isinstance(qwen, dict) else {},
                "board_evidence": evidence,
            }
        )
    return rows


def _extract_board_evidence(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    evidence = value.get("board_evidence") if isinstance(value.get("board_evidence"), dict) else value
    if str(evidence.get("schema_version") or "") == "board_evidence.v1":
        return evidence
    if any(isinstance(evidence.get(key), list) for key in ["components", "connectors", "markings", "damage", "test_points"]):
        return {"schema_version": "board_evidence.v1", **evidence}
    return {}


def _actual_from_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    integrated = plan.get("integrated_plan") if isinstance(plan.get("integrated_plan"), dict) else {}
    summary = analysis.get("hardware_plan_summary") if isinstance(analysis.get("hardware_plan_summary"), dict) else {}
    production = integrated.get("production_repair_authority") if isinstance(integrated.get("production_repair_authority"), dict) else {}
    if not production:
        production = summary.get("production_repair_authority") if isinstance(summary.get("production_repair_authority"), dict) else {}
    trust = analysis.get("arbitrary_board_trust_assessment") if isinstance(analysis.get("arbitrary_board_trust_assessment"), dict) else {}
    multiview = analysis.get("multiview_board_reconstruction") if isinstance(analysis.get("multiview_board_reconstruction"), dict) else {}
    capture_coverage = multiview.get("capture_coverage") if isinstance(multiview.get("capture_coverage"), dict) else {}
    return {
        "function": (analysis.get("board_function_inference") or {}).get("primary_function_id"),
        "status": integrated.get("status"),
        "trust_level": trust.get("level"),
        "trust_score": trust.get("score"),
        "production_readiness_score": trust.get("production_readiness_score"),
        "can_power_or_splice": (integrated.get("assurance") or {}).get("can_power_or_splice"),
        "production_authorized": bool(production.get("authorized")),
        "production_decision": production.get("decision"),
        "multiview_capture_coverage": {
            "available": bool(capture_coverage),
            "score": capture_coverage.get("score"),
            "required_complete": bool(capture_coverage.get("required_complete")),
            "open_required_lanes": capture_coverage.get("open_required_lanes") or [],
            "recommended_open_lanes": capture_coverage.get("recommended_open_lanes") or [],
        },
        "selected_resource_ids": integrated.get("selected_resource_ids") or [],
        "next_actions": integrated.get("next_actions") or [],
    }


def _expected_from_actual(actual: Dict[str, Any]) -> Dict[str, Any]:
    expected = {
        "function": actual.get("function"),
        "status": actual.get("status"),
        "trust_level": actual.get("trust_level"),
        "can_power_or_splice": bool(actual.get("can_power_or_splice")),
        "production_authorized": bool(actual.get("production_authorized")),
    }
    score = actual.get("production_readiness_score")
    if isinstance(score, (int, float)):
        if actual.get("production_authorized"):
            expected["min_production_readiness_score"] = round(max(0.0, float(score) - 0.02), 3)
        else:
            expected["max_production_readiness_score"] = round(min(1.0, float(score) + 0.02), 3)
    return expected


def _upsert_manifest(path: Path, case: Dict[str, Any]) -> None:
    manifest = _load_optional_json(path) or {
        "schema_version": "real_board_corpus.v1",
        "description": "Local real-board corpus generated by scripts/intake_real_board_case.py.",
        "cases": [],
    }
    cases = manifest.get("cases") if isinstance(manifest.get("cases"), list) else []
    cases = [row for row in cases if isinstance(row, dict) and row.get("case_id") != case.get("case_id")]
    cases.append(case)
    manifest["cases"] = cases
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, manifest)


def _load_optional_json(path: str | Path | None) -> Dict[str, Any]:
    if not path:
        return {}
    if not Path(path).exists():
        return {}
    return _load_json(Path(path))


def _load_optional_rows(path: str | Path | None) -> List[Dict[str, Any]]:
    if not path:
        return []
    data = _load_any_json(Path(path))
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


def _relative_to_root(path: Path | None) -> Path | str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError:
        return path


def _view_hint(path: Path | None, index: int) -> str:
    if path is None:
        return f"board evidence {index + 1}"
    name = path.stem.lower()
    if "front" in name or "top" in name:
        return "front or top board photo"
    if "back" in name or "bottom" in name:
        return "back or bottom board photo"
    if "close" in name or "marking" in name:
        return "close-up board photo"
    return "board photo"


def _safe_id(value: Any) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
    return safe[:90] or "real_board_case"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--device-hint", default="")
    parser.add_argument("--photo", action="append", default=[], help="Board photo path. Repeat for multiple views/closeups.")
    parser.add_argument("--board-evidence-json", action="append", default=[], help="board_evidence.v1 JSON path. Repeat to align with photos.")
    parser.add_argument("--reference-topology-json", default="")
    parser.add_argument("--bench-capture-json", default="")
    parser.add_argument("--outcome-json", default="")
    parser.add_argument("--production-release-json", default="")
    parser.add_argument("--required-capability", action="append", default=[])
    parser.add_argument("--strategy-mode", default="constrained", choices=["constrained", "hybrid", "procure"])
    parser.add_argument("--target-authority-level", default="")
    parser.add_argument("--use-reference-catalog", action="store_true")
    parser.add_argument("--live-qwen", action="store_true", help="Spend live Qwen vision calls for supplied photos.")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--append-manifest", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--notes", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = build_case_from_args(args)
    print(f"case_id={report['case_id']}")
    print(f"status={report['actual'].get('status')} function={report['actual'].get('function')}")
    print(
        "can_power_or_splice={can} production_authorized={prod}".format(
            can=report["actual"].get("can_power_or_splice"),
            prod=report["actual"].get("production_authorized"),
        )
    )
    print(f"case_artifact={Path(args.output_root) / report['case_id'] / 'case.json'}")
    if report.get("manifest_updated"):
        print(f"manifest_updated={report['manifest_updated']}")
    if report.get("capture_template_required"):
        print(f"bench_capture_template={Path(args.output_root) / report['case_id'] / 'bench_capture_template.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
