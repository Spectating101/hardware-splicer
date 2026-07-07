"""KiCad sidecar recheck after human edits."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hardware_splicer.kicad_sidecar_recheck import recheck_build_after_kicad_edit


def test_recheck_updates_quality_and_drc(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    pcb = comp / "demo.kicad_pcb"
    sch = comp / "demo.kicad_sch"
    pcb.write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    sch.write_text("(kicad_sch (version 20230121))\n", encoding="utf-8")
    (comp / "DESIGN_QUALITY.json").write_text(json.dumps({"build_id": "test"}), encoding="utf-8")

    drc_report = {"pass": True, "skipped": False, "errors": 0, "warnings": 1, "violations": []}
    erc_report = {"pass": True, "skipped": False, "errors": 0, "warnings": 0, "violations": []}

    with (
        patch("hardware_splicer.kicad_sidecar_recheck.run_kicad_cli_drc", return_value=drc_report),
        patch("hardware_splicer.kicad_sidecar_recheck.run_kicad_cli_erc", return_value=erc_report),
        patch("hardware_splicer.pcb.kicad_cli_views.export_human_views", return_value={"ok": True, "present_count": 0}),
        patch("hardware_splicer.sdk.render_project_package", return_value={"ok": True}),
    ):
        result = recheck_build_after_kicad_edit(tmp_path, source="test")

    assert result["ok"] is True
    assert result["drc"]["pass"] is True
    quality = json.loads((comp / "DESIGN_QUALITY.json").read_text(encoding="utf-8"))
    assert quality["kicad_drc_pass"] is True
    assert quality["kicad_sidecar_source"] == "test"
    assert (comp / "KICAD_DRC.json").is_file()


def test_recheck_requires_pcb(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    with pytest.raises(ValueError, match="no .kicad_pcb"):
        recheck_build_after_kicad_edit(tmp_path)
