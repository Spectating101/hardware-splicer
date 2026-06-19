"""Standard bench safety gates and repair-café intake."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.bench_capture_bridge import build_bench_capture_template_from_gates
from hardware_splicer.repair_intake import apply_repair_intake_context, extract_repair_context
from hardware_splicer.splice_bench import collect_bench_gates, open_bench_session
from hardware_splicer.standard_bench_gates import inject_standard_safety_gates

ROOT = Path(__file__).resolve().parents[1]


def test_inject_psu_and_thermal_gates_for_motor_salvage():
    gates = [{"gate_id": "vmotor", "prompt": "Measure VMOTOR", "gate_type": "voltage", "status": "open"}]
    intake = {"salvage_mode": True, "goal": "robot drive"}
    merged = inject_standard_safety_gates(gates, intake)
    ids = {row["gate_id"] for row in merged}
    assert "psu_current_limit_ramp" in ids
    assert "thermal_baseline_scan" in ids
    thermal = next(row for row in merged if row["gate_id"] == "thermal_baseline_scan")
    assert thermal["critical"] is False
    psu = next(row for row in merged if row["gate_id"] == "psu_current_limit_ramp")
    assert psu["gate_type"] == "psu_ramp"
    assert psu["critical"] is True


def test_repair_intake_merges_symptoms_into_evidence_notes():
    body = apply_repair_intake_context(
        {
            "repair_intake": {
                "symptoms": ["motors dead"],
                "when_it_fails": "on battery connect",
                "device_hint": "RC toy board",
            }
        }
    )
    notes = " ".join(body.get("evidence_notes") or [])
    assert "symptom: motors dead" in notes
    assert "when_it_fails: on battery connect" in notes
    assert body["donor_board_vision"]["device_hint"] == "RC toy board"
    assert body["repair_intake_context"]["symptoms"] == ["motors dead"]


def test_capture_template_includes_psu_ramp_fields(tmp_path: Path) -> None:
    gates = [
        {
            "gate_id": "psu_current_limit_ramp",
            "prompt": "Ramp VMOTOR with current-limited bench PSU",
            "gate_type": "psu_ramp",
            "status": "open",
        }
    ]
    template = build_bench_capture_template_from_gates(gates)
    row = template["measurements"][0]
    assert row["kind"] == "psu_ramp"
    assert row["current_limit_a"] == 0.5


def test_splice_session_includes_standard_gates(tmp_path: Path) -> None:
    intake = {
        "salvage_mode": True,
        "goal": "robot drive motor splice",
        "circuit": {
            "boards": [
                {
                    "board_id": "donor",
                    "functional_salvage": {
                        "reusable_blocks": [
                            {
                                "block_id": "motor_driver",
                                "name": "H-bridge motor driver",
                                "evidence_gates": [
                                    {"gate_id": "vmotor", "prompt": "Measure VMOTOR rail", "gate_type": "voltage"}
                                ],
                            }
                        ]
                    },
                }
            ]
        },
    }
    root = tmp_path / "bench"
    root.mkdir()
    (root / "PROJECT_INTAKE.json").write_text(json.dumps(intake, indent=2), encoding="utf-8")
    (root / "SPLICE_PLAN.json").write_text(json.dumps({"splice_plan": {}}, indent=2), encoding="utf-8")
    session = open_bench_session(root)
    gate_ids = {row["gate_id"] for row in session.get("gates") or []}
    assert "psu_current_limit_ramp" in gate_ids


def test_repair_brief_loads(tmp_path: Path) -> None:
    from hardware_splicer.project_intake import load_project_intake

    brief = ROOT / "examples" / "intakes" / "splice_robot_drive_vision_repair_brief.json"
    intake = load_project_intake(brief)
    ctx = extract_repair_context(intake)
    assert ctx["symptoms"]
    assert "battery connect" in ctx["when_it_fails"].lower()
