"""Build file API for KiCanvas preview."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hardware_splicer.api import create_app
from hardware_splicer.build_files import list_kicad_files, read_build_file


def test_list_and_read_kicad_files(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    pcb = comp / "main_ctrl_build.kicad_pcb"
    pcb.write_text("(kicad_pcb (version 20241229) (generator test))\n", encoding="utf-8")
    sch = comp / "main_ctrl_build.kicad_sch"
    sch.write_text("(kicad_sch (version 20230121) (generator test))\n", encoding="utf-8")

    files = list_kicad_files(tmp_path)
    assert len(files) == 2
    assert files[0]["kind"] == "pcb"

    payload = read_build_file(tmp_path, "build_compilation/main_ctrl_build.kicad_pcb")
    assert payload["kind"] == "pcb"
    assert "(kicad_pcb" in payload["content"]

    with pytest.raises(ValueError, match="invalid relative path|escapes"):
        read_build_file(tmp_path, "../outside.kicad_pcb")


def test_build_files_api(tmp_path: Path) -> None:
    comp = tmp_path / "build_compilation"
    comp.mkdir()
    (comp / "demo.kicad_pcb").write_text("(kicad_pcb (version 20241229))\n", encoding="utf-8")
    (comp / "DESIGN_QUALITY.json").write_text(
        json.dumps(
            {
                "drc_pass": True,
                "drc_errors": 0,
                "drc_warnings": 3,
                "copper_tier": "cosmetic_preview",
                "fab_recommendation": "review_required_preview_copper",
                "build_ready": True,
            }
        ),
        encoding="utf-8",
    )
    (comp / "KICAD_DRC.json").write_text(json.dumps({"pass": True, "errors": 0, "warnings": 3}), encoding="utf-8")

    client = TestClient(create_app())
    listed = client.post("/v1/build-files/list", json={"build_dir": str(tmp_path)}).json()
    assert listed["ok"] is True
    assert listed["files"][0]["name"] == "demo.kicad_pcb"

    content = client.post(
        "/v1/build-files/content",
        json={"build_dir": str(tmp_path), "relative": "build_compilation/demo.kicad_pcb"},
    ).json()
    assert content["ok"] is True
    assert "(kicad_pcb" in content["content"]

    quality = client.post("/v1/build-files/design-quality", json={"build_dir": str(tmp_path)}).json()
    assert quality["ok"] is True
    assert quality["kicad_drc_errors"] == 0
    assert quality["copper_tier"] == "cosmetic_preview"


def test_netlist_fixture_example() -> None:
    client = TestClient(create_app())
    catalog = client.get("/v1/examples/netlist-fixtures").json()
    assert catalog["ok"] is True
    dht = next(row for row in catalog["fixtures"] if row["id"] == "usb_esp_dht22")
    assert "dht22" in dht["description"]
    assert any(row["id"] == "usb_esp_dht22" for row in catalog["fixtures"])

    fixture = client.get("/v1/examples/netlist-fixtures/usb_esp_dht22").json()
    assert fixture["ok"] is True
    assert isinstance(fixture["circuit_json"], list)
    assert len(fixture["circuit_json"]) >= 1
