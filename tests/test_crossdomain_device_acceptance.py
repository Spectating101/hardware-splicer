"""Cross-domain PCB/mechanical truth gates; fixtures are never native evidence."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.crossdomain_device_acceptance import (
    assess_crossdomain_reference, _source_shell_geometry,
)

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "hardware/reference_designs/spi_flash_adapter_v1"
RECIPE = ROOT / "examples/external_engines/cad/spi_adapter_shell.json"


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _run(tmp_path: Path, *, actual_box=None, actual_volume=None,
         alter_hash=False, alter_freecad_input=False) -> Path:
    output = tmp_path / "provider"
    (output / "shell_cad").mkdir(parents=True)
    (output / "shell_inspection").mkdir()
    recipe = RECIPE.read_bytes()
    shell = _source_shell_geometry(json.loads(recipe))
    step = b"ISO-10303-21;\nFAKE TEST STEP, NOT NATIVE CAD\nEND-ISO-10303-21;\n"
    measured = {
        "shape_valid": True,
        "solid_count": 1,
        "volume_mm3": (actual_volume if actual_volume is not None else
                       shell["nominal_shell_material_volume_mm3"]),
        "bbox_mm": actual_box if actual_box is not None else shell["outer_dimensions_mm"],
    }
    proof = json.dumps(measured).encode()
    (output / "shell_cad/model.step").write_bytes(step)
    (output / "shell_inspection/step_inspection.json").write_bytes(proof)
    report = {
        "schema": "hardware_splicer.external_engine_execution.v1",
        "plan_id": "spi_adapter_native_crossdomain_v1",
        "plan_sha256": _sha(b"mock_test_plan"),
        "completed": 2, "blocked": 0,
        "fabrication_authorized": False, "power_on_authorized": False,
        "release_authorized": False,
        "tasks": [
            {"id": "shell_cad", "engine": "solidcraft",
             "status": "tool_passed_artifact_observed",
             "source_sha256": _sha(recipe),
             "artifacts": [{"path": "shell_cad/model.step",
                            "sha256": _sha(step) if not alter_hash else _sha(b"wrong")}]},
            {"id": "shell_inspection", "engine": "freecad",
             "status": "tool_passed_artifact_observed",
             "source_sha256": _sha(step) if not alter_freecad_input else _sha(b"unrelated"),
             "artifacts": [{"path": "shell_inspection/step_inspection.json",
                            "sha256": _sha(proof)}]},
        ],
    }
    (output / "ENGINE_ORCHESTRATION_REPORT.json").write_text(json.dumps(report))
    return output


def _assess(tmp_path, provider=None, **kwargs):
    return assess_crossdomain_reference(
        pcb_path=kwargs.pop("pcb", REF / "spi_flash_adapter_v1.kicad_pcb"),
        receipt_path=kwargs.pop("receipt", REF / "verification.json"),
        cad_recipe_path=kwargs.pop("recipe", RECIPE),
        engine_output_dir=provider or _run(tmp_path),
        output_dir=tmp_path / "assessment",
    )


def test_shell_recipe_requires_real_boolean_cut_not_filled_block():
    source = json.loads(RECIPE.read_text())
    geom = _source_shell_geometry(source)
    assert geom["outer_dimensions_mm"] == [110, 70, 25]
    assert geom["nominal_cavity_dimensions_mm"] == [104, 64, 23]
    assert geom["floor_thickness_mm"] == 2
    assert abs(geom["nominal_shell_material_volume_mm3"] - 39412) < 1e-6
    solid = copy.deepcopy(source)
    solid["commands"][-1]["params"]["operation"] = "join"
    with pytest.raises(ValueError, match="subtract"):
        _source_shell_geometry(solid)


def test_frozen_spi_pcb_and_shell_are_consistent_on_software_envelope_only(tmp_path):
    report = _assess(tmp_path)
    assert report["status"] == "source_linked_envelope_clear_unverified", report["interface_screen"]
    assert report["electrical"]["board_size_mm"] == [90.0, 50.0, 1.6]
    assert report["electrical"]["historical_kicad_native_verification_bound"]
    assert report["interface_screen"]["blocker_count"] == 0
    assert report["electrical"]["native_erc_drc_reexecuted_in_this_run"] is False
    assert not report["fabrication_authorized"] and not report["power_on_authorized"]
    assert not report["mechanical"]["exact_3d_part_collision_verified"]
    assert (tmp_path/"assessment/CROSS_DOMAIN_DEVICE_ASSESSMENT.json").is_file()
    assert (tmp_path/"assessment/electrical/REFERENCE_ASSEMBLY_PLAN.json").is_file()


@pytest.mark.parametrize("mutate", [
    {"actual_box": [105, 70, 25]},
    {"actual_volume": 110*70*25},  # Filled block is not a hollow shell.
    {"alter_hash": True},
    {"alter_freecad_input": True},
])
def test_mismatched_cad_source_native_volume_or_hash_fails_closed(tmp_path, mutate):
    provider = _run(tmp_path, **mutate)
    with pytest.raises(ValueError):
        _assess(tmp_path, provider=provider)


def test_kicad_board_byte_mutation_invalidates_historical_receipt(tmp_path):
    pcb = tmp_path / "wrong.kicad_pcb"
    pcb.write_bytes((REF / "spi_flash_adapter_v1.kicad_pcb").read_bytes()+b"\n")
    with pytest.raises(ValueError, match="KiCad PCB changed"):
        _assess(tmp_path, pcb=pcb)


def test_source_recipe_mutation_cannot_pass_external_source_digest(tmp_path):
    path = tmp_path / "shell.json"
    s = json.loads(RECIPE.read_text())
    s["commands"][1]["params"]["p1"] = [112,70]
    path.write_text(json.dumps(s))
    with pytest.raises(ValueError, match="source recipe lineage"):
        _assess(tmp_path, recipe=path)


def test_restrict_cavity_dimensions_yields_explicit_fit_blocker(tmp_path):
    # Larger electronic PCB with unchanged frozen source cannot be claimed.
    # Instead exercise the screening engine's actual physical size blocking.
    from hardware_splicer.electromechanical_fit import screen_board_enclosure_fit
    large_board = {"source_mode": "test_declared",
                   "board": {"dimensions_mm": {"w": 90, "d": 50, "t": 1.6}},
                   "components": []}
    pocket = {"enclosure": {"inner_dimensions_mm": {"w": 85, "d": 64, "h": 23},
                            "floor_mm": 2},
              "placements": {"pcb": {"origin_xyz_mm": [0,0,6]}}}
    result = screen_board_enclosure_fit(large_board, pocket)
    assert result["status"] == "envelope_collision_detected"
    assert any(x["ref"] == "PCB" and x["axis"] == "x" and x["status"] == "block"
               for x in result["checks"])
