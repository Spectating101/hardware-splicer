from __future__ import annotations

from pathlib import Path

from hardware_splicer.project_intake import run_project_intake
from hardware_splicer.source_agnostic_benchmark import (
    evaluate_source_agnostic_scenario,
    evaluate_source_agnostic_suite,
    load_source_agnostic_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "examples" / "source_agnostic"
CASES = [
    CASE_DIR / "conflicting_quadruped_reconstruction.json",
    CASE_DIR / "requirement_only_inspection_rover.json",
    CASE_DIR / "donor_repair_rover.json",
    CASE_DIR / "field_failure_payload_revision.json",
]


def test_source_agnostic_cases_load_and_cover_all_modes() -> None:
    scenarios = [load_source_agnostic_scenario(path) for path in CASES]

    assert {row["mode"] for row in scenarios} == {
        "reconstruct",
        "synthesize",
        "repair",
        "evolve",
    }
    assert all(row["challenge"] for row in scenarios)


def test_complete_requirement_driven_plan_can_score_one_hundred() -> None:
    scenario = {
        "scenario_id": "perfect_requirement_synthesis",
        "mode": "synthesize",
        "expected_archetype": "rover",
        "engineering_sources": [],
        "challenge": {
            "expected_conflict_count": 0,
            "identity_continuity_required": True,
        },
        "intake": {
            "goal": "design a rover",
            "constraints": {"width_mm": 200},
        },
    }

    def planner(_intake, *, skip_vision):
        assert skip_vision is True
        return {
            "goal": "design a rover",
            "archetype": "rover",
            "recommended_build_id": "robot_drive_base",
            "missing_info": ["physical bench evidence"],
            "assumptions": ["indoor low-speed use"],
            "identity_map": {
                "component_id": "drive_left",
                "interface_id": "motor_bus",
            },
            "authority": {
                "evidence_status": "planning_authority_only",
                "release_status": "not authorized",
            },
            "scenario": {
                "acceptance": {"allowed_blockers": 0},
                "compile_spec": {
                    "machine": {"machine_name": "PerfectRover"},
                    "robotics_project": {"platform": {"type": "differential_drive"}},
                    "safety_case": {"emergency_stop": True},
                },
            },
        }

    result = evaluate_source_agnostic_scenario(scenario, planner=planner)

    assert result["score"] == 100.0
    assert result["verdict"] == "bounded_engineering_candidate"
    assert result["gaps"] == []


def test_requirement_only_case_does_not_require_a_reference_project() -> None:
    scenario = load_source_agnostic_scenario(
        CASE_DIR / "requirement_only_inspection_rover.json"
    )

    result = evaluate_source_agnostic_scenario(scenario)

    assert result["detected_archetype"] == "rover"
    assert result["engineering_source_count"] == 0
    assert result["dimensions"]["source_retention"]["satisfied"] is True
    assert result["dimensions"]["source_provenance"]["satisfied"] is True
    assert result["dimensions"]["candidate_synthesis"]["satisfied"] is True
    assert "engineering_sources_not_retained" not in result["gaps"]
    assert "source_provenance_not_pinned" not in result["gaps"]


def test_conflicting_revisions_remain_explicit_product_gaps() -> None:
    scenario = load_source_agnostic_scenario(
        CASE_DIR / "conflicting_quadruped_reconstruction.json"
    )

    result = evaluate_source_agnostic_scenario(scenario)

    assert result["engineering_source_count"] == 4
    assert "source_conflicts_not_resolved" in result["gaps"]
    assert "engineering_sources_not_retained" in result["gaps"]
    assert "source_provenance_not_pinned" in result["gaps"]
    assert result["verdict"] != "bounded_engineering_candidate"


def test_repair_and_field_evolution_cannot_silently_skip_delta_contracts() -> None:
    repair = evaluate_source_agnostic_scenario(
        load_source_agnostic_scenario(CASE_DIR / "donor_repair_rover.json")
    )
    evolve = evaluate_source_agnostic_scenario(
        load_source_agnostic_scenario(CASE_DIR / "field_failure_payload_revision.json")
    )

    donor_dimension = repair["dimensions"]["donor_reuse"]
    assert donor_dimension["satisfied"] or "donor_mapping_not_resolved" in repair["gaps"]
    assert evolve["dimensions"]["revision_impact"]["satisfied"] is False
    assert "baseline_to_candidate_impact_missing" in evolve["gaps"]
    assert repair["verdict"] != "bounded_engineering_candidate"
    assert evolve["verdict"] != "bounded_engineering_candidate"


def test_suite_reports_all_four_source_agnostic_modes() -> None:
    suite = evaluate_source_agnostic_suite(
        load_source_agnostic_scenario(path) for path in CASES
    )

    assert suite["scenario_count"] == 4
    assert len(suite["rows"]) == 4
    assert sum(
        suite[key]
        for key in (
            "bounded_engineering_candidate_count",
            "structured_project_assistant_count",
            "reference_and_gap_triage_count",
            "unsupported_count",
        )
    ) == 4


def test_requirement_only_full_run_builds_a_bounded_candidate_not_a_release(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
    scenario = load_source_agnostic_scenario(
        CASE_DIR / "requirement_only_inspection_rover.json"
    )

    result = run_project_intake(
        scenario["intake"],
        out_dir=tmp_path / "requirement-only-rover",
        start_splicer=False,
        request_id="requirement-only-rover",
    )

    assert result["compile_ok"] is True
    assert result["intake_plan"]["archetype"] == "rover"
    assert result["intake_plan"].get("reference_sources") is None
    assert Path(result["artifacts"]["planned_scenario"]).is_file()
    assert Path(result["artifacts"]["evidence_capture_kit"]).is_file()
    assert result["production_release_metrics"]["production_ready"] is False
    assert result["evidence_capture_kit"]["open_gate_count"] > 0
