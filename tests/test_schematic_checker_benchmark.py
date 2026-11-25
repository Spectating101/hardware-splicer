"""The benchmark checks a project from its root sheet, never from the sub-sheet a fix touched."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/schematic_checker_benchmark.py"


def _module():
    spec = importlib.util.spec_from_file_location("schematic_checker_benchmark", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_root_is_the_project_sheet_whose_hierarchy_holds_the_touched_sheet(tmp_path):
    bench = _module()
    for name in ("bitaxeUltra", "bitaxeMax"):
        (tmp_path / f"{name}.kicad_pro").write_text("{}")
    (tmp_path / "bitaxeUltra.kicad_sch").write_text('(kicad_sch (sheet (property "Sheetfile" "esp32.kicad_sch")))')
    (tmp_path / "bitaxeMax.kicad_sch").write_text('(kicad_sch (sheet (property "Sheetfile" "power.kicad_sch")))')
    (tmp_path / "esp32.kicad_sch").write_text("(kicad_sch)")
    assert bench.project_root(tmp_path, "esp32.kicad_sch").name == "bitaxeUltra.kicad_sch"
    assert bench.project_root(tmp_path, "power.kicad_sch").name == "bitaxeMax.kicad_sch"
    assert bench.project_root(tmp_path, "bitaxeMax.kicad_sch").name == "bitaxeMax.kicad_sch"


def test_a_folder_without_a_project_falls_back_to_the_given_sheet(tmp_path):
    (tmp_path / "board.kicad_sch").write_text("(kicad_sch)")
    assert _module().project_root(tmp_path, "board.kicad_sch") == tmp_path / "board.kicad_sch"
