"""OSS catalog and artifact export API."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.api import create_app


def test_integrations_catalog() -> None:
    client = TestClient(create_app())
    payload = client.get("/v1/integrations/catalog").json()
    assert payload["ok"] is True
    assert payload["total_count"] >= 10
    assert payload["wired_count"] >= 5
    ids = {row["id"] for row in payload["integrations"]}
    assert "kicanvas" in ids
    assert "circuit-json" in ids
    assert "freerouting" in ids


def test_build_artifacts_and_circuit_json(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    (comp / "demo.kicad_pcb").write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    circuit_docs = [{"type": "source_component", "source_component_id": "u1"}]
    (comp / "circuit_json.json").write_text(json.dumps(circuit_docs), encoding="utf-8")

    client = TestClient(create_app())
    artifacts = client.post("/v1/build-files/artifacts", json={"build_dir": str(tmp_path)}).json()
    assert artifacts["ok"] is True
    rels = {row["relative"] for row in artifacts["artifacts"]}
    assert "build_compilation/demo.kicad_pcb" in rels
    assert "build_compilation/circuit_json.json" in rels

    exported = client.post("/v1/build-files/circuit-json", json={"build_dir": str(tmp_path)}).json()
    assert exported["ok"] is True
    assert exported["circuit_json"][0]["type"] == "source_component"

    download = client.post(
        "/v1/build-files/download",
        json={"build_dir": str(tmp_path), "relative": "build_compilation/circuit_json.json"},
    )
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/json") or "octet" in download.headers[
        "content-type"
    ]


def test_kicad_netlist_fixture_payload() -> None:
    client = TestClient(create_app())
    fixture = client.get("/v1/examples/netlist-fixtures/esp32_servo_kicad").json()
    assert fixture["ok"] is True
    assert fixture["type"] == "kicad_netlist"
    assert isinstance(fixture.get("kicad_netlist_text"), str)
    assert len(fixture["kicad_netlist_text"]) > 20


def test_build_bom_and_fab_manifest(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    bom = {"lines": [{"ref": "R1", "description": "10K", "qty": 1, "jlc_lcsc": "C123"}]}
    (comp / "BOM.json").write_text(json.dumps(bom), encoding="utf-8")
    (comp / "KICAD_DRC.json").write_text(json.dumps({"pass": True}), encoding="utf-8")

    client = TestClient(create_app())
    bom_payload = client.post("/v1/build-files/bom", json={"build_dir": str(tmp_path)}).json()
    assert bom_payload["ok"] is True
    assert bom_payload["line_count"] == 1
    assert bom_payload["lines"][0]["jlc_lcsc"] == "C123"

    manifest = client.post("/v1/build-files/fab-manifest", json={"build_dir": str(tmp_path)}).json()
    assert manifest["ok"] is True
    assert manifest["present_count"] >= 2
    ids = {row["id"] for row in manifest["artifacts"]}
    assert "bom_csv" in ids or "bom_json" in ids
    assert "drc_report" in ids


def test_autoroute_requires_confirm(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    (comp / "demo.kicad_pcb").write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")

    client = TestClient(create_app())
    denied = client.post("/v1/build-files/autoroute", json={"build_dir": str(tmp_path), "confirm": False})
    assert denied.status_code == 422

    with patch(
        "hardware_splicer.integrations.freerouting_bridge.run_freerouting_pipeline",
        return_value={"ok": False, "skipped": True, "reason": "test_skip"},
    ):
        allowed = client.post(
            "/v1/build-files/autoroute",
            json={"build_dir": str(tmp_path), "confirm": True},
        ).json()
    assert allowed["autoroute"]["reason"] == "test_skip"
