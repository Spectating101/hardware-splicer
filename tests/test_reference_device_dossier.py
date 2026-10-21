"""The actual KiCad reference-board bytes drive the assembly readiness dossier."""
import json
from pathlib import Path

from hardware_splicer.reference_device_dossier import build_reference_device_dossier

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"


def test_actual_reference_board_creates_traceable_assembly_and_open_gates(tmp_path):
    result = build_reference_device_dossier(REFERENCE, output_dir=tmp_path)
    assert result["source"]["sha256"].startswith("sha256:")
    assert result["board_size_mm"] == [90.0, 50.0, 1.6]
    assert result["footprints"] == 40
    assert result["fitted"] == 38
    assert result["assembly_steps"] > 0
    assert result["unverified_geometry_findings"]
    assert result["unresolved_gates"]
    assert not result["fabrication_authorized"]
    assert not result["release_authorized"]
    assert result["electromechanical_fit"] is None
    stored = json.loads((tmp_path / "REFERENCE_DEVICE_DOSSIER.json").read_text())
    plan = json.loads((tmp_path / "REFERENCE_ASSEMBLY_PLAN.json").read_text())
    assert stored == result
    assert plan["source"]["pcb_sha256"] == result["source"]["sha256"]


def test_declared_enclosure_may_block_but_never_approves(tmp_path):
    result = build_reference_device_dossier(
        REFERENCE, output_dir=tmp_path,
        declared_internal_enclosure_mm={"w": 50, "d": 40, "h": 9},
    )
    assert result["electromechanical_fit"]["status"] == "envelope_collision_detected"
    assert any(row["type"] == "enclosure_interference" for row in result["unresolved_gates"])
    assert not result["physical_assembly_complete"]


def test_declared_generous_enclosure_still_does_not_validate_source_parts(tmp_path):
    result = build_reference_device_dossier(
        REFERENCE, output_dir=tmp_path,
        declared_internal_enclosure_mm={"w": 125, "d": 85, "h": 60},
    )
    assert result["electromechanical_fit"]["status"] == "envelope_screen_clear_unverified"
    assert not result["source_manufacturer_specs_authenticated"]
    assert not result["bench_operation_verified"]
