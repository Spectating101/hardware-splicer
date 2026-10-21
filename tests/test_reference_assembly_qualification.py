"""Real, source-file-bound PCB-to-assembly acceptance — no physical approval."""
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.reference_assembly_qualification import (
    qualify_source_board, write_reference_qualification,
)

BOARD = (
    Path(__file__).resolve().parents[1]
    / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
)


def qualify(*, w=140, d=100, h=60, standoff=8):
    return qualify_source_board(
        BOARD,
        inner_dimensions_mm={"w": w, "d": d, "h": h},
        standoff_mm=standoff,
    )


def test_reference_board_runs_source_assembly_and_3d_envelope_in_same_workflow():
    result = qualify()
    assert result["board_dimensions_mm"] == [90.0, 50.0, 1.6]
    assert result["footprints_total"] == 40
    assert result["footprints_fitted"] == 38
    assert result["footprints_not_fitted"] == 2
    assert result["assembly_step_count"] > 0
    assert result["component_envelope_count"] > 0
    assert result["source_board_sha256"] == "sha256:" + hashlib.sha256(BOARD.read_bytes()).hexdigest()
    assert result["assembly"]["source"]["pcb_sha256"] == result["source_board_sha256"]
    assert result["electromechanical_fit"]["schema"] == "hardware_splicer.electromechanical_envelope_fit.v1"
    assert result["fit_status"] == "envelope_screen_clear_unverified"
    assert result["fit_blocker_count"] == 0
    assert result["component_heights_source_authenticated"] is False
    assert result["electrical_function_verified"] is False
    assert result["fabrication_authorized"] is False
    assert result["release_authorized"] is False


def test_too_small_enclosure_is_rejected_by_actual_board_geometry():
    result = qualify(w=75, d=35, h=12)
    assert result["fit_status"] == "envelope_collision_detected"
    assert result["fit_blocker_count"] >= 2
    assert any(
        row["ref"] == "PCB" and row["status"] == "block"
        for row in result["electromechanical_fit"]["checks"]
    )
    assert result["fabrication_authorized"] is False


def test_mechanically_clear_source_does_not_fake_component_evidence():
    report = qualify()
    assert report["fitted_parts_missing_mpn_count"] >= 1
    assert sum(report["height_basis_counts"].values()) >= report["component_envelope_count"]
    assert report["cavity_dimensions_physically_measured"] is False
    assert report["exact_3d_collision_verified"] is False
    assert report["physical_build_completed"] is False


def test_source_bound_handoff_files_contain_unchecked_assembly_tasks(tmp_path):
    report = qualify()
    artifacts = write_reference_qualification(report, tmp_path / "reference")
    assert len(artifacts) == 4
    summary = json.loads(Path(artifacts["REFERENCE_QUALIFICATION.json"]).read_text())
    plan = json.loads(Path(artifacts["SOURCE_ASSEMBLY_PLAN.json"]).read_text())
    assert summary["source_board_sha256"] == report["source_board_sha256"]
    assert "assembly" not in summary
    assert len(plan["steps"]) == report["assembly_step_count"]
    checklist = Path(artifacts["BUILD_VALIDATION_CHECKLIST.md"]).read_text()
    assert "No physical measurement" in checklist
    assert "continuity" in checklist
    assert "- [ ]" in checklist
    assert "fabrication_authorized" not in checklist


def test_qualification_outputs_cannot_silently_overwrite_evidence(tmp_path):
    report = qualify()
    write_reference_qualification(report, tmp_path)
    with pytest.raises(FileExistsError):
        write_reference_qualification(report, tmp_path)


@pytest.mark.parametrize("bad", [float("nan"), -1, 0, True])
def test_invalid_enclosure_dimensions_fail_closed(bad):
    with pytest.raises((TypeError, ValueError)):
        qualify_source_board(BOARD, inner_dimensions_mm={"w": bad, "d": 100, "h": 60})
