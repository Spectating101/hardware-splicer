"""The measured-fit engine on geometry with known answers, and its cached API route."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hardware_splicer import project_scene_api, scene_fit
from hardware_splicer.digital_project import native_python

ROOT = Path(__file__).resolve().parents[1]

# Known geometry (mm): A is a 10 mm cube at the origin.
#   overlap: a 10 mm cube shifted 5 mm in x  -> 500 mm^3 shared with A
#   gap:     a 10 mm cube 0.5 mm beyond A's +y face  -> a 0.5 mm gap
#   seat:    a 10 mm cube resting on A's top face    -> touching
#   far:     a 10 mm cube 50 mm away                -> not reported
#   rough:   an envelope cube overlapping A by 2 mm  -> a stand-in overlap
BUILD = r"""
import json, sys, trimesh
out = sys.argv[1]
scene = trimesh.Scene()
def cube(name, offset):
    box = trimesh.creation.box(extents=[10, 10, 10])
    box.apply_translation([5 + offset[0], 5 + offset[1], 5 + offset[2]])
    scene.add_geometry(box, node_name=name, geom_name=name)
cube("A", (0, 0, 0)); cube("overlap", (5, 0, 0)); cube("gap", (0, 10.5, 0))
cube("seat", (0, 0, 10)); cube("far", (60, 0, 0)); cube("rough", (-8, 0, 0))
open(out + "/model.glb", "wb").write(scene.export(file_type="glb"))
parts = [{"node_name": n, "part_id": n.lower(), "label": n, "geometry_basis": "envelope" if n == "rough" else "custom"}
         for n in ["A", "overlap", "gap", "seat", "far", "rough"]]
json.dump({"schema_version": "hardware_splicer.parts_sidecar.v1", "glb_scale_to_mm": 1, "parts": parts}, open(out + "/parts.json", "w"))
"""


def _native_ready() -> str | None:
    python = native_python()
    probe = subprocess.run([python, "-c", "import trimesh, scipy, manifold3d"], capture_output=True)
    return python if probe.returncode == 0 else None


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    python = _native_ready()
    if python is None:
        pytest.skip("native CAD interpreter lacks trimesh, scipy or manifold3d")
    work = tmp_path_factory.mktemp("fit")
    subprocess.run([python, "-c", BUILD, str(work)], check=True)
    done = subprocess.run([python, "-I", scene_fit.__file__, "--glb", str(work / "model.glb"),
                           "--parts", str(work / "parts.json")], capture_output=True, text=True, check=True)
    report = json.loads(done.stdout)
    return {frozenset((row["a"], row["b"])): row for row in report["pairs"]}, report


def test_overlap_volume_is_exact(measured):
    pairs, report = measured
    row = pairs[frozenset(("a", "overlap"))]
    assert row["kind"] == "overlap" and not row["stand_in"]
    assert row["overlap_mm3"] == pytest.approx(500.0, abs=0.5)
    assert report["counts"]["overlap_real"] == 1


def test_gap_is_an_upper_bound_within_its_precision(measured):
    pairs, _ = measured
    row = pairs[frozenset(("a", "gap"))]
    assert row["kind"] == "tight"
    assert row["gap_mm"] - row["precision_mm"] <= 0.5 <= row["gap_mm"] + 1e-9


def test_seated_parts_touch_and_far_parts_are_not_reported(measured):
    pairs, _ = measured
    assert pairs[frozenset(("a", "seat"))]["kind"] == "touching"
    assert not any("far" in pair for pair in pairs)


def test_an_envelope_overlap_is_a_stand_in(measured):
    pairs, report = measured
    row = pairs[frozenset(("a", "rough"))]
    assert row["kind"] == "overlap" and row["stand_in"] and sorted(row["basis"]) == ["custom", "envelope"]
    assert report["counts"]["overlap_stand_in"] == 1


def test_size_covers_every_measured_part(measured):
    _, report = measured
    assert report["size_mm"] == [78.0, 20.5, 20.0]


# --- API ---------------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HARDWARE_SPLICER_REPO_ROOT", str(ROOT))
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(project_scene_api.project_scene_router)
    return TestClient(app)


def _canned(calls, *, returncode=0):
    def run(argv, **kwargs):
        calls.append(argv)
        report = {"schema": "hardware_splicer.scene_fit.v1", "version": scene_fit.VERSION, "size_mm": [1, 2, 3],
                  "pairs": [], "counts": {}, "not_computed": [], "parts_measured": 1, "parts_unmatched": []}
        return subprocess.CompletedProcess(argv, returncode, json.dumps(report) if returncode == 0 else "", "boom /secret/path")
    return run


def test_fit_route_measures_once_then_serves_the_cache(client, monkeypatch):
    calls = []
    monkeypatch.setattr(project_scene_api.subprocess, "run", _canned(calls))
    first = client.get("/v1/scenes/esp32-servo-board/a/fit")
    second = client.get("/v1/scenes/esp32-servo-board/a/fit")
    assert first.status_code == second.status_code == 200
    assert first.json()["size_mm"] == [1, 2, 3] and first.json()["revision"] == "a"
    assert len(calls) == 1


def test_fit_route_runs_the_engine_with_a_clean_environment(client, monkeypatch):
    calls, seen = [], {}
    run = _canned(calls)

    def spy(argv, **kwargs):
        seen.update(kwargs.get("env") or {})
        return run(argv, **kwargs)

    monkeypatch.setenv("HS_TEST_SECRET_TOKEN", "do-not-pass")
    monkeypatch.setattr(project_scene_api.subprocess, "run", spy)
    client.get("/v1/scenes/esp32-servo-board/a/fit")
    assert "HS_TEST_SECRET_TOKEN" not in seen
    assert calls[0][2] == scene_fit.__file__


def test_fit_route_errors_are_fixed_messages(client, monkeypatch):
    monkeypatch.setattr(project_scene_api.subprocess, "run", _canned([], returncode=1))
    failed = client.get("/v1/scenes/esp32-servo-board/a/fit")
    assert failed.status_code == 503
    assert "/secret" not in failed.text and str(ROOT) not in failed.text
    assert client.get("/v1/scenes/esp32-servo-board/zz/fit").status_code == 404
    assert client.get("/v1/scenes/no-such-project/a/fit").status_code == 404
