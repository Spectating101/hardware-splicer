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
    tb.call("hs_project_record", {"project_id": pid, "kind": "research", "title": "prior art", "sources": ["https://example.org/rover"]})
    failing = tb.call("hs_size_rover_drive", {"project_id": pid, "mass_kg": 60, "wheel_mm": 80, "speed_m_s": 3.0, "slope_deg": 30})
    assert not failing["ok"] and failing["problems"] and failing["project_step"] == 2
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


def test_writing_a_file_or_searching_is_not_counted_as_a_check():
    pid = tb.call("hs_project_open", {"objective": "x"})["result"]["project_id"]
    tb.call("hs_project_write_artifact", {"project_id": pid, "path": "software/a.py", "content": "print(1)\n"})
    bad = tb.call("hs_project_write_artifact", {"project_id": pid, "path": "../escape.txt", "content": "no"})
    assert not bad["ok"]
    st = ObjectiveProject.load(pid).status()
    assert st["deliverables"][0]["artifact"] == "software/a.py"
    assert not st["software_checked"] and st["open"][0]["check"] == "artifact:../escape.txt"


def test_a_parts_list_reports_salvage_and_needs_a_reason_when_nothing_is_reused():
    new = {"item": "ESP32-C3 board", "qty": 1, "unit_usd": 3.0, "source": "https://example.org/esp32c3"}
    plain = tb.call("hs_bom_check", {"lines": [new], "budget_usd": 50})
    assert any("no salvaged part" in p for p in plain["problems"])
    reasoned = tb.call("hs_bom_check", {"lines": [new], "budget_usd": 50, "salvage_rejected_because": "no donor has a 3.3 V MCU"})
    assert not reasoned["problems"]
    mixed = tb.call("hs_bom_check", {"budget_usd": 50, "lines": [new,
        {"item": "camera, Wi-Fi and battery", "qty": 1, "unit_usd": 0, "origin": "salvaged", "source": "donor:cracked Android phone",
         "mass_g": 170, "new_equivalent_usd": 25},
        {"item": "gearmotors and wheels", "qty": 1, "unit_usd": 0, "origin": "salvaged", "source": "a toy car"}]})
    assert any("must name its donor" in p for p in mixed["problems"])
    s = mixed["result"]["salvage"]
    assert s["salvaged_lines"] == 2 and s["new_spend_usd"] == 3.0 and s["mass_diverted_g"] == 170 and s["new_equivalent_replaced_usd"] == 25


def test_junk_lookup_names_donors_for_a_rover_and_flags_what_junk_cannot_give():
    env = tb.call("hs_junk_lookup", {"needs": ["drive_motors", "camera", "wifi_compute", "battery_cells"]})
    plan = env["result"]["donor_plan"]
    assert {c for d in plan for c in d["covers"]} == {"drive_motors", "camera", "wifi_compute", "battery_cells"}
    assert plan[0]["device"] == "phone-android-cracked" and len(plan) <= 3
    assert all(d["device"] != "microwave-oven" for d in plan)
    assert env["ok"] and env["claim_boundary"]
    bad = tb.call("hs_junk_lookup", {"needs": ["teleporter"]})
    assert not bad["ok"] and "unknown capabilities" in bad["problems"][0]


def test_a_project_that_checks_or_writes_without_prior_art_keeps_it_open():
    pid = tb.call("hs_project_open", {"objective": "rover"})["result"]["project_id"]
    tb.call("hs_size_rover_drive", {"project_id": pid, "mass_kg": 1.2, "wheel_mm": 80, "speed_m_s": 0.4, "slope_deg": 10})
    assert any(o["check"] == "prior_art" for o in ObjectiveProject.load(pid).status()["open"])
    tb.call("hs_prior_art_search", {"project_id": pid, "query": "rover", "sources": ["hs_own"]})
    assert not any(o["check"] == "prior_art" for o in ObjectiveProject.load(pid).status()["open"])


def test_prior_art_finds_what_hs_already_recorded():
    env = tb.call("hs_prior_art_search", {"query": "smartphone robot rover", "sources": ["hs_own"], "limit": 20})
    urls = [u.lower() for h in env["result"]["hs_own"] for u in h["urls"]]
    assert any("openbot" in u for u in urls)


def test_a_missing_required_input_is_named_not_a_crash():
    env = tb.call("hs_size_arm_actuators", {"links_mm": [150, 150], "payload_kg": 0.2})
    assert not env["ok"] and "missing required input" in env["problems"][0]
    assert "supply_v" in env["problems"][0] and "max_stall_share" in env["problems"][0]


def test_prior_art_finds_capabilities_hs_already_has_in_its_own_source():
    env = tb.call("hs_prior_art_search", {"query": "fem screening", "sources": ["hs_own"], "limit": 30})
    assert "mechanical_cad_fem" in {h.get("module") for h in env["result"]["hs_own"]}
    env = tb.call("hs_prior_art_search", {"query": "thermal device review", "sources": ["hs_own"], "limit": 30})
    assert "device_engineering" in {h.get("module") for h in env["result"]["hs_own"]}
