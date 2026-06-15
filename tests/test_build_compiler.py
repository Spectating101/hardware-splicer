from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import (
    CATALOG_BUILD_IDS,
    apply_board_outline_to_machine,
    compile_catalog_build,
    resolve_build_id,
)
from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.production_release_metrics import build_production_release_metrics


ROOT = Path(__file__).resolve().parents[1]
COMPILE_SCRIPT = ROOT / "scripts" / "compile_build_graph.cjs"


@pytest.mark.parametrize("build_id", CATALOG_BUILD_IDS)
def test_catalog_build_compiles_drc_clean(build_id: str, tmp_path: Path) -> None:
    result = compile_catalog_build(build_id, tmp_path, export_gerber=False)
    assert result.design_quality_file
    quality = result.design_quality
    assert quality.get("build_graph_compiled") is True, quality
    assert quality.get("electrical_safety_pass") is True, quality.get("electrical_issues")
    assert quality.get("drc_pass") is True, quality.get("drc_violations")
    assert result.ok is True, result.error
    assert result.kicad_pcb_file
    kicad = Path(result.kicad_pcb_file)
    assert kicad.is_file()
    text = kicad.read_text(encoding="utf-8")
    assert text.startswith("(kicad_pcb")


def test_resolve_build_id_for_plant_watering() -> None:
    assert resolve_build_id(archetype="automatic_watering") == "automatic_plant_watering"


@pytest.mark.parametrize(
    "archetype,expected",
    [
        ("rover", "robot_drive_base"),
        ("pan_tilt", "inspection_motion_fixture"),
        ("airflow_controller", "usb_fume_extractor"),
        ("gripper", "low_voltage_motor_test_jig"),
    ],
)
def test_resolve_build_id_archetype_aliases(archetype: str, expected: str) -> None:
    assert resolve_build_id(archetype=archetype) == expected


@pytest.mark.skipif(not shutil.which("node") or not shutil.which("kicad-cli"), reason="node and kicad-cli required")
def test_gerber_export_when_kicad_cli_available(tmp_path: Path) -> None:
    result = compile_catalog_build("automatic_plant_watering", tmp_path, export_gerber=True)
    assert result.ok is True
    assert result.design_quality.get("gerber_ready") is True
    assert result.gerber_package_dir
    gerber_dir = Path(result.gerber_package_dir)
    assert gerber_dir.is_dir()
    assert (gerber_dir / "gerber_package.zip").is_file()
    assert any(gerber_dir.glob("*.gtl")) or any(gerber_dir.glob("*.gbr"))


def test_production_metrics_circuit_gate_requires_build_quality() -> None:
    result = {
        "ok": True,
        "engineering": {
            "build_compilation": {
                "design_quality": {
                    "build_id": "automatic_plant_watering",
                    "build_graph_compiled": True,
                    "build_ready": False,
                    "drc_pass": False,
                    "drc_errors": 2,
                    "electrical_safety_pass": True,
                },
                "design_quality_gate": {
                    "build_ready": False,
                    "design_quality_score": 0.4,
                    "blockers": ["DRC failed"],
                },
            }
        },
    }
    authority = {
        "dashboard": {},
        "mechatronics_authority": {
            "subsystems": {
                "circuit": {"release_ready": True, "board_design_file_count": 1, "readiness": "release_ready"},
            },
            "layer_closure": {"circuit_release_ready": True, "electrical_integration_ready": True},
        },
    }
    metrics = build_production_release_metrics(result=result, project_authority=authority)
    circuit_gate = next(row for row in metrics["weighted_gates"] if row["id"] == "circuit_release")
    assert circuit_gate["passed"] is False
    assert any("DRC" in blocker for blocker in circuit_gate["blockers"])


def test_design_quality_gate_blocks_draft_mismatch_without_compiler() -> None:
    gate = build_design_quality_gate(
        {
            "build_ready": True,
            "build_graph_compiled": False,
            "electrical_safety_pass": True,
            "drc_pass": False,
            "circuit_readiness": "build_ready",
        },
        engineering={"analysis": {"circuit": {"readiness_level": "draft"}}},
    )
    assert gate["build_ready"] is False
    assert gate["blockers"]


def test_design_quality_gate_trusts_compiler_verified_over_draft() -> None:
    gate = build_design_quality_gate(
        {
            "build_ready": True,
            "build_graph_compiled": True,
            "electrical_safety_pass": True,
            "drc_pass": True,
            "circuit_readiness": "build_ready",
        },
        engineering={"analysis": {"circuit": {"readiness_level": "draft"}}},
    )
    assert gate["compiler_verified"] is True
    assert gate["build_ready"] is True
    assert not any("draft" in blocker.lower() for blocker in gate["blockers"])


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_plant_watering_intake_emits_build_artifacts(tmp_path: Path) -> None:
    from hardware_splicer.project_intake import load_project_intake, run_project_intake

    brief = load_project_intake(ROOT / "examples" / "intakes" / "plant_watering_brief.json")
    result = run_project_intake(brief, out_dir=tmp_path, start_splicer=False)
    assert result.get("ok") is True
    quality_path = tmp_path / "DESIGN_QUALITY.json"
    gate_path = tmp_path / "DESIGN_QUALITY_GATE.json"
    assert quality_path.is_file(), "expected DESIGN_QUALITY.json from build compilation"
    assert gate_path.is_file(), "expected DESIGN_QUALITY_GATE.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    assert quality.get("build_id") == "automatic_plant_watering"
    assert quality.get("drc_pass") is True
    kicad = tmp_path / "build_compilation" / "main_ctrl_build.kicad_pcb"
    assert kicad.is_file()


def test_apply_board_outline_to_machine_updates_pcb_outline() -> None:
    machine = {"boards": [{"board_id": "main_ctrl"}]}
    updated = apply_board_outline_to_machine(
        machine,
        {"board_outline": {"width_mm": 92.5, "height_mm": 61.0}},
    )
    assert updated["boards"][0]["pcb_outline_mm"] == [92.5, 61.0, 1.6]


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
@pytest.mark.parametrize("build_id", CATALOG_BUILD_IDS)
def test_catalog_builds_have_zero_electrical_warnings(build_id: str, tmp_path: Path) -> None:
    result = compile_catalog_build(build_id, tmp_path, export_gerber=False)
    assert int(result.design_quality.get("electrical_warnings") or 0) == 0
    assert result.design_quality.get("build_ready") is True
