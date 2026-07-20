"""Tests for splice golden loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.golden_loop import build_simulated_capture, run_splice_golden_loop
from hardware_splicer.project_intake import load_project_intake

ROOT = Path(__file__).resolve().parents[1]
VISION_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_vision_brief.json"


def test_build_simulated_capture_marks_simulated():
    template = {
        "schema_version": "bench_topology_capture.v1",
        "measurements": [
            {"gate_id": "g1", "kind": "voltage", "target": "VMOTOR", "unit": "V"},
            {"gate_id": "g2", "kind": "continuity", "target": "harness"},
        ],
    }
    capture = build_simulated_capture(template)
    assert capture.get("simulated") is True
    assert len(capture.get("measurements") or []) == 2
    assert all(row.get("status") == "pass" for row in capture.get("measurements") or [])


@pytest.mark.skipif(not Path("/usr/bin/node").exists() and not Path("/usr/local/bin/node").exists(), reason="node required for compile")
def test_golden_loop_vision_junk(tmp_path: Path):
    intake = load_project_intake(VISION_INTAKE)
    report = run_splice_golden_loop(intake, out_dir=tmp_path / "loop", simulate_bench=True)
    assert report.get("drc_pass") is True
    assert int(report.get("donor_vision_applied") or 0) >= 1
    assert report["bench_after"].get("power_on_authorized") is False
    assert report.get("authorization_outcome") == "correctly_blocked"
    assert int(report.get("authority_gates_remaining") or 0) >= 1
    assert report.get("passed") is True
    report_path = tmp_path / "loop" / "SPLICE_GOLDEN_LOOP_REPORT.json"
    assert report_path.is_file()
    body = json.loads(report_path.read_text(encoding="utf-8"))
    assert body.get("schema_version") == "hardware_splicer.splice_golden_loop.v1"
