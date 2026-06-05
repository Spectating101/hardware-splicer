from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.robotics_platform_geometry import attach_robotics_platform_geometry
from hardware_splicer.runtime import SPLICER3D_VENV_PYTHON, ensure_circuit_import_path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "kicad_pcb_fixtures" / "kicad_demos_9_0_2" / "custom_pads_test.kicad_pcb"


def _cadquery_runtime_ready() -> bool:
    if not SPLICER3D_VENV_PYTHON.exists():
        return False
    proc = subprocess.run(
        [str(SPLICER3D_VENV_PYTHON), "-c", "import cadquery"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    return proc.returncode == 0


def test_kicad_fixture_generates_native_and_integrated_step_assembly(tmp_path):
    if not shutil.which("kicad-cli"):
        pytest.skip("kicad-cli is required for native KiCad STEP export")
    if not _cadquery_runtime_ready():
        pytest.skip("3D-Splicer CadQuery runtime is required for integrated STEP assembly export")

    body = {
        "project_name": "kicad_fixture_step_test",
        "board_design_files": {"fixture_board": {"path": str(FIXTURE), "kind": "pcb"}},
        "machine": {
            "boards": [
                {
                    "board_id": "fixture_board",
                    "name": "custom_pads_test",
                    "pcb_outline_mm": [118.0, 90.0, 1.6],
                    "mounts": [
                        {"id": "M1", "x_mm": 8.0, "y_mm": 8.0, "d_mm": 2.4},
                        {"id": "M2", "x_mm": 110.0, "y_mm": 82.0, "d_mm": 2.4},
                    ],
                    "capabilities": {"pwm_channels": 0, "stepper_channels": 0, "actuation_current_budget_a": 0.0},
                }
            ]
        },
        "mechanism": {
            "enclosure": {
                "name": "fixture_case",
                "inner_w_mm": 130.0,
                "inner_d_mm": 102.0,
                "inner_h_mm": 18.0,
                "wall_mm": 2.0,
                "floor_mm": 2.0,
                "lid_mm": 2.0,
                "clearance_mm": 0.5,
            }
        },
    }
    engineering = {"analysis": {"mechanism": {"outputs": [], "parts": [], "dfm": [], "simulation": [], "safety": []}}}

    ensure_circuit_import_path()
    result = attach_robotics_platform_geometry(body, engineering=engineering, out_dir=tmp_path)
    report_path = Path(result["artifacts"]["kicad_step_assembly_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    checks = {row["id"]: row for row in report["checks"]}

    assert report["assembly_ready"] is True
    assert report["mode"] == "kicad_cli_plus_cadquery_assembly"
    assert report["source_precision"] == "exact_kicad_pcb"
    assert report["placement"]["source_mode"] == "kicad_pcb_geometry"
    assert report["placement"]["component_count"] >= 1
    assert checks["kicad_board_step_export"]["status"] == "pass"
    assert checks["system_step_assembly"]["status"] == "pass"
    assert checks["board_outline_consistency"]["status"] == "pass"
    assert Path(result["artifacts"]["kicad_board_step_model"]).exists()
    assert Path(result["artifacts"]["kicad_step_assembly_model"]).exists()
