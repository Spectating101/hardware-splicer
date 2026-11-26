"""Engineering toolbelt: the envelope, project recording, problems staying open until fixed, and MCP/REST exposure."""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from hardware_splicer import engineering_toolbelt as tb
from hardware_splicer.objective_project import ObjectiveProject


@pytest.fixture(autouse=True)
def _projects(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_PROJECTS_ROOT", str(tmp_path / "projects"))


def test_a_decision_needs_its_reason_and_research_keeps_sources():
    pid = tb.call("hs_project_open", {"objective": "An inspection rover"})["result"]["project_id"]
    bad = tb.call("hs_project_record", {"project_id": pid, "kind": "decision", "title": "drive", "choice": "4WD"})
    assert not bad["ok"] and "reason" in bad["problems"][0]
    tb.call("hs_project_record", {"project_id": pid, "kind": "decision", "title": "drive", "choice": "4WD skid steer",
                                  "because": "no caster to snag", "alternatives": ["2WD + caster"]})
    tb.call("hs_project_record", {"project_id": pid, "kind": "research", "title": "prior art", "sources": ["https://example.org/rover"]})
    st = tb.call("hs_project_status", {"project_id": pid})["result"]
    assert st["decisions"][0]["because"] == "no caster to snag"
    assert st["research"][0]["sources"] == ["https://example.org/rover"]


def test_tool_runs_are_recorded_and_a_problem_stays_open_until_the_same_check_passes():
    pid = tb.call("hs_project_open", {"objective": "rover"})["result"]["project_id"]
    failing = tb.call("hs_size_rover_drive", {"project_id": pid, "mass_kg": 60, "wheel_mm": 80, "speed_m_s": 3.0, "slope_deg": 30})
    assert not failing["ok"] and failing["problems"] and failing["project_step"] == 1
    assert ObjectiveProject.load(pid).status()["open"][0]["check"] == "hs_size_rover_drive"
    passing = tb.call("hs_size_rover_drive", {"project_id": pid, "mass_kg": 1.2, "wheel_mm": 80, "speed_m_s": 0.4, "slope_deg": 10})
    assert passing["ok"], passing["problems"]
    st = ObjectiveProject.load(pid).status()
    assert not st["open"] and st["software_checked"][0]["check"] == "hs_size_rover_drive"
    assert st["physical_required"] and passing["sources"]


def test_errors_come_back_in_the_envelope_and_paths_stay_inside():
    env = tb.call("hs_review_kicad_schematic", {"schematic": "/etc/passwd"})
    assert not env["ok"] and "outside" in env["problems"][0]
    with pytest.raises(KeyError):
        tb.call("no_such_tool", {})


@pytest.mark.skipif(shutil.which("kicad-cli") is None or not Path("/usr/share/kicad/symbols/Device.kicad_sym").is_file(),
                    reason="needs kicad-cli and the KiCad libraries")
def test_component_board_schematic_stage_runs_through_the_toolbelt():
    pid = tb.call("hs_project_open", {"objective": "divider"})["result"]["project_id"]
    design = {"name": "divider", "parts": [
        {"ref": "J1", "lib_id": "Connector_Generic:Conn_01x03", "value": "IN", "footprint": "Connector_JST:JST_EH_B3B-EH-A_1x03_P2.50mm_Vertical", "sch_xy": [25.4, 50.8]},
        {"ref": "R1", "lib_id": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0603_1608Metric", "sch_xy": [50.8, 50.8]},
        {"ref": "R2", "lib_id": "Device:R", "value": "10k", "footprint": "Resistor_SMD:R_0603_1608Metric", "sch_xy": [76.2, 50.8]}],
        "nets": {"VIN": ["J1.1", "R1.1"], "MID": ["R1.2", "R2.1", "J1.2"], "GND": ["R2.2", "J1.3"]}, "paper": "A4"}
    env = tb.call("hs_component_board", {"project_id": pid, "design": design, "stages": ["schematic"]})
    assert env["ok"], env["problems"]
    assert env["result"]["stages"]["schematic"]["parity"]["pass"]
    assert any(f.endswith("divider.kicad_sch") for f in env["result"]["files_in_project"])


def test_every_toolbelt_tool_is_on_the_mcp_server_and_the_rest_api():
    pytest.importorskip("mcp")
    from hardware_splicer import mcp_server
    names = {t.name for t in asyncio.run(mcp_server.list_tools())}
    assert set(tb.TOOLS) <= names and "hs_sdk_info" in names
    from fastapi.testclient import TestClient
    from hardware_splicer.engineering_toolbelt_api import create_engineering_toolbelt_router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(create_engineering_toolbelt_router())
    client = TestClient(app)
    assert {t["name"] for t in client.get("/v1/toolbelt/tools").json()} == set(tb.TOOLS)
    opened = client.post("/v1/toolbelt/hs_project_open", json={"objective": "via REST"}).json()
    assert opened["ok"] and opened["result"]["project_id"]
    assert client.post("/v1/toolbelt/nope", json={}).status_code == 404
