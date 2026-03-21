"""
Integration tests for Circuit-AI API endpoints.

These are in-process tests (Flask test client). They do not require a running server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server

DEMO_PCB = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.setenv("CIRCUIT_AI_USAGE_DB", str(tmp_path / "usage.sqlite"))
    return api_server.app.test_client()


def test_api_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") in {"ok", "healthy"}


def test_components(client):
    r = client.get("/api/components")
    assert r.status_code == 200
    data = r.get_json() or {}
    comps = data.get("components") or []
    # Depending on build, this endpoint can return either:
    # - a flat list of component records, or
    # - a categorized dict of component IDs
    assert isinstance(comps, (list, dict))
    if isinstance(comps, list):
        assert len(comps) >= 1
    else:
        assert len(comps.keys()) >= 1
        assert any(isinstance(v, list) and len(v) >= 1 for v in comps.values())


def test_v2_beginner_workflow(client):
    payload = {
        "skill_level": 2,
        "inventory": [
            {"id": "esp32", "condition": "new", "quantity": 1},
            {"id": "bme280", "condition": "used", "quantity": 1},
        ],
        "goal": "learning",
    }
    r = client.post("/api/v2/workflow/beginner", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    assert (data.get("project") or {}).get("name")


def test_v2_api_key_required_when_enabled(client, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "test_key_123")

    payload = {"skill_level": 1, "goal": "learning"}
    r = client.post("/api/v2/workflow/beginner", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 401

    r = client.post(
        "/api/v2/workflow/beginner",
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": "Bearer test_key_123"},
    )
    assert r.status_code == 200


def test_v2_simulate_spice_missing_ngspice_returns_501(client):
    payload = {"netlist_text": "* test\n.op\n.end\n"}
    r = client.post("/api/v2/simulate/spice", data=json.dumps(payload), content_type="application/json")
    assert r.status_code in (200, 501)
    data = r.get_json() or {}
    if r.status_code == 501:
        assert data.get("error") == "ngspice_not_available"


def test_v2_layout_and_prototype3d_endpoints_accept_pcb(client):
    assert DEMO_PCB.exists(), f"demo KiCad PCB not present: {DEMO_PCB}"

    with DEMO_PCB.open("rb") as f:
        r = client.post("/api/v2/layout/advice", data={"pcb_file": (f, "board.kicad_pcb")}, content_type="multipart/form-data")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    assert "report_md" in data
    assert "pcbnew_script_py" in data

    with DEMO_PCB.open("rb") as f:
        r = client.post(
            "/api/v2/prototype3d/package",
            data={"pcb_file": (f, "board.kicad_pcb")},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    artifacts = data.get("artifacts") or {}
    assert "scad" in artifacts
    assert "wiring_plan_md" in artifacts


def test_v2_machine_compile_multiboard(client):
    payload = {
        "machine_name": "BenchInspector",
        "lane": "generic",
        "design_intent": "prototype",
        "boards": [
            {
                "board_id": "main_ctrl",
                "name": "Main Controller",
                "lane": "generic",
                "design_intent": "prototype",
                "requirements": {
                    "meta": {"project_name": "BenchInspector Main"},
                    "manufacturing": {"fab": {"name": "JLCPCB"}},
                    "risk_and_validation": {"what_good_looks_like": "Boots and talks to sensor board"},
                },
                "pcb_outline_mm": [80, 50, 1.6],
            },
            {
                "board_id": "sensor_io",
                "name": "Sensor IO",
                "lane": "power",
                "design_intent": "prototype",
                "requirements": {
                    "meta": {"project_name": "BenchInspector Sensor"},
                    "manufacturing": {"fab": {"name": "JLCPCB"}},
                    "risk_and_validation": {"what_good_looks_like": "Reads current shunt + reports over I2C"},
                    "board": {"layers": 2},
                },
                "pcb_outline_mm": [45, 35, 1.6],
            },
        ],
        "interconnects": [
            {
                "from_board": "main_ctrl",
                "to_board": "sensor_io",
                "interface": "i2c",
                "signals": ["SCL", "SDA", "GND"],
                "connector": "JST-XH-4",
                "length_cm": 25,
            }
        ],
        "power_tree": [
            {"source": "bench_supply", "board_id": "main_ctrl", "rail": "VIN", "voltage_v": 12.0, "max_current_a": 1.5},
            {"source": "main_ctrl:3V3", "board_id": "sensor_io", "rail": "3V3", "voltage_v": 3.3, "max_current_a": 0.4},
        ],
    }

    r = client.post("/api/v2/machines/compile", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"

    result = data.get("result") or {}
    machine = result.get("machine") or {}
    assert machine.get("machine_name") == "BenchInspector"
    assert machine.get("board_count") == 2

    boards = result.get("boards") or []
    assert len(boards) == 2
    assert all((b.get("board_id") and b.get("hints")) for b in boards)

    system = result.get("system") or {}
    assert "harness_bom_csv" in system
    assert "main_ctrl" in (system.get("harness_bom_csv") or "")
    anchors = system.get("mecha_electronics_anchors") or []
    assert len(anchors) == 2


def test_v2_machine_build_package_multiboard(client):
    assert DEMO_PCB.exists(), f"demo KiCad PCB not present: {DEMO_PCB}"

    machine_payload = {
        "machine_name": "BenchInspectorPkg",
        "boards": [
            {"board_id": "main_ctrl", "lane": "generic"},
            {"board_id": "sensor_io", "lane": "power"},
        ],
        "interconnects": [{"from_board": "main_ctrl", "to_board": "sensor_io", "interface": "i2c"}],
    }

    with DEMO_PCB.open("rb") as f1, DEMO_PCB.open("rb") as f2:
        r = client.post(
            "/api/v2/machines/build-package",
            data={
                "machine_json": json.dumps(machine_payload),
                "pcb_file_main_ctrl": (f1, "main_ctrl.kicad_pcb"),
                "pcb_file_sensor_io": (f2, "sensor_io.kicad_pcb"),
            },
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    machine = data.get("machine") or {}
    assert machine.get("board_count") == 2
    assert data.get("machine_package_file")
    assert data.get("download_url")


def test_v2_machine_engineer_simulation(client):
    payload = {
        "machine": {
            "machine_name": "BenchBotEngineer",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "lane": "generic",
                    "estimated_current_a": 0.4,
                    "pcb_outline_mm": [80, 50, 1.6],
                    "capabilities": {"pwm_channels": 2, "stepper_channels": 1, "actuation_current_budget_a": 0.6},
                },
                {"board_id": "sensor_io", "lane": "power", "estimated_current_a": 0.2, "pcb_outline_mm": [45, 35, 1.6]},
            ],
            "interconnects": [
                {"from_board": "main_ctrl", "to_board": "sensor_io", "interface": "i2c", "length_cm": 25},
                {"from_board": "main_ctrl", "to_board": "sensor_io", "interface": "power", "length_cm": 25, "wire_awg": "24"},
            ],
            "power_tree": [
                {"source": "main_ctrl", "board_id": "sensor_io", "rail": "VIN", "voltage_v": 12.0, "max_current_a": 1.0},
                {"source": "bench_12v", "board_id": "main_ctrl", "rail": "VIN", "voltage_v": 12.0, "max_current_a": 1.0},
            ],
        },
        "mechanism": {"project_name": "bench_mech", "pan_tilt": {"name": "pt", "pan_servo": "sg90", "tilt_servo": "sg90"}},
        "run_mechanism_sim": False,
        "simulation_fidelity": "high",
    }
    r = client.post("/api/v2/machines/engineer", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    result = data.get("result") or {}
    analysis = result.get("analysis") or {}
    assert "placement" in analysis
    assert "power" in analysis
    assert "interconnects" in analysis
    assert "control_coupling" in analysis
    assert "report_md" in result
    assert result.get("intake_id")


def test_v2_machine_full_simulate_json_mode(client):
    demo_dir = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo"
    net_a = demo_dir / "usb_esp32_sensor.net"
    net_b = demo_dir / "drone_fc_power.net"
    if not net_a.exists() or not net_b.exists():
        pytest.skip("demo netlists not present")

    payload = {
        "machine": {
            "machine_name": "FullSimDemo",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "lane": "generic",
                    "requirements": {
                        "meta": {"project_name": "Main Ctrl"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "risk_and_validation": {"what_good_looks_like": "Boot"},
                    },
                },
                {
                    "board_id": "power_stage",
                    "lane": "power",
                    "requirements": {
                        "meta": {"project_name": "Power Stage"},
                        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
                        "board": {"layers": 2},
                        "power": {
                            "rails": [{"name": "12V", "voltage_v": 12.0, "max_current_a": 1.0}],
                            "sources": [{"name": "VIN", "voltage_v": 24.0, "max_current_a": 2.0}],
                            "loads": [{"name": "Main", "rail": "12V", "current_a": 0.4}],
                        },
                        "risk_and_validation": {"what_good_looks_like": "No brownout"},
                    },
                },
            ],
            "interconnects": [{"from_board": "power_stage", "to_board": "main_ctrl", "interface": "power", "length_cm": 20}],
            "power_tree": [
                {"source": "battery_24v", "board_id": "power_stage", "rail": "VIN", "voltage_v": 24.0, "max_current_a": 2.0},
                {"source": "power_stage", "board_id": "main_ctrl", "rail": "12V", "voltage_v": 12.0, "max_current_a": 1.0},
            ],
        },
        "board_design_files": {
            "main_ctrl": {"path": str(net_a), "kind": "netlist"},
            "power_stage": {"path": str(net_b), "kind": "netlist"},
        },
        "strict": False,
        "simulation_fidelity": "high",
    }
    r = client.post("/api/v2/machines/full-simulate", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    result = data.get("result") or {}
    assert result.get("verdict") in {"pass", "partial_pass", "fail"}
    assert isinstance(result.get("gates"), list)
    assert isinstance(result.get("board_simulations"), list)
    assert len(result.get("board_simulations") or []) >= 2
    gate_names = {g.get("gate") for g in (result.get("gates") or []) if isinstance(g, dict)}
    assert "board_level_operating_point" in gate_names
    assert result.get("intake_id")


def test_v2_report_ee_quality_and_projects_diff(client):
    # Create minimal project + two revisions with different requirements.
    r = client.post("/api/v2/projects", data=json.dumps({"name": "Demo Project"}), content_type="application/json")
    assert r.status_code == 200
    project_id = (r.get_json() or {}).get("project_id")
    assert project_id

    # Revision A: draft (missing fields)
    req_a = {"meta": {"lane": "generic", "design_intent": "prototype", "project_name": "DemoA"}, "manufacturing": {"fab": {"name": ""}}}
    r = client.post(
        f"/api/v2/projects/{project_id}/revisions",
        data=json.dumps({"notes": "revA", "requirements": req_a}),
        content_type="application/json",
    )
    assert r.status_code == 200
    rev_a = (r.get_json() or {}).get("revision_id")
    assert rev_a

    # Revision B: more complete
    req_b = {
        "meta": {"lane": "power", "design_intent": "professional", "project_name": "DemoB"},
        "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "explicit"},
        "board": {"layers": 2},
        "risk_and_validation": {"what_good_looks_like": "Powers on."},
        "power": {
            "rails": [{"name": "3V3", "voltage_v": 3.3, "max_current_a": 1.0}],
            "sources": [{"name": "VIN", "voltage_v": 5.0, "max_current_a": 2.0}],
            "loads": [{"name": "MCU", "rail": "3V3", "current_a": 0.2}],
        },
    }
    r = client.post(
        f"/api/v2/projects/{project_id}/revisions",
        data=json.dumps({"notes": "revB", "requirements": req_b}),
        content_type="application/json",
    )
    assert r.status_code == 200
    rev_b = (r.get_json() or {}).get("revision_id")
    assert rev_b

    # EE quality report endpoint (JSON mode)
    r = client.post("/api/v2/report/ee-quality", data=json.dumps({"requirements": req_b}), content_type="application/json")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    assert "report_md" in data

    # Diff endpoint
    r = client.get(f"/api/v2/projects/{project_id}/diff?from={rev_a}&to={rev_b}")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    diff = data.get("diff") or {}
    assert diff.get("from_revision_id") == rev_a
    assert diff.get("to_revision_id") == rev_b
    assert "diff_md" in diff


def test_v2_robot_probe_plan_mvp(client):
    demo_pcb = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"
    if not demo_pcb.exists():
        pytest.skip("demo KiCad PCB not present")

    plan = {"points": [{"ref": "U1", "point_id": "U1"}, {"x_mm": 10.0, "y_mm": 20.0, "point_id": "P1"}]}
    with demo_pcb.open("rb") as f:
        r = client.post(
            "/api/v2/robot/probe-plan",
            data={"pcb_file": (f, "board.kicad_pcb"), "plan": json.dumps(plan)},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    assert "gcode" in data
    assert "runlog_csv" in data
    assert "report_md" in data
