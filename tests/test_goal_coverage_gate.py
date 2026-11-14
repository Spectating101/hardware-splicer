"""A catalog scaffold picked by a fallback must not read as covering the stated goal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.project_intake import plan_project_from_intake, run_project_intake

CYBERDECK_GOAL = (
    "Engineer a self-contained Linux field-electronics cyberdeck with display, keyboard, USB access, "
    "offline documentation, remote access, a safe commercial USB-C power-bank supply, "
    "a realizable enclosure, under US$250"
)
BLOCKER = "goal_not_covered_by_selected_design"


def _ready_quality(**over: Any) -> Dict[str, Any]:
    quality: Dict[str, Any] = {
        "build_ready": True,
        "build_graph_compiled": True,
        "electrical_safety_pass": True,
        "drc_pass": True,
        "gerber_ready": True,
        "bom_ready": True,
        "fabrication_ready": True,
    }
    quality.update(over)
    return quality


def test_gate_blocks_when_goal_not_covered() -> None:
    gate = build_design_quality_gate(_ready_quality(goal_covered_by_selected_design=False))
    assert gate["build_ready"] is False
    assert gate["fabrication_ready"] is False
    assert gate["compiler_verified"] is False
    assert any(BLOCKER in row for row in gate["blockers"])


def test_gate_unchanged_when_goal_coverage_unknown_or_covered() -> None:
    assert build_design_quality_gate(_ready_quality())["build_ready"] is True
    assert build_design_quality_gate(_ready_quality(goal_covered_by_selected_design=True))["build_ready"] is True


def test_fallback_pick_for_unrelated_goal_is_flagged_uncovered() -> None:
    plan = plan_project_from_intake({"goal": CYBERDECK_GOAL})
    package = plan["salvage_package"]
    assert package["build_selection"]["source"] == "legacy_diy_planner"
    coverage = package["goal_coverage"]
    assert coverage["covered"] is False
    assert coverage["blocker"] == BLOCKER
    assert coverage["selected_build_id"] == "bench_power_adapter"
    compile_spec_bc = plan["scenario"]["compile_spec"]["build_compilation"]
    assert compile_spec_bc["goal_coverage"]["covered"] is False


def test_keyword_matched_goal_is_covered() -> None:
    plan = plan_project_from_intake({"goal": "Automatic plant watering with soil moisture sensor and pump"})
    package = plan["salvage_package"]
    assert package["build_selection"]["source"] == "legacy_keyword"
    assert package["goal_coverage"]["covered"] is True


def test_run_project_intake_cyberdeck_is_not_build_ready(tmp_path: Path, assume_clean_kicad_erc: None) -> None:
    # KiCad ERC is held clean so only the scaffold/goal mismatch can block readiness.
    result = run_project_intake({"goal": CYBERDECK_GOAL}, out_dir=tmp_path / "deck", start_splicer=False)
    gates = [
        result["project_authority"]["design_quality_gate"],
        result["production_release_metrics"]["design_quality_gate"],
        result["compile_result"]["engineering"]["build_compilation"]["design_quality_gate"],
    ]
    for gate in gates:
        assert gate["build_ready"] is False
        assert gate["fabrication_ready"] is False
        assert any(BLOCKER in row for row in gate["blockers"])
    on_disk = json.loads((tmp_path / "deck" / "DESIGN_QUALITY_GATE.json").read_text(encoding="utf-8"))
    assert on_disk["build_ready"] is False
    assert result["ok"] is False
