from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.golden_intakes import golden_compile_cases
from hardware_splicer.project_intake import load_project_intake
from hardware_splicer.salvage_bridge import build_intake_salvage_package


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case", golden_compile_cases(), ids=lambda c: c["id"])
def test_golden_intake_compiles_drc_clean(case: dict, tmp_path: Path) -> None:
    intake_path: Path = case["intake_path"]
    assert intake_path.is_file(), f"missing intake: {intake_path}"

    intake = load_project_intake(intake_path)
    package = build_intake_salvage_package(
        goal=str(intake.get("goal") or ""),
        parts=list(intake.get("available_parts") or []),
        constraints=dict(intake.get("constraints") or {}),
        project_name=str(intake.get("project_name") or case["id"]),
    )

    expected_build_id = case["expected_build_id"]
    assert package.get("recommended_build_id") == expected_build_id, package

    if case.get("expected_power_topology"):
        assert package.get("power_topology") == case["expected_power_topology"]

    graph_input = package.get("graph_input") or {}
    result = compile_catalog_build(
        expected_build_id,
        tmp_path,
        export_gerber=False,
        splice_plan=graph_input,
        resolved_modules=list(package.get("resolved_modules") or []),
    )

    quality = result.design_quality
    assert quality.get("build_graph_compiled") is True, quality
    assert quality.get("electrical_safety_pass") is True, quality.get("electrical_issues")
    assert quality.get("drc_pass") is True, quality.get("drc_violations")
    assert result.ok is True, result.error
    assert result.kicad_pcb_file
    assert Path(result.kicad_pcb_file).is_file()

    graph = json.loads(Path(result.build_graph_file).read_text(encoding="utf-8"))
    assert len(graph.get("nodes") or []) >= int(case.get("min_modules") or 2)
    assert len(graph.get("wires") or []) >= int(case.get("min_wires") or 2)
