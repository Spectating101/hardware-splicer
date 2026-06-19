from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake
from hardware_splicer.splice_bench import (
    SESSION_FILE,
    bench_status,
    collect_bench_gates,
    open_bench_session,
    submit_bench_measurements,
)
from hardware_splicer.sdk import splice_bench_status, splice_bench_submit, splice_build

ROOT = Path(__file__).resolve().parents[1]
ROBOT_INTAKE = ROOT / "examples" / "intakes" / "splice_robot_drive_brief.json"
DONOR_FIXTURE = ROOT / "examples" / "fixtures" / "splice_donor_rc_motor_board.json"


def _write_minimal_bench_artifacts(tmp_path: Path) -> Path:
    donor = json.loads(DONOR_FIXTURE.read_text(encoding="utf-8"))
    intake = {
        "project_name": "bench_unit",
        "recommended_build_id": "robot_drive_base",
        "circuit": {
            "boards": [
                {
                    "board_id": "donor_rc_car_ctrl",
                    "functional_salvage": donor,
                }
            ]
        },
    }
    bringup = {
        "bench_checks": ["Verify VMOTOR before connecting logic harness"],
    }
    splice_plan = {
        "splice_plan": {
            "required_measurements": ["Measure VMOTOR at J_LOGIC"],
            "do_not_connect_until": ["Do not connect ESP32 until VMOTOR gate closes"],
        }
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "PROJECT_INTAKE.json").write_text(json.dumps(intake, indent=2), encoding="utf-8")
    (tmp_path / "BRINGUP_CARD.json").write_text(json.dumps(bringup, indent=2), encoding="utf-8")
    (tmp_path / "SPLICE_PLAN.json").write_text(json.dumps(splice_plan, indent=2), encoding="utf-8")
    return tmp_path


def test_collect_bench_gates_from_artifacts(tmp_path: Path) -> None:
    root = _write_minimal_bench_artifacts(tmp_path / "build")
    gates = collect_bench_gates(root)
    gate_ids = {row["gate_id"] for row in gates}
    assert "vmotor_rail" in gate_ids
    assert "bringup_1" in gate_ids
    assert any(row.get("critical") for row in gates)


def test_bench_submit_closes_gates_and_updates_readiness(tmp_path: Path) -> None:
    root = _write_minimal_bench_artifacts(tmp_path / "submit")
    session = open_bench_session(root)
    assert session["readiness"] == "bench_gates_open"
    assert session["critical_open_count"] >= 1

    critical_ids = [row["gate_id"] for row in session["gates"] if row.get("critical")]
    measurements = [
        {"gate_id": gate_id, "status": "closed", "value": 6.0, "unit": "V", "method": "DMM"}
        for gate_id in critical_ids
    ]
    updated = submit_bench_measurements(root, measurements)
    assert updated["critical_open_count"] == 0
    assert updated["power_on_authorized"] is True
    assert updated["readiness"] in {"ready_for_power_on", "bench_complete"}
    assert (root / SESSION_FILE).is_file()


def test_bench_status_persists_session(tmp_path: Path) -> None:
    root = _write_minimal_bench_artifacts(tmp_path / "status")
    first = bench_status(root)
    second = bench_status(root)
    assert first["gate_count"] == second["gate_count"]
    assert "open_gates" in second


def test_sdk_bench_wrappers(tmp_path: Path) -> None:
    root = _write_minimal_bench_artifacts(tmp_path / "sdk")
    status = splice_bench_status(root)
    assert status["schema_version"].startswith("hardware_splicer")
    submit = splice_bench_submit(
        root,
        [{"gate_id": "vmotor_rail", "status": "closed", "value": 6.1, "unit": "V"}],
    )
    assert submit["gate_count"] >= 1


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_splice_build_opens_bench_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    intake = load_project_intake(ROBOT_INTAKE)
    result = splice_build(intake, out_dir=tmp_path / "robot", export_gerber=False)
    bench = result.get("bench_session") or {}
    assert bench.get("session_path")
    assert Path(bench["session_path"]).is_file()
    assert bench.get("open_gate_count", 0) >= 1
    assert result["artifacts"].get("bench_session") == bench["session_path"]


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_splice_build_bench_submit_integration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")
    intake = load_project_intake(ROBOT_INTAKE)
    out = tmp_path / "robot_bench"
    splice_and_build_from_intake(intake, out_dir=out, export_gerber=False)
    session = bench_status(out)
    critical_open = [row for row in session.get("gates") or [] if row.get("critical") and row.get("status") != "closed"]
    assert critical_open
    measurements = [
        {"gate_id": row["gate_id"], "status": "closed", "value": 6.0, "unit": "V", "method": "DMM"}
        for row in critical_open
    ]
    updated = submit_bench_measurements(out, measurements)
    assert updated["critical_open_count"] == 0
    assert updated["power_on_authorized"] is True
