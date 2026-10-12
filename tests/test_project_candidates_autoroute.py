"""Autoroute as a candidate proposal: the router's output is a reviewable copy, never a write to a revision."""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer import project_candidates
from hardware_splicer.artifact_retention import retain_revision_artifacts
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_candidates import (
    CandidateValidationError,
    RoutingFailed,
    RoutingNotAvailable,
    propose_candidate,
    routing_capability,
)
from hardware_splicer.project_candidates_api import create_project_candidates_router
from hardware_splicer.project_review_store import ProjectReviewStore
from hardware_splicer.project_store import ProjectStore
from hardware_splicer.routing_engine import RoutingError, RoutingUnavailable, route_pcb

REF = Path(__file__).resolve().parents[1] / "hardware" / "reference_designs" / "spi_flash_adapter_v1"
SCH = REF / "spi_flash_adapter_v1.kicad_sch"
PCB = REF / "spi_flash_adapter_v1.kicad_pcb"

ADDED_SEGMENT = """  (segment
    (start 10 12)
    (end 20 12)
    (width 0.2)
    (layer "F.Cu")
    (net 2)
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4")
  )
"""
ADDED_VIA = """  (via
    (at 15 10)
    (size 0.6)
    (drill 0.3)
    (layers "F.Cu" "B.Cu")
    (net 1)
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa5")
  )
"""


class _TrackEngine:
    name = "fake-router"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        self.calls.append({"max_passes": max_passes, "keep_existing_tracks": keep_existing_tracks})
        closing = pcb_text.rfind(")")
        return pcb_text[:closing] + ADDED_SEGMENT + ADDED_VIA + pcb_text[closing:]


def _snapshot(build: Path) -> dict:
    return {
        "projectId": "robot",
        "projectName": "Robot",
        "currentStage": "design",
        "buildDir": str(build),
        "machineProject": {"project_id": "robot", "name": "Robot", "purpose": "Route the board"},
    }


@pytest.fixture()
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.delenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_BUILD_FILE_ROOTS", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", "/var/empty-hs-autoroute-path")
    build = tmp_path / "build" / "build_compilation"
    build.mkdir(parents=True)
    shutil.copy(SCH, build / SCH.name)
    shutil.copy(PCB, build / PCB.name)
    store = ProjectStore(tmp_path / "store")
    store.save("robot", _snapshot(tmp_path / "build"), expected_revision=0)
    assert retain_revision_artifacts(store, "robot", 1, basis="at_save") is not None
    return store, ProjectReviewStore(store)


def _use_engine(monkeypatch: pytest.MonkeyPatch, engine: object) -> None:
    def routed(text: str, **options):
        return route_pcb(text, engine=engine, **options)

    monkeypatch.setattr(project_candidates, "route_pcb", routed)


def test_autoroute_opens_a_pending_review_and_changes_no_revision(seeded, monkeypatch) -> None:
    store, reviews = seeded
    engine = _TrackEngine()
    _use_engine(monkeypatch, engine)
    before = store.load("robot", revision=1)

    result = propose_candidate(store, "robot", kind="pcb", autoroute={"max_passes": 7}, author="Alice", review_store=reviews)
    candidate = result["candidate"]

    assert engine.calls == [{"max_passes": 7, "keep_existing_tracks": True}]
    assert candidate["kind"] == "pcb"
    assert candidate["authority"]["state"] == "proposal"
    assert candidate["diff"]["summary"]["added"] == 2
    assert candidate["applied"][0]["op"] == "autoroute"
    assert "1 segments and 1 vias added" in candidate["applied"][0]["detail"]
    assert any("not DRC-clean" in warning or "candidate" in warning.lower() for warning in candidate["warnings"])
    assert reviews.list("robot")[0]["status"] == "pending"
    assert store.load("robot", revision=1) == before
    assert store.load("robot")["revision"] == 1


def test_autoroute_defaults_keep_existing_tracks(seeded, monkeypatch) -> None:
    store, reviews = seeded
    engine = _TrackEngine()
    _use_engine(monkeypatch, engine)
    propose_candidate(store, "robot", kind="pcb", autoroute={}, author="Alice", review_store=reviews)
    assert engine.calls == [{"max_passes": 20, "keep_existing_tracks": True}]


@pytest.mark.parametrize(
    "autoroute",
    [
        {"max_passes": 0},
        {"max_passes": 51},
        {"max_passes": True},
        {"max_passes": "9"},
        {"keep_existing_tracks": "yes"},
        {"surprise": 1},
        "fast",
        [],
    ],
)
def test_autoroute_options_are_validated_before_any_work(seeded, monkeypatch, autoroute) -> None:
    store, reviews = seeded
    engine = _TrackEngine()
    _use_engine(monkeypatch, engine)
    with pytest.raises(CandidateValidationError):
        propose_candidate(store, "robot", kind="pcb", autoroute=autoroute, author="Alice", review_store=reviews)
    assert engine.calls == []
    assert reviews.list("robot") == []


def test_autoroute_cannot_be_combined_with_ops_or_used_on_a_schematic(seeded, monkeypatch) -> None:
    store, reviews = seeded
    engine = _TrackEngine()
    _use_engine(monkeypatch, engine)
    with pytest.raises(CandidateValidationError, match="cannot be combined"):
        propose_candidate(store, "robot", kind="pcb", autoroute={}, ops=[{"op": "rotate", "ref": "R3", "degrees": 90}], author="Alice", review_store=reviews)
    with pytest.raises(CandidateValidationError, match="applies to the PCB"):
        propose_candidate(store, "robot", kind="schematic", autoroute={}, author="Alice", review_store=reviews)
    assert engine.calls == []


def test_missing_router_tools_report_what_to_install_and_leave_nothing(seeded, tmp_path, monkeypatch) -> None:
    store, reviews = seeded

    def unavailable(text: str, **options):
        raise RoutingUnavailable("set HARDWARE_SPLICER_FREEROUTING_JAR to a FreeRouting jar")

    monkeypatch.setattr(project_candidates, "route_pcb", unavailable)
    with pytest.raises(RoutingNotAvailable, match="FREEROUTING_JAR"):
        propose_candidate(store, "robot", kind="pcb", autoroute={}, author="Alice", review_store=reviews)
    assert reviews.list("robot") == []
    assert not (tmp_path / "candidates").exists() or not any((tmp_path / "candidates").rglob("cand-*"))


def test_a_router_result_that_changes_more_than_copper_is_refused(seeded, monkeypatch) -> None:
    store, reviews = seeded

    class MovesAFootprint:
        def route(self, pcb_text: str, **options) -> str:
            return pcb_text.replace("(at 181 88", "(at 182 88", 1)

    _use_engine(monkeypatch, MovesAFootprint())
    with pytest.raises(RoutingFailed, match="placement"):
        propose_candidate(store, "robot", kind="pcb", autoroute={}, author="Alice", review_store=reviews)
    assert reviews.list("robot") == []


def test_routing_capability_reports_components_without_paths(monkeypatch) -> None:
    monkeypatch.setattr(
        project_candidates,
        "routing_capability_probe",
        lambda: {
            "available": False,
            "reason": "set HARDWARE_SPLICER_FREEROUTING_JAR to a FreeRouting jar",
            "components": {
                "kicad_python": {"ok": True, "version": "9.0.2", "path": "/usr/bin/python3"},
                "java": {"ok": True, "version": "21"},
                "freerouting_jar": {"ok": False, "path": None, "sha256_prefix": None},
            },
        },
    )
    capability = routing_capability()
    assert capability["available"] is False
    assert "FREEROUTING_JAR" in capability["reason"]
    assert capability["components"]["kicad_python"] == {"ok": True, "version": "9.0.2"}
    assert "/usr/bin" not in str(capability)


def _client(store: ProjectStore, reviews: ProjectReviewStore) -> TestClient:
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_candidates_router(store, reviews))
    return TestClient(app)


def test_http_autoroute_maps_outcomes_to_stable_errors(seeded, monkeypatch) -> None:
    store, reviews = seeded
    client = _client(store, reviews)
    _use_engine(monkeypatch, _TrackEngine())

    created = client.post("/v1/projects/robot/candidates", json={"kind": "pcb", "autoroute": {"max_passes": 3}, "author": "Alice"})
    assert created.status_code == 201, created.text
    assert created.json()["candidate"]["applied"][0]["op"] == "autoroute"

    def unavailable(text: str, **options):
        raise RoutingUnavailable("FreeRouting is not installed")

    monkeypatch.setattr(project_candidates, "route_pcb", unavailable)
    refused = client.post("/v1/projects/robot/candidates", json={"kind": "pcb", "autoroute": {}, "author": "Alice"})
    assert refused.status_code == 409
    assert refused.json()["detail"]["type"] == "routing_unavailable"

    def failed(text: str, **options):
        raise RoutingError("routing changed placement")

    monkeypatch.setattr(project_candidates, "route_pcb", failed)
    broken = client.post("/v1/projects/robot/candidates", json={"kind": "pcb", "autoroute": {}, "author": "Alice"})
    assert broken.status_code == 422
    assert broken.json()["detail"]["type"] == "routing_failed"

    invalid = client.post("/v1/projects/robot/candidates", json={"kind": "pcb", "autoroute": {"max_passes": 999}, "author": "Alice"})
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["type"] == "invalid_request"


def test_http_routing_capability_route(seeded) -> None:
    store, reviews = seeded
    response = _client(store, reviews).get("/v1/projects/robot/routing")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert set(body["routing"]) == {"available", "reason", "components"}


def test_a_slow_proposal_does_not_block_other_requests(seeded, monkeypatch) -> None:
    """The router and the checks take seconds. They run on a worker thread, so the server keeps answering."""

    store, reviews = seeded
    # Used as a context manager so every request shares ONE event loop, like a real server. Without it each request
    # gets its own loop and a blocked handler could never be noticed.
    with _client(store, reviews) as client:
        _assert_slow_proposal_does_not_block(client, monkeypatch)


def _assert_slow_proposal_does_not_block(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    started = threading.Event()
    release = threading.Event()

    class SlowEngine(_TrackEngine):
        def route(self, pcb_text: str, **options) -> str:
            started.set()
            assert release.wait(timeout=20)
            return super().route(pcb_text, **options)

    _use_engine(monkeypatch, SlowEngine())
    outcome: dict = {}

    def propose() -> None:
        outcome["response"] = client.post("/v1/projects/robot/candidates", json={"kind": "pcb", "autoroute": {}, "author": "Alice"})

    worker = threading.Thread(target=propose)
    worker.start()
    assert started.wait(timeout=10)
    began = time.monotonic()
    other = client.get("/v1/projects/robot/routing")
    elapsed = time.monotonic() - began
    release.set()
    worker.join(timeout=30)

    assert other.status_code == 200
    assert elapsed < 5
    assert outcome["response"].status_code == 201
