"""Scene evidence readers on the repository's real records, path confinement, and the KiCad route."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hardware_splicer import project_scene_api
from hardware_splicer.scene_evidence import EvidenceError, resolve, scene_evidence, summarise_kicad

ROOT = Path(__file__).resolve().parents[1]


def _records(project_id):
    manifest = json.loads((ROOT / "projects" / project_id / "scene.json").read_text())
    return {row["kind"]: row for row in scene_evidence(ROOT, manifest)}


def test_strategy_record_keeps_every_option_and_the_decision():
    record = _records("drone-build")["strategy"]
    assert [row["id"] for row in record["options"]][:1] == ["reference_development_kit"]
    assert len(record["options"]) == 4 and record["options"][0]["known_usd"] == 579.0
    assert record["decision"]["procurement_approved"] is False


def test_simulation_record_reports_scenarios_and_authorization():
    record = _records("hs3g-b-drone")["simulation"]
    assert [row["id"] for row in record["scenarios"]] == ["nominal", "mass_plus_5g", "motor_failure"]
    assert all(row["accepted"] for row in record["scenarios"])
    assert record["authorization"].get("flight_authorized") is False


def test_receipt_tool_run_and_bom_on_the_spi_board():
    records = _records("spi-flash-adapter-board")
    assert records["design_receipt"]["authority"]["physical_correctness"] == "UNPROVEN"
    tool = records["tool_run"]
    assert tool["tools"][0]["repository"] == "tipoLi5890/akcli" and tool["findings"]
    assert any("U3" in row["parts"] for row in tool["findings"])
    assert {row["repository"] for row in tool["not_run"]} == {"0x12net/kdif"}
    bom = records["bom_csv"]
    assert bom["lines"] and bom["known_total_usd"] >= 0


@pytest.mark.parametrize("path", ["../etc/passwd", "/etc/passwd", "src/hardware_splicer/api.py", "projects/../src/x.json", ""])
def test_evidence_paths_stay_inside_the_allowed_roots(path):
    with pytest.raises(EvidenceError):
        resolve(ROOT, path)


def test_a_bad_record_is_reported_not_dropped():
    out = scene_evidence(ROOT, {"evidence": [{"kind": "bom_csv", "path": "projects/nope.csv", "label": "x"}]})
    assert out == [{"kind": "bom_csv", "label": "x", "source": "projects/nope.csv", "error": "Evidence record not found"}]


def test_violations_are_traced_to_named_and_located_parts():
    drc = {"kicad_version": "9.0.2", "violations": [
        {"type": "shorting_items", "severity": "error", "description": "Items shorting two nets",
         "items": [{"description": "PTH pad 1 [GND] of J3", "pos": {"x": 72, "y": 31.8}},
                   {"description": "Track [SERVO_5V] on B.Cu", "pos": {"x": 10.5, "y": 10.5}}]}],
        "unconnected_items": [], "schematic_parity": []}
    footprints = [{"ref": "J3", "bbox": [70, 30, 74, 40]}, {"ref": "U1", "bbox": [10, 10, 12, 12]}]
    row = summarise_kicad(drc, None, footprints)["drc"]["violations"][0]
    assert row["parts"] == ["J3", "U1"] and row["parts_named"] == ["J3"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HARDWARE_SPLICER_REPO_ROOT", str(ROOT))
    app = FastAPI()
    app.include_router(project_scene_api.project_scene_router)
    return TestClient(app)


def test_evidence_route(client):
    body = client.get("/v1/scenes/hs3g-b-drone/evidence").json()
    assert [row["kind"] for row in body["records"]] == ["simulation"]
    assert client.get("/v1/scenes/no-such/evidence").status_code == 404


def test_kicad_route_maps_violations_to_part_ids_and_caches(client, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        out = Path(argv[argv.index("-o") + 1])
        out.write_text(json.dumps({"kicad_version": "9.0.2", "violations": [
            {"type": "clearance", "severity": "error", "description": "Clearance violation",
             "items": [{"description": "Pad 2 [GND] of U2 on F.Cu", "pos": {"x": 1, "y": 1}}]}],
            "unconnected_items": [], "schematic_parity": []}))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(project_scene_api.subprocess, "run", fake_run)
    first = client.get("/v1/scenes/esp32-servo-board/a/kicad").json()
    second = client.get("/v1/scenes/esp32-servo-board/a/kicad").json()
    assert first == second and len(calls) == 1
    assert first["drc"]["violations"][0]["part_ids"] == ["u2"]
    assert client.get("/v1/scenes/hs3g-b-drone/b/kicad").status_code == 404


@pytest.mark.skipif(shutil.which("kicad-cli") is None, reason="kicad-cli not installed")
def test_kicad_route_on_the_real_esp32_board(client):
    body = client.get("/v1/scenes/esp32-servo-board/a/kicad").json()
    assert body["drc"]["counts"].get("error", 0) > 0
    shorts = [row for row in body["drc"]["violations"] if row["type"] == "shorting_items"]
    assert shorts and all(row["part_ids"] for row in shorts)
