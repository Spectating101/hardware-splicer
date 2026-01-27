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


@pytest.fixture()
def client():
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
    # Use a demo KiCad board shipped with the repo.
    demo_pcb = REPO_ROOT / "data" / "demo_kicad_projects" / "pic_programmer" / "pic_programmer.kicad_pcb"
    if not demo_pcb.exists():
        pytest.skip("demo KiCad PCB not present")

    with demo_pcb.open("rb") as f:
        r = client.post("/api/v2/layout/advice", data={"pcb_file": (f, "board.kicad_pcb")}, content_type="multipart/form-data")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    assert "report_md" in data
    assert "pcbnew_script_py" in data

    with demo_pcb.open("rb") as f:
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
