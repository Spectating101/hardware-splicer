from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.project_intake import (
    load_project_intake,
    plan_project_from_intake,
    run_project_intake,
    splice_and_build_from_intake,
)
from hardware_splicer.scoring_summary import scorecard_from_artifacts


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "brief_rel,expected_gates",
    [
        ("examples/intakes/plant_watering_evidence_pack.json", 9),
        ("examples/intakes/plant_watering_tier5_brief.json", 9),
    ],
)
def test_plant_release_briefs_hit_nine_of_nine_gates(tmp_path, brief_rel, expected_gates):
    intake = load_project_intake(ROOT / brief_rel)
    vision = dict(intake.get("vision_assistance") or {})
    vision["live"] = False
    intake["vision_assistance"] = vision
    run_project_intake(intake, out_dir=tmp_path / "intake", start_splicer=False)
    card = scorecard_from_artifacts(tmp_path / "intake")
    assert int(card.get("gates_passed") or 0) >= expected_gates
    assert float(card.get("production_readiness_score") or 0) >= 0.99


def test_annotated_vision_brief_closes_more_mechanical_evidence_than_brief_only(tmp_path):
    brief_only = load_project_intake(ROOT / "examples/intakes/plant_watering_brief.json")
    annotated = load_project_intake(ROOT / "examples/intakes/plant_watering_vision_annotated_brief.json")
    brief_plan = plan_project_from_intake(brief_only, skip_vision=True)
    annotated_plan = plan_project_from_intake(annotated, skip_vision=True)
    brief_measurements = bool((brief_plan.get("evidence_summary") or {}).get("has_measurements"))
    annotated_measurements = bool((annotated_plan.get("evidence_summary") or {}).get("has_measurements"))
    assert annotated_measurements and not brief_measurements
    assert annotated_plan["evidence_extraction_report"]["accepted_count"] >= 3


def test_splice_and_build_emits_compiler_evidence_patch(tmp_path):
    intake = load_project_intake(ROOT / "examples/intakes/plant_watering_brief.json")
    result = splice_and_build_from_intake(intake, out_dir=tmp_path / "splice", export_gerber=False)
    assert result.get("ok")
    patch = result.get("compiler_evidence_patch") or {}
    assert patch.get("mechanical_measurement_capture", {}).get("compiler_derived_envelope") is True
    assert Path(result["artifacts"]["compiler_evidence_patch"]).is_file()
