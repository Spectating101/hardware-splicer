from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from hardware_splicer.fabrication_inspection import inspect_fabrication_package
from hardware_splicer.functional_delivery import build_functional_delivery_score
from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake


def test_inspection_flags_empty_pcb_as_bad(tmp_path):
    pcb = tmp_path / "empty.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20221018) (generator test))\n", encoding="utf-8")
    result = inspect_fabrication_package(
        build_compilation={"design_quality": {"drc_pass": True, "gerber_ready": True}, "kicad_pcb_file": str(pcb)},
        artifacts={},
    )
    assert result["inspection_score"] < 100
    assert result["honest_fabrication_ready"] is False
    assert any(row["id"] == "pcb_has_footprints" and not row["passed"] for row in result["checks"])


def test_inspection_catches_drc_claim_vs_empty_pcb(tmp_path):
    pcb = tmp_path / "empty.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20221018) (generator test))\n", encoding="utf-8")
    result = inspect_fabrication_package(
        build_compilation={
            "design_quality": {"drc_pass": True, "gerber_ready": False, "module_count": 5},
            "kicad_pcb_file": str(pcb),
        },
        artifacts={},
    )
    assert any(row["id"] == "drc_claim_matches_pcb" and not row["passed"] for row in result["checks"])


def test_functional_delivery_is_not_100_for_empty_pcb_claiming_pass(tmp_path):
    pcb = tmp_path / "empty.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20221018) (generator test))\n", encoding="utf-8")
    scorecard = build_functional_delivery_score(
        build_compilation={
            "design_quality": {
                "drc_pass": True,
                "electrical_safety_pass": True,
                "electrical_warnings": 0,
                "gerber_ready": True,
                "fabrication_ready": True,
                "build_graph_compiled": True,
                "module_count": 1,
                "board_outline": {"width_mm": 50, "height_mm": 50},
            },
            "kicad_pcb_file": str(pcb),
        },
        artifacts={"build_kicad_pcb": str(pcb), "fab_package_zip": str(_tiny_zip(tmp_path / "fab.zip"))},
    )
    assert scorecard["artifact_presence_score"] > 0
    assert scorecard["functional_delivery_score"] < scorecard["artifact_presence_score"]
    assert scorecard["honest_fabrication_ready"] is False


def test_real_plant_splice_uses_module_footprints_not_generic_headers(tmp_path):
    intake = load_project_intake(Path(__file__).resolve().parents[1] / "examples/intakes/plant_watering_brief.json")
    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "splice", export_gerber=True)
    scorecard = result["functional_delivery"]
    assert scorecard["prototype_breakout_only"] is False
    assert scorecard["honest_fabrication_ready"] is True
    assert scorecard["functional_delivery_score"] >= 90.0
    inspection = scorecard["fabrication_inspection"]
    # USB salvage brief: 4 modules (no 12V barrel / buck on the 5V bank path).
    assert inspection["pcb"]["footprint_count"] == 4
    assert inspection["pcb"]["generic_header_footprints"] == 0
    names = inspection["pcb"].get("footprint_names") or []
    assert any("ESP32" in name for name in names)
    assert any("USB" in name.upper() for name in names)
    assert all("PinHeader" not in name for name in names)
    assert all("BUCK" not in name.upper() for name in names)
    assert inspection["pcb"].get("has_fab_outlines") is True


def test_plant_pcb_has_module_footprints_and_fab_outlines(tmp_path):
    intake = load_project_intake(Path(__file__).resolve().parents[1] / "examples/intakes/plant_watering_brief.json")
    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "splice", export_gerber=False)
    pcb_path = Path(result["artifacts"]["kicad_pcb"])
    text = pcb_path.read_text(encoding="utf-8")
    assert "Connector:USB-MICRO-POWER" in text or "USB-MICRO" in text
    assert "Module:ESP32-WROOM-32" in text
    assert "BUCK-MP1584" not in text
    assert "fp_rect" in text
    assert result["build_compilation"]["design_quality"].get("drc_pass") is True


def _tiny_zip(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("gerbers/fake-F_Cu.gtl", "G04 fake\n" + ("X1Y1D02*\n" * 50))
        archive.writestr("gerbers/fake-Edge_Cuts.gm1", "G04 edge\n")
        archive.writestr("gerbers/fake.drl", "M48\n")
    return path
