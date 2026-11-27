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


def test_capability_search_reports_status_and_wiring_of_hs_own_modules():
    env = tb.call("hs_capability_search", {"query": "fem screening"})
    hits = {h["module"]: h for h in env["result"]["matches"]}
    assert env["ok"] and "mechanical_cad_fem" in hits and hits["mechanical_cad_fem"]["status"] == "product"
    one = tb.call("hs_capability_search", {"module": "battery_runtime"})["result"]
    assert one["tool"] and "engineering_toolbelt" in one["importers"]
    assert not tb.call("hs_capability_search", {"module": "no_such_module"})["ok"]


def test_existing_device_review_and_battery_runtime_are_tools():
    env = tb.call("hs_device_review", {"example": "esp32_oled_bme280_usb"})
    assert env["ok"] and env["result"]["physical_correctness"] == "UNPROVEN" and env["claim_boundary"]
    missing = tb.call("hs_device_review", {})
    assert not missing["ok"] and "esp32_oled_usb" in missing["problems"][0]  # names the built-in examples
    run = tb.call("hs_battery_runtime", {"capacity_mah": 2600, "period_s": 600, "sleep_ua": 10,
                                         "phases": [{"label": "LoRa transmit", "ma": 120, "seconds": 0.5}]})
    low, high = run["result"]["runtime_days"]["with_self_discharge"]
    assert run["ok"] and 0 < low <= high


def test_prop_hover_reads_the_given_database_and_refuses_extrapolation(tmp_path, monkeypatch):
    import zipfile
    db = tmp_path / "db.zip"
    with zipfile.ZipFile(db, "w") as z:
        z.writestr("UIUC-propDB/volume-2/data/test_3x2_static_0001rd.txt",
                   "RPM CT CP\n" + "\n".join(f"{r} 0.1 0.05" for r in (5000, 10000, 15000, 20000)) + "\n")
    assert "HARDWARE_SPLICER_UIUC_PROPDB" in tb.call("hs_prop_hover", {"prop": "test_3x2", "thrust_g": 20})["problems"][0]
    monkeypatch.setenv("HARDWARE_SPLICER_UIUC_PROPDB", str(db))
    assert tb.call("hs_prop_hover", {"prop": "test_3x2", "thrust_g": 20})["ok"]
    far = tb.call("hs_prop_hover", {"prop": "test_3x2", "thrust_g": 5000})
    assert not far["ok"] and "not extrapolated" in far["problems"][0]


def test_identify_part_says_why_when_there_is_nothing_to_match():
    env = tb.call("hs_identify_part", {"marking": "ab"})
    assert not env["ok"] and env["problems"]


def _native_ready() -> bool:
    import os
    import subprocess
    py = os.environ.get("HARDWARE_SPLICER_DIGITAL_PYTHON")
    return bool(py) and subprocess.run([py, "-c", "import cadquery, gmsh, pybullet"], capture_output=True).returncode == 0


ARM = {"joints": [{"joint_id": "base_yaw", "axis": [0, 0, 1], "link_length_mm": 60, "lower_limit_deg": -150, "upper_limit_deg": 150,
                   "actuator_part_id": "dynamixel-xl430-w250-t"},
                  {"joint_id": "shoulder", "axis": [0, 1, 0], "link_length_mm": 150, "lower_limit_deg": -90, "upper_limit_deg": 90,
                   "actuator_part_id": "dynamixel-xl430-w250-t"},
                  {"joint_id": "elbow", "axis": [0, 1, 0], "link_length_mm": 140, "lower_limit_deg": -120, "upper_limit_deg": 120,
                   "actuator_part_id": "dynamixel-xl430-w250-t"}],
       "end_effector": "gripper"}


@pytest.mark.skipif(not _native_ready(), reason="needs HARDWARE_SPLICER_DIGITAL_PYTHON with cadquery, gmsh and pybullet")
def test_arm_chain_sizing_kinematics_then_motion_sweep():
    pid = tb.call("hs_project_open", {"objective": "desk arm"})["result"]["project_id"]
    env = tb.call("hs_arm_kinematics", {"project_id": pid, "proposal": ARM, "name": "desk", "supply_v": 12, "max_stall_share": 0.5,
                                        "requirements": {"required_reach_mm": 300, "payload_mass_kg": 0.1,
                                                         "minimum_static_torque_safety_factor": 2}})
    res = env["result"]
    assert res["kinematics"]["status"] == "pass" and res["closed_by_kinematics"]
    assert not any(p.startswith(("WORKSPACE_NOT_VERIFIED", "ACTUATOR_IDENTITY_UNRESOLVED")) for p in env["problems"])
    assert any(f["code"] == "PAYLOAD_ONLY_TORQUE_BOUND" for f in res["evaluation"]["findings"])  # cited servos were used
    sweep = tb.call("hs_motion_sweep", {"project_id": pid, "urdf": res["urdf"], "steps": 7})
    assert sweep["ok"], sweep["problems"]


@pytest.mark.skipif(not _native_ready(), reason="needs HARDWARE_SPLICER_DIGITAL_PYTHON with cadquery, gmsh and pybullet")
def test_fem_screen_runs_in_the_native_interpreter_and_keeps_the_field_on_the_project(tmp_path):
    import os
    import subprocess
    pid = tb.call("hs_project_open", {"objective": "bracket"})["result"]["project_id"]
    project = ObjectiveProject.load(pid)
    step = project.artifacts_dir / "bar.step"
    step.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([os.environ["HARDWARE_SPLICER_DIGITAL_PYTHON"], "-c",
                    f"import cadquery as cq; cq.exporters.export(cq.Workplane().box(60, 10, 10), {str(step)!r})"], check=True)
    env = tb.call("hs_fem_screen", {"project_id": pid, "cad_file": str(step.relative_to(project.root)), "fixed_plane": "x_min",
                                    "loaded_plane": "x_max", "force_n": [100, 0, 0], "youngs_pa": 2.0e9, "poisson": 0.35,
                                    "yield_pa": 40e6, "mesh_size_mm": 5})
    res = env["result"]
    assert res["max_von_mises_pa"] > 0 and (project.root / res["full_result"]).is_file()
    assert "nodal_displacements_m" not in res  # the field stays in the file, not in the agent's context
    assert any("blocker" in p for p in env["problems"])  # linear tetrahedra are not conservative: the check stays open


def test_plan_circuit_runs_the_named_planner_without_a_model_call(monkeypatch):
    import hardware_splicer.circuit_synthesis.semantic_planner_selector as sel
    monkeypatch.setattr(sel, "select_semantic_circuit_planner", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model called")))
    intent = {"goal": "drive a small DC pump from a microcontroller GPIO",
              "supply_rails": [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}],
              "load_requirements": [{"name": "pump", "type": "dc_motor", "voltage_v": 5.0, "current_a": 0.45}],
              "signal_requirements": [{"name": "control", "type": "pwm", "voltage_v": 3.3}],
              "allowed_modules": ["usb-power-5v", "esp32-devkit", "mosfet-irlz44n", "water_pump_5v"]}
    env = tb.call("hs_plan_circuit", {"intent": intent, "planner": "motor_driver"})
    assert env["result"]["candidate"]["metadata"]["dispatch"]["selected_planner"] == "motor_driver"
    # the catalogue has no current rating for this MOSFET: the planner blocks instead of guessing
    assert not env["ok"] and any("switch_current_rating" in p for p in env["problems"])
    bad = tb.call("hs_plan_circuit", {"intent": intent, "planner": "flux_capacitor"})
    assert not bad["ok"] and "battery_power" in bad["problems"][0]


def test_an_objective_links_to_a_stored_design_and_reports_its_release_state(tmp_path, monkeypatch):
    from hardware_splicer.project_store import ProjectStore
    monkeypatch.setenv("HARDWARE_SPLICER_PROJECT_ROOT", str(tmp_path / "designs"))
    ProjectStore().save("robot-arm", {"machineProject": {"project_id": "robot-arm", "name": "Desk arm", "purpose": "pick parts"}})
    pid = tb.call("hs_project_open", {"objective": "desk arm"})["result"]["project_id"]
    assert not tb.call("hs_project_link_design", {"project_id": pid, "design_project_id": "no-such-design"})["ok"]
    env = tb.call("hs_project_link_design", {"project_id": pid, "design_project_id": "robot-arm"})
    assert env["ok"] and env["result"]["revision"] == 1
    status = tb.call("hs_project_status", {"project_id": pid})["result"]
    assert status["design"]["project_id"] == "robot-arm" and status["design"]["name"] == "Desk arm"
    if status["design"]["release_blockers"]:  # the design's own blockers are on the objective's open list
        assert any(o["check"] == "design:robot-arm" for o in status["open"])
    # the link reports only: the stored design is unchanged
    assert ProjectStore().load("robot-arm")["revision"] == 1


def test_device_review_repairs_a_broken_spec_with_the_planners_suggestions():
    import copy
    from hardware_splicer.device_plan import build_device_plan, example_specs
    spec = copy.deepcopy(example_specs()["esp32_oled_bme280_usb"])
    spec["connections"] = [c for c in spec["connections"] if c["from"] != "display.GND"]  # a broken ground wire
    assert build_device_plan(spec)["counts"]["errors"]
    env = tb.call("hs_device_review", {"spec": spec})
    assert not env["ok"] and "suggested_spec" in env["problems"][-1]
    fixed = env["result"]["suggested_spec"]
    assert any(c["from"] == "display.GND" for c in fixed["connections"])
    again = tb.call("hs_device_review", {"spec": fixed})
    assert "suggested_spec" not in again["result"]  # the repaired spec plans cleanly and is reviewed as given


def test_route_economics_prices_routes_and_keeps_missing_costs_missing():
    money = lambda a, c="ESTIMATED": {"amount": a, "evidence_class": c}  # noqa: E731
    route = {"route_id": "repair-and-sell", "action": "refurbish", "currency": "TWD", "success_probability": 0.8,
             "probability_evidence": "HYPOTHESIS", "sale_proceeds": money(600, "HYPOTHESIS"), "failure_proceeds": money(20),
             "expenses": {k: money(v) for k, v in {"acquisition": 100, "material_and_fab": 100, "engineering": 50, "labor": 20,
                                                   "quality": 10, "freight_and_tax": 10, "sales_and_payment": 10,
                                                   "warranty_and_returns": 10}.items()}}
    case = {"schema_version": "hardware_splicer.commercial_value_case.v1", "candidate_id": "TW-USED-001", "currency": "TWD",
            "market": "Taiwan", "routes": [route]}
    env = tb.call("hs_route_economics", {"case": case})
    assert env["ok"] and env["result"]["routes"][0]["net_value"] == 174.0
    del route["expenses"]["quality"]
    gap = tb.call("hs_route_economics", {"case": case})
    assert not gap["ok"] and any("expenses.quality" in p for p in gap["problems"])


def test_bench_parts_lead_to_a_lab_pack_on_the_project():
    have = tb.call("hs_what_can_i_build", {"have": ["esp32-devkitc-v4", "adafruit-bh1750-stemma-qt"]})
    assert have["ok"] and have["result"]["ready"]
    pid = tb.call("hs_project_open", {"objective": "light logger from parts on hand"})["result"]["project_id"]
    lab = tb.call("hs_device_lab", {"project_id": pid, "example": "esp32_oled_usb", "name": "logger"})
    assert lab["ok"] and any(f.endswith("LAB.md") for f in lab["result"]["files_in_project"])
    assert lab["result"]["power_on_authorized"] is False
    st = ObjectiveProject.load(pid).status()
    assert any(d["artifact"].startswith("lab:") for d in st["deliverables"])


def test_eagle_board_draft_lists_what_must_still_be_cited(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("eagle_fixture", Path(__file__).with_name("test_eagle_board_import.py"))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    pid = tb.call("hs_project_open", {"objective": "reuse a breakout"})["result"]["project_id"]
    brd = ObjectiveProject.load(pid).artifacts_dir / "board.brd"
    brd.write_bytes(fixture.BOARD)
    env = tb.call("hs_import_eagle_module", {"project_id": pid, "brd": "artifacts/board.brd", "url": fixture.URL, "module_id": "test-breakout"})
    assert env["result"]["draft"]["status"] == "GEOMETRY_ONLY_DRAFT"
    assert env["problems"] and all(p.startswith("fill from a cited page") for p in env["problems"])


def test_board_parts_are_checked_against_the_distributor_listing(monkeypatch):
    import shutil as _sh
    from hardware_splicer import distributor_check
    if not _sh.which("kicad-cli"):
        pytest.skip("needs kicad-cli to export the netlist")
    monkeypatch.setattr(distributor_check, "lcsc_fetcher", lambda *a, **k: (
        lambda code: {"code": code, "found": True, "package": "QFN-56", "name": "QFN-56 part", "model": "X", "stock": 5}))
    env = tb.call("hs_check_board_parts", {"board": "projects/hs-bus-a/kicad/hs_bus_a.kicad_sch"})
    assert env["result"]["parts_with_codes"] > 0
    assert any("package_mismatch" in p for p in env["problems"])  # every 0603 part is not a QFN-56


def test_measured_outcomes_append_to_the_project_ledger_once():
    money = lambda a: {"amount": a, "evidence_class": "MEASURED", "reference": "receipt-1"}  # noqa: E731
    tx = {"transaction_id": "sale-001", "candidate_id": "refurb-laptop", "route_id": "refurbish", "currency": "TWD",
          "acceptance_status": "ACCEPTED", "acceptance_reference": "signed-1", "payment_status": "SETTLED",
          "payment_reference": "bank-1", "revenue": money(10000),
          "costs": {k: money(100) for k in ("acquisition", "materials", "engineering", "labor", "quality", "logistics_and_tax",
                                            "fees", "warranty_cash_spent")}}
    pid = tb.call("hs_project_open", {"objective": "refurbish and sell"})["result"]["project_id"]
    assert tb.call("hs_record_outcome", {"project_id": pid, "transaction": tx})["ok"]
    again = tb.call("hs_record_outcome", {"project_id": pid, "transaction": tx})
    assert not again["ok"] and "duplicate_transaction_id" in again["problems"]


def test_salvage_resources_need_a_linked_design_and_never_mark_unevidenced_donors_ready(tmp_path, monkeypatch):
    from hardware_splicer.project_store import ProjectStore
    monkeypatch.setenv("HARDWARE_SPLICER_PROJECT_ROOT", str(tmp_path / "designs"))
    pid = tb.call("hs_project_open", {"objective": "radio buttons"})["result"]["project_id"]
    assert "hs_project_link_design" in tb.call("hs_salvage_resources", {"project_id": pid})["problems"][0]
    ProjectStore().save("monitor", {"machineProject": {"project_id": "monitor", "name": "Monitor", "purpose": "watch"}})
    tb.call("hs_project_link_design", {"project_id": pid, "design_project_id": "monitor"})
    env = tb.call("hs_salvage_resources", {"project_id": pid, "donors": [{"donor_id": "donor:radio:buttons", "label": "Buttons"}],
                                           "lab_tools": [{"operator_id": "printer-1", "kind": "printer", "display_name": "FDM",
                                                          "capabilities": ["fdm.print"], "limits": {}, "available": True,
                                                          "simulated_only": False}]})
    assert any("donor:radio:buttons" in p for p in env["problems"])


def test_propulsion_pick_then_check_by_table_id():
    spec = {"rotors": 4, "mass_without_motors_g": 197.5, "battery": {"cells": 4, "capacity_mah": 850, "c_continuous": 70},
            "esc_continuous_a": 35, "frame": {"wheelbase_mm": 137}}
    picked = tb.call("hs_pick_propulsion", {"spec": spec})
    assert picked["ok"], picked["problems"]
    best = picked["result"]["passing"][0]
    checked = tb.call("hs_check_propulsion", {"spec": {"rotors": 4, "prop": best["prop"], "all_up_mass_g": best["all_up_mass_g"],
                                                       "battery": spec["battery"], "esc_continuous_a": 35}, "table": best["table"]})
    assert checked["result"]["results"]["hover_time_min"] == best["hover_time_min"]
    none = tb.call("hs_pick_propulsion", {"spec": dict(spec, mass_without_motors_g=5000)})
    assert not none["ok"] and none["problems"]
