from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.build_evidence import enrich_compile_spec_from_build_compilation
from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.functional_delivery import build_functional_delivery_score
from hardware_splicer.production_release_metrics import build_production_release_metrics
from hardware_splicer.schemas import HardwareCompileSpec


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_plant_watering_functional_delivery_above_70(tmp_path: Path) -> None:
    result = compile_catalog_build("automatic_plant_watering", tmp_path, export_gerber=False)
    scorecard = build_functional_delivery_score(build_compilation=result.to_dict())
    assert scorecard["functional_delivery_score"] >= 70.0
    assert scorecard["checks_passed"] >= 8
    outline = result.design_quality.get("board_outline") or {}
    assert outline.get("width_mm")
    assert outline.get("height_mm")


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_enrich_spec_adds_compiler_evidence(tmp_path: Path) -> None:
    result = compile_catalog_build("automatic_plant_watering", tmp_path, export_gerber=False)
    spec = HardwareCompileSpec.from_dict(
        {
            "project_name": "plant",
            "machine": {"machine_name": "plant", "boards": [{"board_id": "main_ctrl"}]},
            "mechanism": {"mode": "prototype", "enclosure": {"inner_w_mm": 95, "inner_d_mm": 70}},
        }
    )
    enriched, payload = enrich_compile_spec_from_build_compilation(spec, result.to_dict(), tmp_path)
    assert enriched.circuit_release.get("compiler_verified") is True
    assert enriched.mechanical_measurement_capture.get("compiler_derived_envelope") is True
    width = enriched.machine["boards"][0]["pcb_outline_mm"][0]
    assert width > 0
    assert enriched.mechanism["enclosure"]["inner_w_mm"] >= width


def test_circuit_release_gate_passes_on_fabrication_ready() -> None:
    metrics = build_production_release_metrics(
        result={
            "ok": True,
            "engineering": {
                "build_compilation": {
                    "design_quality": {
                        "build_id": "automatic_plant_watering",
                        "build_graph_compiled": True,
                        "build_ready": True,
                        "fabrication_ready": True,
                        "drc_pass": True,
                        "electrical_safety_pass": True,
                        "electrical_warnings": 0,
                    }
                }
            },
        },
        project_authority={"project_authority_level": "control_safety_project_package", "claimable": True},
    )
    circuit_gate = next(row for row in metrics["weighted_gates"] if row["id"] == "circuit_release")
    assert circuit_gate["passed"] is True
    assert circuit_gate["score"] == 1.0
