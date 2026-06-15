from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.golden_intakes import golden_catalog_direct_cases


@pytest.mark.parametrize("case", golden_catalog_direct_cases(), ids=lambda c: c["id"])
def test_catalog_build_compiles_with_netlist_engine(case: dict, tmp_path: Path) -> None:
    build_id = str(case["build_id"])
    result = compile_catalog_build(build_id, tmp_path, export_gerber=False)
    quality = result.design_quality
    assert quality.get("build_graph_compiled") is True, quality
    assert quality.get("erc_pass") is True, quality.get("erc_report_path")
    assert quality.get("electrical_safety_pass") is True, quality.get("electrical_issues")
    assert quality.get("drc_pass") is True, quality.get("drc_violations")
    assert result.ok is True, result.error
    assert (tmp_path / "build_compilation" / "circuit_netlist.json").is_file()
    assert (tmp_path / "build_compilation" / "ERC.json").is_file()
