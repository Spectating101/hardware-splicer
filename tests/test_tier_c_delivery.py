"""Tier C: catalog BOMs must carry MPNs for honest fabrication."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from hardware_splicer.build_compiler import CATALOG_BUILD_IDS, compile_catalog_build

_TIER_C_BOM_BUILDS = (
    "room_display_station",
    "small_audio_amp_box",
    "camera_ir_light_or_sensor_mount",
    "plotter_motion_stage",
)


@pytest.mark.parametrize("build_id", _TIER_C_BOM_BUILDS)
def test_catalog_bom_lines_have_mpns(tmp_path: Path, build_id: str) -> None:
    result = compile_catalog_build(build_id, tmp_path / build_id, export_gerber=False)
    assert result.ok, result.error
    bom_path = tmp_path / build_id / "build_compilation" / "BOM.json"
    assert bom_path.is_file(), "BOM.json missing"
    bom = json.loads(bom_path.read_text(encoding="utf-8"))
    lines = list(bom.get("lines") or [])
    assert lines, "empty BOM"
    missing = [row.get("module_id") for row in lines if not str(row.get("mpn") or "").strip()]
    assert not missing, f"missing MPN for modules: {missing}"


def test_functional_audit_honest_fabrication_all_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Strict Tier C gate: every catalog build is honest_fabrication_ready."""
    from hardware_splicer.functional_delivery import build_functional_delivery_score

    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    export_gerber = shutil.which("kicad-cli") is not None
    if not export_gerber:
        pytest.skip("kicad-cli required for honest_fabrication_ready gerber checks")
    not_honest: list[str] = []
    for build_id in CATALOG_BUILD_IDS:
        target = tmp_path / build_id
        result = compile_catalog_build(build_id, target, export_gerber=export_gerber)
        scorecard = build_functional_delivery_score(build_compilation=result.to_dict())
        if not scorecard.get("honest_fabrication_ready"):
            not_honest.append(f"{build_id}: {scorecard.get('blockers')}")
    assert not not_honest, "not honest_fabrication_ready: " + "; ".join(not_honest)
