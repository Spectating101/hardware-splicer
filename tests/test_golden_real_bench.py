"""Golden real S3 — typed donor contract evidence plus manual bench capture."""

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
INTERFACE_ID = "if:donor-rc-car-ctrl:motor-driver-section"


def test_golden_photo_capture_and_contract_updates_committed():
    assert GOLDEN_PHOTO.is_file()
    assert GOLDEN_PHOTO.stat().st_size > 100_000
    capture = load_golden_bench_capture(GOLDEN_CAPTURE)
    assert capture.get("simulated") is False
    assert capture.get("operator_id")
    assert len(capture.get("measurements") or []) >= 10
    updates = capture.get("contract_updates") or []
    assert len(updates) >= 2
    assert updates[-1].get("interface_complete") is True
    assert {row.get("signal_id") for row in updates} >= {"motor_a_enable", "motor_b_enable"}
    evidence_measurements = {
        row.get("measurement_id")
        for row in capture.get("measurements") or []
        if row.get("interface_id") == INTERFACE_ID
    }
    assert evidence_measurements >= {
        "ground_resistance_ohm",
        "idle_voltage_v",
        "stimulus_voltage_v",
        "supply_current_a",
        "response_observed",
    }


def test_filter_capture_matches_direct_and_evidence_template_rows():
    capture = load_golden_bench_capture(GOLDEN_CAPTURE)
    template = {
        "measurements": [
            {"gate_id": "bringup_1"},
            {"gate_id": "psu_current_limit_ramp"},
            {
                "gate_id": "evidence_driver_measurement_ground_resistance_ohm",
                "interface_id": INTERFACE_ID,
                "measurement_id": "ground_resistance_ohm",
            },
            {"gate_id": "missing_gate"},
        ]
    }
    filtered = filter_capture_for_template(capture, template)
    ids = {row["gate_id"] for row in filtered.get("measurements") or []}
    assert ids == {
        "bringup_1",
        "psu_current_limit_ramp",
        "evidence_driver_measurement_ground_resistance_ohm",
    }
    ground = next(
        row
        for row in filtered.get("measurements") or []
        if row.get("measurement_id") == "ground_resistance_ohm"
    )
    assert ground["value"] == 0.7
    assert ground["unit"] == "ohm"


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
    assert report.get("contract_updates_ok") is True, report
    assert int(report.get("contract_update_count") or 0) >= 2
    assert report.get("firmware_authorized") is True, report
    assert int(report.get("matched_measurement_count") or 0) >= 10
    assert report.get("bench_after_contract", {}).get("power_on_authorized") is False
    assert report.get("bench_after", {}).get("power_on_authorized") is True, report
    assert report.get("open_gates") == []
    assert report.get("passed") is True

    body = json.loads(
        (tmp_path / "golden_real" / "SPLICE_GOLDEN_REAL_REPORT.json").read_text(encoding="utf-8")
    )
    assert body.get("golden_photo_path")
    assert body.get("contract_updates_ok") is True
    assert body.get("firmware_authorized") is True
