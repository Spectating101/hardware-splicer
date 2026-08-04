from __future__ import annotations

from pathlib import Path

from hardware_splicer.robot_reference_e2e import (
    flatten_catalog,
    load_json,
    run_robot_reference_e2e,
    selected_engineering_sources,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "examples" / "robot_reference_corpus" / "robot_reference_catalog.json"
CASE_PATH = ROOT / "examples" / "robot_reference_e2e" / "reference_rich_indoor_inspection_rover.json"


def _fixtures() -> tuple[dict, dict]:
    return load_json(CATALOG_PATH), load_json(CASE_PATH)


def test_robot_reference_catalog_is_large_diverse_and_identity_safe() -> None:
    catalog, _ = _fixtures()
    sources = flatten_catalog(catalog)
    families = catalog["families"]
    source_types = {row["source_type"] for row in sources.values()}
    video_sources = [
        row
        for row in sources.values()
        if row["source_type"] in {"video", "video_index"}
    ]

    assert len(families) == 11
    assert len(sources) == 51
    assert len(sources) == len(set(sources))
    assert {row["genre"] for row in families} >= {
        "rover",
        "serial_manipulator",
        "quadruped",
        "aerial",
    }
    assert {"repository", "documentation", "assembly_manual", "research_paper"}.issubset(
        source_types
    )
    assert len(video_sources) >= 10
    assert all(row["authority_ceiling"] == "observed" for row in video_sources)
    assert all(row.get("revision_policy") for row in sources.values())
    assert all(row.get("evidence_use") for row in sources.values())
    assert all(row.get("limitations") for row in sources.values())


def test_reference_selection_retains_public_and_structured_sources_without_fake_conflicts() -> None:
    catalog, case = _fixtures()
    sources = selected_engineering_sources(catalog, case)

    assert len(sources) == 14
    assert {row["source_id"] for row in sources} >= {
        "linorobot2-repo",
        "tb3-hardware-assembly",
        "ardurover-docs",
        "e2e-rover-urdf",
        "e2e-firmware-manifest",
        "e2e-ros-contract",
    }
    videos = [row for row in sources if row.get("source_type") == "video"]
    assert len(videos) == 2
    assert all(row["authority_ceiling"] == "observed" for row in videos)
    public_claim_keys = [
        (claim["subject_id"], claim["predicate"])
        for row in sources
        for claim in row.get("claims") or []
    ]
    assert len(public_claim_keys) == len(set(public_claim_keys))


def test_reference_rich_rover_runs_end_to_end_and_remains_fail_closed() -> None:
    catalog, case = _fixtures()
    report = run_robot_reference_e2e(catalog, case)

    failed = [row for row in report["checks"] if not row["passed"]]
    assert report["passed"] is True, failed
    assert report["catalog"]["family_count"] == 11
    assert report["catalog"]["source_count"] == 51
    assert report["selected_evidence"]["source_count"] == 14
    assert report["selected_evidence"]["video_source_count"] == 2

    summary = report["plan_summary"]
    assert summary["native_robot_genre"] == "rover"
    assert summary["source_graph_source_count"] == 14
    assert summary["source_graph_conflict_count"] == 0
    assert summary["topology_joint_count"] >= 2
    assert summary["topology_actuator_count"] >= 2
    assert summary["analysis_finding_count"] > 0
    assert summary["operator_guide_step_count"] >= 12
    assert summary["next_action_id"]

    plan = report["plan"]
    assert plan["source_adapter"]["selected_robot_model_source_id"] == "e2e-rover-urdf"
    assert plan["engineering_readiness"]["structured_robot_model_selected"] is True
    assert plan["manufacturing_closure"]
    assert plan["engineering_execution_plan"]
    assert plan["operator_guide"]
    assert report["prepared_action"]["payload"]
    assert all(value is False for value in report["physical_authority"].values())
    assert report["prepared_action"]["metadata"]["physical_action"] is False
    assert report["prepared_action"]["metadata"]["automatic_execution"] is False
