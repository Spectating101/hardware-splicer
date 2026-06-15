"""KiCad 9 CLI DRC integration tests."""

from __future__ import annotations

import shutil

import pytest

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.pcb.kicad_cli_drc import run_kicad_cli_drc


@pytest.mark.skipif(not shutil.which("kicad-cli"), reason="kicad-cli required")
def test_emitted_pcb_loads_in_kicad_cli_drc(tmp_path) -> None:
    result = compile_catalog_build("sensor_logger", str(tmp_path))
    assert result.ok, result.quality
    pcb = result.kicad_pcb_file
    assert pcb

    report = run_kicad_cli_drc(pcb, out_dir=tmp_path / "drc")
    assert report.get("skipped") is not True
    assert report.get("reason") != "kicad-cli drc failed"
    assert report.get("kicad_version")
    assert isinstance(report.get("violations"), list)
