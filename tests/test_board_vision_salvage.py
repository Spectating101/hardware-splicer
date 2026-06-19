from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.board_vision_salvage import (
    board_evidence_to_functional_salvage,
    enrich_intake_with_donor_board_vision,
)
from hardware_splicer.project_intake import load_project_intake, plan_project_from_intake, splice_and_build_from_intake

ROOT = Path(__file__).resolve().parents[1]
BOARD_EVIDENCE = ROOT / "tests" / "data" / "board_evidence_rc_motor_donor.json"
VISION_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_vision_brief.json"
FIXTURE_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json"


def test_board_evidence_to_functional_salvage_rc_motor():
    evidence = json.loads(BOARD_EVIDENCE.read_text(encoding="utf-8"))
    salvage = board_evidence_to_functional_salvage(
        evidence,
        board_id="donor_rc_car_ctrl",
        goal="robot drive base",
        source_artifact=str(BOARD_EVIDENCE),
    )
    assert salvage["schema_version"] == "functional_salvage.v1"
    assert salvage["verdict"] == "ready_after_measurements"
    assert len(salvage["reusable_blocks"]) >= 2
    assert any("motor" in str(row.get("name") or "").lower() for row in salvage["reusable_blocks"])
    assert salvage["evidence_gates"]


def test_enrich_intake_applies_board_evidence_without_fixture():
    intake = load_project_intake(VISION_INTAKE)
    body, report = enrich_intake_with_donor_board_vision(intake)
    assert report["applied_board_count"] == 1
    board = body["circuit"]["boards"][0]
    fs = board.get("functional_salvage") or {}
    assert fs.get("source") == "board_vision"
    assert len(fs.get("reusable_blocks") or []) >= 2
    fixture_board = json.loads(FIXTURE_INTAKE.read_text(encoding="utf-8"))["circuit"]["boards"][0]
    assert "board_evidence" not in fixture_board


def test_plan_from_vision_intake_has_circuit_backed_blocks():
    intake = load_project_intake(VISION_INTAKE)
    plan = plan_project_from_intake(intake, skip_vision=True)
    splice_plan = (plan.get("salvage_package") or {}).get("splice_plan") or {}
    circuit_blocks = [
        row for row in (splice_plan.get("reusable_blocks") or []) if row.get("source") == "circuit_functional_salvage"
    ]
    assert len(circuit_blocks) >= 1
    assert plan.get("donor_board_vision_report", {}).get("applied_board_count") == 1


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_splice_build_from_vision_intake_without_static_fixture(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    intake = load_project_intake(VISION_INTAKE)
    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "vision_splice", export_gerber=False)
    assert result["build_id"] == "robot_drive_base"
    assert Path(result["artifacts"]["donor_board_vision_report"]).is_file()
    assert Path(result["artifacts"]["bench_capture_template"]).is_file()
    donor_report = json.loads(Path(result["artifacts"]["donor_board_vision_report"]).read_text(encoding="utf-8"))
    assert donor_report.get("applied_board_count") == 1
