from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.splice_manifest import (
    evaluate_splice_case,
    get_splice_case,
    load_splice_manifest,
    run_and_evaluate_manifest,
    run_splice_case,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "splice" / "manifest.json"


def test_splice_manifest_loads_cases():
    manifest = load_splice_manifest(MANIFEST)
    assert manifest["schema_version"] == "hardware_splicer.splice_demo_manifest.v1"
    assert len(manifest["cases"]) >= 2
    robot = get_splice_case(manifest, "robot_drive_from_rc_toy")
    assert robot["expected_build_id"] == "robot_drive_base"


def test_robot_splice_case_evaluation_structure(tmp_path):
    manifest = load_splice_manifest(MANIFEST)
    case = get_splice_case(manifest, "robot_drive_from_rc_toy")
    splice_plan = tmp_path / "SPLICE_PLAN.json"
    kicad_pcb = tmp_path / "main.kicad_pcb"
    splice_plan.write_text("{}", encoding="utf-8")
    kicad_pcb.write_text("(kicad_pcb)", encoding="utf-8")
    metrics = {
        "build_id": "robot_drive_base",
        "circuit_backed_block_count": 3,
        "extractability_classes": ["connector_reuse", "board_section_cut_candidate"],
        "verdict": "ready_after_measurements",
        "drc_pass": True,
        "artifacts": {"splice_plan": str(splice_plan), "kicad_pcb": str(kicad_pcb)},
        "result_ok": False,
    }
    evaluation = evaluate_splice_case(metrics, case)
    assert evaluation["passed"] is True


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_verify_splice_manifest_robot_case(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    manifest = load_splice_manifest(MANIFEST)
    report = run_and_evaluate_manifest(
        manifest,
        out_root=tmp_path / "splice_verify",
        case_ids=["robot_drive_from_rc_toy"],
        export_gerber=False,
    )
    assert report["passed_count"] == 1
    assert report["all_passed"] is True
    case_row = report["cases"][0]
    assert case_row["evaluation"]["passed"] is True
    assert case_row["metrics"]["build_id"] == "robot_drive_base"
    assert case_row["metrics"]["circuit_backed_block_count"] >= 2
    assert Path(report["report_path"]).is_file()


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_verify_splice_manifest_printer_case(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    manifest = load_splice_manifest(MANIFEST)
    report = run_and_evaluate_manifest(
        manifest,
        out_root=tmp_path / "splice_verify_printer",
        case_ids=["printer_motion_stage"],
        export_gerber=False,
    )
    case_row = report["cases"][0]
    if not case_row["evaluation"]["passed"]:
        pytest.fail(json.dumps(case_row["evaluation"], indent=2))
    assert case_row["metrics"]["build_id"] == "plotter_motion_stage"
