"""KiCad ERC/DRC results must gate build readiness and trust, never be ignored."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from hardware_splicer.build_compiler import compile_catalog_build
from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.trust_report import build_trust_report

SIM = {"simulation_pass": True, "skipped": False, "power_budget": {"estimated_load_a": 0.4, "margin_a": 0.5}}


def _clean_quality(**over: Any) -> Dict[str, Any]:
    quality: Dict[str, Any] = {
        "build_ready": True,
        "build_graph_compiled": True,
        "electrical_safety_pass": True,
        "drc_pass": True,
        "kicad_drc_pass": True,
        "kicad_drc_errors": 0,
        "erc_pass": True,
        "kicad_erc_pass": True,
        "kicad_erc_errors": 0,
        "bom_ready": True,
        "gerber_ready": True,
    }
    quality.update(over)
    return quality


def test_trust_report_fully_clean_is_build_trusted() -> None:
    report = build_trust_report(design_quality=_clean_quality(), simulation=SIM, build_id="x")
    assert report["trust_level"] == "build_trusted"
    assert report["trust_score"] == 1.0
    assert report["gates"]["kicad_erc_available"] is True
    assert report["gates"]["kicad_erc_pass"] is True


def test_trust_report_kicad_erc_failure_blocks_trust() -> None:
    quality = _clean_quality(kicad_erc_pass=False, kicad_erc_errors=2)
    report = build_trust_report(design_quality=quality, simulation=SIM, build_id="x")
    assert report["trust_level"] != "build_trusted"
    assert report["trust_level"] == "blocked"
    assert report["trust_score"] < 1.0
    assert report["gates"]["kicad_erc_pass"] is False
    assert report["design_quality"]["build_ready"] is False
    assert any("KiCad ERC" in row and "2" in row for row in report["blockers"])
    assert "KiCad ERC" in report["summary_markdown"]


@pytest.mark.parametrize("missing", [{"kicad_erc_pass": None, "kicad_erc_skipped": True}, {"kicad_erc_pass": None}])
def test_trust_report_kicad_erc_unavailable_is_not_a_pass(missing: Dict[str, Any]) -> None:
    quality = _clean_quality(**missing)
    report = build_trust_report(design_quality=quality, simulation=SIM, build_id="x")
    assert report["gates"]["kicad_erc_available"] is False
    assert report["gates"]["kicad_erc_pass"] is False
    assert report["trust_level"] != "build_trusted"
    assert report["trust_score"] < 1.0
    assert any("KiCad ERC was not available" in row for row in report["blockers"])
    assert "no verification claim made" in report["summary_markdown"].lower()


def test_trust_report_kicad_drc_failure_marks_build_not_ready() -> None:
    quality = _clean_quality(kicad_drc_pass=False, kicad_drc_errors=3)
    report = build_trust_report(design_quality=quality, simulation=SIM, build_id="x")
    assert report["trust_level"] == "blocked"
    assert report["design_quality"]["build_ready"] is False
    assert any("KiCad DRC has 3" in row for row in report["blockers"])


def test_design_quality_gate_blocks_on_kicad_erc_failure() -> None:
    gate = build_design_quality_gate(_clean_quality(kicad_erc_pass=False, kicad_erc_errors=2))
    assert gate["build_ready"] is False
    assert gate["fabrication_ready"] is False
    assert any("KiCad ERC" in row for row in gate["blockers"])


def test_design_quality_gate_blocks_on_kicad_drc_failure() -> None:
    gate = build_design_quality_gate(_clean_quality(kicad_drc_pass=False, kicad_drc_errors=4))
    assert gate["build_ready"] is False
    assert any("KiCad DRC" in row for row in gate["blockers"])


def test_design_quality_gate_clean_kicad_still_ready() -> None:
    gate = build_design_quality_gate(_clean_quality())
    assert gate["build_ready"] is True
    assert not any("KiCad" in row for row in gate["blockers"])


def test_compile_with_failing_kicad_erc_is_not_build_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hardware_splicer.netlist.compile.run_kicad_cli_erc",
        lambda *a, **k: {"pass": False, "skipped": False, "errors": 2, "warnings": 0, "violations": [], "report_path": None},
    )
    result = compile_catalog_build("sensor_logger", tmp_path, export_gerber=False)
    assert result.design_quality.get("kicad_erc_pass") is False
    assert result.design_quality.get("build_ready") is False
    gate = build_design_quality_gate(result.design_quality)
    assert gate["build_ready"] is False
    trust = json.loads((tmp_path / "build_compilation" / "TRUST_REPORT.json").read_text(encoding="utf-8"))
    assert trust["trust_level"] != "build_trusted"
    assert trust["design_quality"]["build_ready"] is False
    assert any("KiCad ERC" in row for row in trust["blockers"])


def test_compile_with_unavailable_kicad_erc_is_not_trusted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hardware_splicer.netlist.compile.run_kicad_cli_erc",
        lambda *a, **k: {"pass": None, "skipped": True, "reason": "kicad-cli not on PATH", "errors": 0, "warnings": 0, "violations": []},
    )
    compile_catalog_build("sensor_logger", tmp_path, export_gerber=False)
    trust = json.loads((tmp_path / "build_compilation" / "TRUST_REPORT.json").read_text(encoding="utf-8"))
    assert trust["trust_level"] != "build_trusted"
    assert trust["gates"]["kicad_erc_pass"] is False
    assert any("KiCad ERC was not available" in row for row in trust["blockers"])
