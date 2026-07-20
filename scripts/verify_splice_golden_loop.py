#!/usr/bin/env python3
"""Verify splice golden loop: fixture S2, vision junk S3, repair-café S3."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.golden_loop import run_splice_golden_loop
from hardware_splicer.project_intake import load_project_intake


def _gate_ids(build_dir: Path) -> set[str]:
    session_path = build_dir / "SPLICE_BENCH_SESSION.json"
    if not session_path.is_file():
        return set()
    session = json.loads(session_path.read_text(encoding="utf-8"))
    return {str(row.get("gate_id") or "") for row in (session.get("gates") or []) if isinstance(row, dict)}


def _gate_status(build_dir: Path, gate_id: str) -> str:
    session_path = build_dir / "SPLICE_BENCH_SESSION.json"
    if not session_path.is_file():
        return ""
    session = json.loads(session_path.read_text(encoding="utf-8"))
    for row in session.get("gates") or []:
        if isinstance(row, dict) and str(row.get("gate_id") or "") == gate_id:
            return str(row.get("status") or "")
    return ""


def evaluate_case(case: Mapping[str, Any], intake: Mapping[str, Any], report: Dict[str, Any], out_dir: Path) -> List[str]:
    failures: List[str] = []
    if int(report.get("donor_vision_applied") or 0) < int(case.get("expect_vision") or 0):
        failures.append(
            f"donor_vision_applied {report.get('donor_vision_applied')} < {case.get('expect_vision')}"
        )
    if not report.get("passed"):
        failures.append("golden_loop report.passed is false")

    if case.get("expect_repair_context"):
        ctx = intake.get("repair_intake_context") if isinstance(intake.get("repair_intake_context"), dict) else {}
        if not ctx.get("symptoms"):
            failures.append("missing repair_intake_context.symptoms")
        if not str(ctx.get("when_it_fails") or "").strip():
            failures.append("missing repair_intake_context.when_it_fails")

    for gate_id in case.get("expect_standard_gates") or []:
        gate_id = str(gate_id)
        if gate_id not in _gate_ids(out_dir):
            failures.append(f"missing standard gate {gate_id}")
        elif case.get("simulate_bench") and _gate_status(out_dir, gate_id) != "closed":
            failures.append(f"gate {gate_id} not closed after simulated bench")

    if case.get("simulate_bench"):
        outcome = str(report.get("authorization_outcome") or "")
        if outcome not in {"authorized", "correctly_blocked"}:
            failures.append(f"unexpected authorization_outcome {outcome!r}")
        if not report.get("bench_workflow_passed"):
            failures.append("bench_workflow_passed false after simulated bench")
        if outcome == "correctly_blocked":
            if report.get("physical_authorized"):
                failures.append("correctly_blocked outcome cannot be physically authorized")
            if int(report.get("authority_gates_remaining") or 0) < 1:
                failures.append("correctly_blocked outcome missing authority gates")
        elif not report.get("bench_after", {}).get("power_on_authorized"):
            failures.append("authorized outcome missing power_on_authorized")

    intake_path = out_dir / "PROJECT_INTAKE.json"
    if intake_path.is_file() and case.get("expect_repair_context"):
        saved = json.loads(intake_path.read_text(encoding="utf-8"))
        notes = " ".join(saved.get("evidence_notes") or [])
        if "symptom:" not in notes:
            failures.append("PROJECT_INTAKE.json missing symptom evidence_notes")

    return failures


def main() -> int:
    if not shutil.which("node"):
        print("verify-splice-loop: SKIP (node not available)")
        return 0

    cases = [
        {
            "case_id": "robot_fixture_s2",
            "intake": ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json",
            "simulate_bench": False,
            "expect_vision": 0,
        },
        {
            "case_id": "robot_vision_junk_s3",
            "intake": ROOT / "examples" / "intakes" / "splice_robot_drive_vision_brief.json",
            "simulate_bench": True,
            "expect_vision": 1,
        },
        {
            "case_id": "robot_repair_cafe_s3",
            "intake": ROOT / "examples" / "intakes" / "splice_robot_drive_vision_repair_brief.json",
            "simulate_bench": True,
            "expect_vision": 1,
            "expect_repair_context": True,
            "expect_standard_gates": ["psu_current_limit_ramp", "thermal_baseline_scan"],
        },
    ]

    out_root = Path("/tmp/hs_splice_golden_verify")
    rows = []
    for case in cases:
        intake = load_project_intake(case["intake"])
        out_dir = out_root / str(case["case_id"])
        report = run_splice_golden_loop(
            intake,
            out_dir=out_dir,
            simulate_bench=bool(case["simulate_bench"]),
            request_id=str(case["case_id"]),
        )
        failures = evaluate_case(case, intake, report, out_dir)
        passed = not failures
        rows.append(
            {
                "case_id": case["case_id"],
                "passed": passed,
                "failures": failures,
                "report": report,
            }
        )

    passed_count = sum(1 for row in rows if row["passed"])
    summary = {
        "schema_version": "hardware_splicer.splice_golden_loop_verify.v1",
        "passed_count": passed_count,
        "total": len(rows),
        "all_passed": passed_count == len(rows),
        "cases": rows,
        "out_root": str(out_root),
    }
    out_root.mkdir(parents=True, exist_ok=True)
    report_path = out_root / "SPLICE_GOLDEN_LOOP_VERIFY.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Splice golden loop verify: {passed_count}/{len(rows)} passed")
    print(f"report: {report_path}")
    for row in rows:
        mark = "PASS" if row["passed"] else "FAIL"
        print(f"  [{mark}] {row['case_id']}")
        for failure in row.get("failures") or []:
            print(f"         - {failure}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
