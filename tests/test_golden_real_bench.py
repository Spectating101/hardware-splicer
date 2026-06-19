"""Golden real S3 — manual bench capture, not simulator."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.golden_real_bench import filter_capture_for_template, load_golden_bench_capture
from hardware_splicer.project_intake import load_project_intake

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PHOTO = ROOT / "tests" / "data" / "golden" / "rc_toy_motor_board.jpg"
GOLDEN_CAPTURE = ROOT / "tests" / "data" / "golden" / "rc_motor_manual_bench_capture.v1.json"
GOLDEN_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_golden_real_brief.json"


def test_golden_photo_and_capture_committed():
    assert GOLDEN_PHOTO.is_file()
    assert GOLDEN_PHOTO.stat().st_size > 100_000
    capture = load_golden_bench_capture(GOLDEN_CAPTURE)
    assert capture.get("simulated") is False
    assert capture.get("operator_id")
    assert len(capture.get("measurements") or []) >= 5


def test_filter_capture_matches_template():
    capture = load_golden_bench_capture(GOLDEN_CAPTURE)
    template = {
        "measurements": [
            {"gate_id": "bringup_1"},
            {"gate_id": "psu_current_limit_ramp"},
            {"gate_id": "missing_gate"},
        ]
    }
    filtered = filter_capture_for_template(capture, template)
    ids = {row["gate_id"] for row in filtered.get("measurements") or []}
    assert ids == {"bringup_1", "psu_current_limit_ramp"}


@pytest.mark.skipif(not shutil.which("node"), reason="node required for compile")
def test_golden_real_s3_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    from hardware_splicer.golden_real_bench import run_splice_golden_real

    intake = load_project_intake(GOLDEN_INTAKE)
    report = run_splice_golden_real(
        intake,
        out_dir=tmp_path / "golden_real",
        capture_path=GOLDEN_CAPTURE,
    )
    assert report.get("drc_pass") is True
    assert report.get("simulated") is False
    assert report.get("bench_after", {}).get("power_on_authorized") is True
    assert report.get("passed") is True
    body = json.loads((tmp_path / "golden_real" / "SPLICE_GOLDEN_REAL_REPORT.json").read_text(encoding="utf-8"))
    assert body.get("golden_photo_path")
