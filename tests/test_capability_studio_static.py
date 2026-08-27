from __future__ import annotations

from pathlib import Path


PAGE = (
    Path(__file__).resolve().parents[1]
    / "apps"
    / "splice-ui"
    / "public"
    / "capability-studio.html"
)


def test_capability_studio_preserves_complete_external_engine_flow() -> None:
    source = PAGE.read_text(encoding="utf-8")

    for label in (
        "Inspect intake",
        "Compile",
        "Review evidence",
        "Handoff",
        "Import ceiling · proposed",
        "External review ceiling · observed",
        "No automatic fabrication authorization",
    ):
        assert label in source

    for endpoint in (
        "/v1/interchange/circuit-json/inspect",
        "/v1/netlist-compile",
        "/v1/build-files/engineering-review/status",
        "/v1/build-files/engineering-review/run",
        "/v1/build-files/download",
    ):
        assert endpoint in source


def test_capability_studio_exposes_review_artifact_and_main_product_handoff() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "ENGINEERING_REVIEW.json" in source
    assert "Open main project UI" in source
    assert "Human review and release gates remain authoritative" in source
