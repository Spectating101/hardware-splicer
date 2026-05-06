from pathlib import Path

from fastapi.testclient import TestClient

from src.api.v1.main import app
from src.ml.research_radar import (
    build_research_integration_plan,
    markdown_report,
    research_source_registry,
    top_research_sources,
)
from src.vision import foundation_adapters
from src.vision.foundation_adapters import (
    build_foundation_assist_plan,
    foundation_backend_statuses,
    prompt_bank_for_case,
)


def test_research_registry_tracks_foundation_and_aoi_sources() -> None:
    ids = {source.source_id for source in research_source_registry()}

    assert {"yolo11", "sam2", "grounding_dino", "florence2", "paddleocr"} <= ids
    assert all(source.url.startswith("https://") for source in research_source_registry())


def test_research_integration_plan_has_claim_boundary_and_lanes() -> None:
    plan = build_research_integration_plan(Path("."))
    lanes = {lane["lane_id"] for lane in plan["lanes"]}

    assert "production_component_detection" in lanes
    assert "open_vocab_discovery" in lanes
    assert "marking_ocr" in lanes
    assert "production truth" in plan["principle"]
    assert "Do not" not in markdown_report(plan)


def test_top_research_sources_are_priority_sorted() -> None:
    top = top_research_sources(research_source_registry(), limit=3)

    assert len(top) == 3
    assert top[0].priority <= top[1].priority <= top[2].priority


def test_foundation_backend_statuses_are_dependency_light() -> None:
    statuses = foundation_backend_statuses()
    ids = {status["backend_id"] for status in statuses}

    assert {"ultralytics", "sam2", "grounding_dino", "florence2", "paddleocr"} <= ids
    assert all("missing_imports" in status for status in statuses)


def test_foundation_status_with_mocked_imports(monkeypatch) -> None:
    available = {"torch", "transformers", "ultralytics"}

    def fake_find_spec(name: str):
        return object() if name in available else None

    monkeypatch.setattr(foundation_adapters.importlib.util, "find_spec", fake_find_spec)
    statuses = foundation_backend_statuses()
    by_id = {status["backend_id"]: status for status in statuses}

    assert by_id["florence2"]["available"] is True
    assert by_id["ultralytics"]["available"] is True
    assert by_id["grounding_dino"]["available"] is True
    assert by_id["grounding_dino"]["adapter_backend"] == "transformers"
    assert by_id["sam2"]["available"] is False
    assert "sam2" in by_id["sam2"]["missing_imports"]


def test_foundation_assist_plan_builds_contextual_prompt_bank(monkeypatch) -> None:
    monkeypatch.setattr(foundation_adapters.importlib.util, "find_spec", lambda name: None)
    plan = build_foundation_assist_plan(
        device_hint="USB fan",
        symptoms=("will not spin", "charging port loose"),
        has_video=True,
        goal="salvage",
    )

    prompts = set(plan["prompt_bank"])
    step_ids = {step["id"] for step in plan["steps"]}
    assert "USB fan power section" in prompts
    assert "motor driver IC" in prompts
    assert "charging port" in prompts
    assert "useful module" in prompts
    assert "video_part_tracking" in step_ids
    assert "Foundation backends propose evidence" in plan["claim_boundary"]


def test_prompt_bank_deduplicates_terms() -> None:
    prompts = prompt_bank_for_case(device_hint="USB port", symptoms=("USB charge issue",))

    assert len(prompts) == len(set(prompts))
    assert "USB connector" in prompts


def test_v1_api_exposes_research_and_foundation_status() -> None:
    with TestClient(app) as client:
        radar = client.get("/ml/research-radar")
        assert radar.status_code == 200
        assert (radar.json() or {}).get("goal") == "research_backed_foundation_assist_for_aoi_repair_salvage"

        status = client.get("/ml/foundation/status?device_hint=USB%20fan&goal=salvage&has_video=true")
        assert status.status_code == 200
        payload = status.json() or {}
        assert "backend_statuses" in payload
        assert payload["assist_plan"]["device_hint"] == "USB fan"
        assert any(step["id"] == "video_part_tracking" for step in payload["assist_plan"]["steps"])
