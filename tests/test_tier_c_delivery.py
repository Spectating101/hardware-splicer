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
    """Strict Tier C gate: each catalog package is valid, and honest only where every fit is verified.

    Footprint fit is an independent fabrication blocker (see tests/test_module_fit_gate.py): a build
    that uses a module whose footprint was never checked against the real part is not
    honest_fabrication_ready, and that must be the only thing standing in the way.
    """
    from hardware_splicer.functional_delivery import build_functional_delivery_score
    from hardware_splicer.pcb.fit_report import UNVERIFIED_FIT_BLOCKER_PREFIX

    monkeypatch.setenv("HARDWARE_SPLICER_AUTOROUTE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_JLC_ENRICH", "0")
    export_gerber = shutil.which("kicad-cli") is not None
    if not export_gerber:
        pytest.skip("kicad-cli required for honest_fabrication_ready gerber checks")
    other_blockers: list[str] = []
    wrong_verdict: list[str] = []
    for build_id in CATALOG_BUILD_IDS:
        target = tmp_path / build_id
        result = compile_catalog_build(build_id, target, export_gerber=export_gerber)
        scorecard = build_functional_delivery_score(build_compilation=result.to_dict())
        blockers = [str(b) for b in scorecard.get("blockers") or []]
        other = [b for b in blockers if not b.startswith(UNVERIFIED_FIT_BLOCKER_PREFIX)]
        if other:
            other_blockers.append(f"{build_id}: {other}")
        unverified = list(result.design_quality.get("unverified_fit_modules") or [])
        if bool(scorecard.get("honest_fabrication_ready")) != (not unverified and not other):
            wrong_verdict.append(f"{build_id}: unverified={unverified} honest={scorecard.get('honest_fabrication_ready')}")
    assert not other_blockers, "fabrication package problems besides footprint fit: " + "; ".join(other_blockers)
    assert not wrong_verdict, "honest_fabrication_ready disagrees with the fit record: " + "; ".join(wrong_verdict)
