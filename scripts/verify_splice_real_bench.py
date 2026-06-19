#!/usr/bin/env python3
"""Verify golden real S3: real photo + manual bench capture (not simulator)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.golden_real_bench import load_golden_bench_capture, run_splice_golden_real
from hardware_splicer.project_intake import load_project_intake

GOLDEN_PHOTO = ROOT / "tests" / "data" / "golden" / "rc_toy_motor_board.jpg"
GOLDEN_CAPTURE = ROOT / "tests" / "data" / "golden" / "rc_motor_manual_bench_capture.v1.json"


def main() -> int:
    if not shutil.which("node"):
        print("verify-splice-real-bench: SKIP (node not available)")
        return 0

    failures: list[str] = []
    if not GOLDEN_PHOTO.is_file():
        failures.append(f"missing golden photo: {GOLDEN_PHOTO}")
    if not GOLDEN_CAPTURE.is_file():
        failures.append(f"missing golden capture: {GOLDEN_CAPTURE}")
    else:
        capture = load_golden_bench_capture(GOLDEN_CAPTURE)
        if capture.get("simulated"):
            failures.append("golden capture must have simulated:false")
        if not str(capture.get("operator_id") or "").strip():
            failures.append("golden capture missing operator_id")

    if failures:
        for item in failures:
            print(f"FAIL: {item}")
        return 1

    intake = load_project_intake(ROOT / "examples" / "intakes" / "splice_robot_drive_golden_real_brief.json")
    out_dir = Path("/tmp/hs_splice_golden_real_verify")
    report = run_splice_golden_real(
        intake,
        out_dir=out_dir,
        capture_path=GOLDEN_CAPTURE,
        request_id="golden_real_s3",
    )

    if not report.get("passed"):
        failures.append("golden real report.passed is false")
    if report.get("simulated"):
        failures.append("report marked simulated")
    if int(report.get("matched_measurement_count") or 0) < 5:
        failures.append(f"too few matched measurements: {report.get('matched_measurement_count')}")

    summary = {
        "schema_version": "hardware_splicer.splice_golden_real_verify.v1",
        "passed": not failures,
        "failures": failures,
        "report": report,
        "golden_photo": str(GOLDEN_PHOTO),
        "golden_capture": str(GOLDEN_CAPTURE),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "SPLICE_GOLDEN_REAL_VERIFY.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    mark = "PASS" if not failures else "FAIL"
    print(f"Golden real S3 verify: {mark}")
    print(f"  photo: {GOLDEN_PHOTO.name} ({GOLDEN_PHOTO.stat().st_size // 1024} KB)")
    print(f"  capture: {GOLDEN_CAPTURE.name} operator={load_golden_bench_capture(GOLDEN_CAPTURE).get('operator_id')}")
    print(f"  power_on_authorized={report.get('bench_after', {}).get('power_on_authorized')}")
    print(f"  report: {path}")
    for item in failures:
        print(f"  - {item}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
