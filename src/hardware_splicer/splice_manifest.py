"""Splice demo manifest loading, execution metrics, and pass/fail evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from .project_intake import load_project_intake, splice_and_build_from_intake


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "examples" / "splice" / "manifest.json"
SCHEMA_VERSION = "hardware_splicer.splice_demo_result.v1"


def load_splice_manifest(path: str | Path | None = None) -> Dict[str, Any]:
    manifest_path = Path(path or DEFAULT_MANIFEST).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("splice manifest must be a JSON object")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("splice manifest must include a non-empty cases array")
    return data


def get_splice_case(manifest: Mapping[str, Any], case_id: str) -> Dict[str, Any]:
    for row in manifest.get("cases") or []:
        if isinstance(row, dict) and str(row.get("case_id") or "") == case_id:
            return dict(row)
    raise KeyError(f"unknown splice demo case_id: {case_id}")


def _extractability_classes(blocks: Sequence[Mapping[str, Any]]) -> List[str]:
    classes: List[str] = []
    for block in blocks:
        extractability = block.get("extractability") if isinstance(block.get("extractability"), dict) else {}
        value = str(extractability.get("class") or "").strip()
        if value and value not in classes:
            classes.append(value)
    return classes


def run_splice_case(
    case: Mapping[str, Any],
    *,
    out_dir: str | Path,
    export_gerber: bool = False,
) -> Dict[str, Any]:
    intake_path = REPO_ROOT / str(case["intake"])
    intake = load_project_intake(intake_path)
    result = splice_and_build_from_intake(
        intake,
        out_dir=Path(out_dir),
        export_gerber=bool(export_gerber),
        request_id=str(case.get("case_id") or "splice_case"),
    )
    salvage = result.get("salvage_package") or {}
    splice_plan = salvage.get("splice_plan") or {}
    reusable_blocks = list(splice_plan.get("reusable_blocks") or [])
    circuit_blocks = [row for row in reusable_blocks if row.get("source") == "circuit_functional_salvage"]
    quality = (result.get("build_compilation") or {}).get("design_quality") or {}
    functional_reuse = splice_plan.get("functional_reuse_plan") or {}
    verdict = str(salvage.get("verdict") or splice_plan.get("verdict") or "")
    return {
        "case_id": case.get("case_id"),
        "title": case.get("title"),
        "tier": case.get("tier"),
        "intake": str(intake_path),
        "out_dir": str(out_dir),
        "result_ok": bool(result.get("ok")),
        "build_id": result.get("build_id"),
        "expected_build_id": case.get("expected_build_id"),
        "graph_mode": salvage.get("graph_mode"),
        "verdict": verdict,
        "splice_readiness": functional_reuse.get("splice_readiness"),
        "circuit_backed_block_count": len(circuit_blocks),
        "extractability_classes": _extractability_classes(circuit_blocks),
        "drc_pass": bool(quality.get("drc_pass")),
        "build_ready": bool(quality.get("build_ready")),
        "electrical_errors": int(quality.get("electrical_errors") or 0),
        "artifacts": result.get("artifacts") or {},
        "splice_plan": splice_plan,
        "raw_result": result,
    }


def evaluate_splice_case(metrics: Mapping[str, Any], case: Mapping[str, Any]) -> Dict[str, Any]:
    failures: List[str] = []
    warnings: List[str] = []

    expected_build_id = str(case.get("expected_build_id") or "").strip()
    actual_build_id = str(metrics.get("build_id") or "").strip()
    if expected_build_id and actual_build_id != expected_build_id:
        failures.append(f"build_id mismatch: expected {expected_build_id}, got {actual_build_id or '(empty)'}")

    min_blocks = int(case.get("min_circuit_backed_blocks") or 0)
    block_count = int(metrics.get("circuit_backed_block_count") or 0)
    if block_count < min_blocks:
        failures.append(f"circuit_backed_blocks {block_count} < required {min_blocks}")

    required_classes = [str(item) for item in (case.get("required_extractability_classes") or []) if str(item).strip()]
    found_classes = set(metrics.get("extractability_classes") or [])
    missing_classes = [item for item in required_classes if item not in found_classes]
    if missing_classes:
        failures.append(f"missing extractability classes: {', '.join(missing_classes)}")

    expected_verdicts = {str(item) for item in (case.get("expected_verdicts") or []) if str(item).strip()}
    verdict = str(metrics.get("verdict") or "")
    if expected_verdicts and verdict not in expected_verdicts:
        failures.append(f"verdict {verdict!r} not in {sorted(expected_verdicts)}")

    splice_plan_path = (metrics.get("artifacts") or {}).get("splice_plan")
    if not splice_plan_path or not Path(str(splice_plan_path)).is_file():
        failures.append("missing SPLICE_PLAN artifact")

    if bool(case.get("requires_compile")):
        if not metrics.get("drc_pass"):
            failures.append("drc_pass is false")
        kicad_pcb = (metrics.get("artifacts") or {}).get("kicad_pcb")
        if not kicad_pcb or not Path(str(kicad_pcb)).is_file():
            failures.append("missing carrier KiCad PCB artifact")
        if not metrics.get("result_ok"):
            warnings.append("result_ok=false but compile metrics may still be acceptable for S2 (check drc_pass)")

    passed = not failures
    return {
        "case_id": case.get("case_id"),
        "passed": passed,
        "failures": failures,
        "warnings": warnings,
        "metrics": {
            "build_id": metrics.get("build_id"),
            "circuit_backed_block_count": metrics.get("circuit_backed_block_count"),
            "extractability_classes": metrics.get("extractability_classes"),
            "drc_pass": metrics.get("drc_pass"),
            "build_ready": metrics.get("build_ready"),
            "verdict": metrics.get("verdict"),
            "splice_readiness": metrics.get("splice_readiness"),
        },
    }


def run_and_evaluate_manifest(
    manifest: Mapping[str, Any],
    *,
    out_root: str | Path,
    case_ids: Sequence[str] | None = None,
    export_gerber: bool = False,
) -> Dict[str, Any]:
    out_root_path = Path(out_root)
    out_root_path.mkdir(parents=True, exist_ok=True)
    selected = list(case_ids or [str(row.get("case_id")) for row in manifest.get("cases") or [] if row.get("case_id")])
    case_rows = [get_splice_case(manifest, case_id) for case_id in selected]
    results: List[Dict[str, Any]] = []
    for case in case_rows:
        case_id = str(case["case_id"])
        metrics = run_splice_case(case, out_dir=out_root_path / case_id, export_gerber=export_gerber)
        evaluation = evaluate_splice_case(metrics, case)
        results.append(
            {
                "evaluation": evaluation,
                "metrics": {k: metrics[k] for k in metrics if k != "raw_result"},
                "out_dir": metrics.get("out_dir"),
            }
        )
    passed = sum(1 for row in results if row["evaluation"]["passed"])
    report = {
        "schema_version": SCHEMA_VERSION,
        "manifest_schema": manifest.get("schema_version"),
        "case_count": len(results),
        "passed_count": passed,
        "failed_count": len(results) - passed,
        "all_passed": passed == len(results),
        "cases": results,
    }
    report_path = out_root_path / "SPLICE_DEMO_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
