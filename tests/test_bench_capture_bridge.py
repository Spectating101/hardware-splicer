from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.bench_capture_bridge import (
    bench_capture_to_splice_measurements,
    build_bench_capture_template_from_gates,
    collect_capture_measurements,
    submit_bench_capture,
)
from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake
from hardware_splicer.sdk import vision_capabilities, vision_enrich_intake
from hardware_splicer.splice_bench import open_bench_session

ROOT = Path(__file__).resolve().parents[1]
ROBOT_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json"
DONOR_FIXTURE = ROOT / "examples" / "fixtures" / "splice_donor_rc_motor_board.json"


def _minimal_build(tmp_path: Path) -> Path:
    donor = json.loads(DONOR_FIXTURE.read_text(encoding="utf-8"))
    root = tmp_path / "build"
    intake = {
        "project_name": "bridge_unit",
        "circuit": {"boards": [{"board_id": "donor_rc_car_ctrl", "functional_salvage": donor}]},
    }
    splice_plan = {"splice_plan": {"required_measurements": ["Measure VMOTOR at J_LOGIC"]}}
    root.mkdir(parents=True, exist_ok=True)
    (root / "PROJECT_INTAKE.json").write_text(json.dumps(intake, indent=2), encoding="utf-8")
    (root / "SPLICE_PLAN.json").write_text(json.dumps(splice_plan, indent=2), encoding="utf-8")
    open_bench_session(root)
    return root


def test_collect_capture_measurements():
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "measurements": [
            {"kind": "voltage", "target": "VMOTOR at J_LOGIC", "value": 6.0, "unit": "V", "status": "pass"},
            {"kind": "continuity", "target": "motor harness pairs", "value": "pass", "status": "pass"},
        ],
    }
    rows = collect_capture_measurements(capture)
    assert len(rows) == 2


def test_build_bench_capture_template_from_gates():
    gates = [
        {"gate_id": "vmotor_rail", "prompt": "Measure VMOTOR", "gate_type": "voltage", "status": "open"},
        {"gate_id": "done_gate", "prompt": "Already closed", "status": "closed"},
    ]
    template = build_bench_capture_template_from_gates(gates, project_name="robot")
    assert template["schema_version"] == "bench_topology_capture.v1"
    assert len(template["measurements"]) == 1
    assert template["measurements"][0]["gate_id"] == "vmotor_rail"


def test_splice_build_writes_capture_template(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    intake = load_project_intake(ROBOT_INTAKE)
    out = tmp_path / "robot_template"
    splice_and_build_from_intake(intake, out_dir=out, export_gerber=False)
    template_path = out / "BENCH_CAPTURE_TEMPLATE.json"
    assert template_path.is_file()
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert template["schema_version"] == "bench_topology_capture.v1"
    assert len(template.get("measurements") or []) >= 1
    assert (out / "VISION_EVIDENCE_REPORT.json").is_file()


def test_bench_capture_maps_to_splice_gates(tmp_path: Path) -> None:
    root = _minimal_build(tmp_path)
    session = open_bench_session(root)
    capture = {
        "schema_version": "bench_topology_capture.v1",
        "operator_id": "bench_rig_01",
        "instrument_id": "bench_dmm_01",
        "measurements": [
            {
                "gate_id": "vmotor_rail",
                "kind": "voltage",
                "target": "VMOTOR",
                "value": 6.0,
                "unit": "V",
                "status": "pass",
                "instrument_id": "bench_dmm_01",
            },
            {
                "gate_id": "motor_harness_continuity",
                "kind": "continuity",
                "target": "motor harness",
                "value": "pass",
                "status": "verified",
            },
        ],
    }
    mapped = bench_capture_to_splice_measurements(capture, gates=session["gates"])
    assert len(mapped) == 2
    result = submit_bench_capture(str(root), capture)
    assert result["ok"] is True
    assert result["mapped_count"] == 2
    closed_ids = {row["gate_id"] for row in result["bench_session"].get("closed_gates") or []}
    assert "vmotor_rail" in closed_ids
    assert "motor_harness_continuity" in closed_ids


def test_vision_capabilities_inventory():
    caps = vision_capabilities()
    assert "hardware_splicer" in caps
    assert "circuit_ai" in caps
    assert "splice_robot_drive_vision_brief.json" in caps["hardware_splicer"]["example_vision_splice_intake"]


def test_vision_enrich_intake_offline():
    intake = {
        "project_name": "offline_vision",
        "attachments": [{"id": "photo", "kind": "image", "path": "assets/plant_bench_reference.png"}],
    }
    result = vision_enrich_intake(intake, live=False)
    report = result["vision_evidence_report"]
    assert report.get("schema_version", "").startswith("hardware_splicer.vision")
    assert "evidence_extraction_report" in result
