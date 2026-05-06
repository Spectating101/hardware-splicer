from pathlib import Path

from src.ml.competitive_engine import (
    build_catchup_plan,
    markdown_report,
    source_readiness,
    source_registry,
    top_sources_by_priority,
)


def test_registry_tracks_core_sources() -> None:
    ids = {source.source_id for source in source_registry()}

    assert {"electrocom61_local", "deeppcb", "fpic", "ifixit", "daoai_aoi", "flux_ai"} <= ids


def test_readiness_detects_local_deeppcb_manifest() -> None:
    deeppcb = next(source for source in source_registry() if source.source_id == "deeppcb")
    readiness = source_readiness(deeppcb, Path("."))

    assert readiness["readiness"] in {"ready", "needs_fetch", "partial"}
    if Path("datasets/deeppcb_subset/manifest.json").exists():
        assert readiness["readiness"] == "ready"


def test_catchup_plan_has_training_and_gates() -> None:
    plan = build_catchup_plan(Path("."))
    action_ids = {action["id"] for action in plan["immediate_actions"]}

    assert "production_gates" in plan
    assert plan["production_gates"]["component_detection"]["minimum_map50"] >= 0.6
    assert "capture_protocol" in action_ids
    assert "repair_packs" in action_ids


def test_markdown_report_contains_sources() -> None:
    report = markdown_report(build_catchup_plan(Path(".")))

    assert "Competitive Engine Catch-Up Plan" in report
    assert "DeepPCB" in report
    assert "Production Gates" in report


def test_top_sources_are_priority_sorted() -> None:
    top = top_sources_by_priority(source_registry(), limit=2)

    assert len(top) == 2
    assert top[0].priority <= top[1].priority
