"""
Expanded smoke coverage for the Flask product backend.

These tests execute the main route families with shipped sample assets so the
backend contract stays tied to the code that actually ships.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server

DEMO_NET = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.net"
DEMO_PCB = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"

INVENTORY = [
    {"id": "arduino_uno", "condition": "used", "quantity": 1},
    {"id": "bme280", "condition": "new", "quantity": 1},
    {"id": "led", "condition": "new", "quantity": 3},
    {"id": "resistor", "condition": "new", "quantity": 5},
]

REQUIREMENTS = {
    "meta": {"project_name": "Smoke Intake", "lane": "generic", "design_intent": "prototype"},
    "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "allow"},
    "board": {"layers": 2},
    "risk_and_validation": {"what_good_looks_like": "boots and senses"},
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.setenv("CIRCUIT_AI_USAGE_DB", str(tmp_path / "usage.sqlite"))
    return api_server.app.test_client()


def _json_post(client, path: str, payload: dict):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def test_core_and_guidance_routes_smoke(client):
    assert DEMO_NET.exists()
    assert DEMO_PCB.exists()

    r = client.get("/")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("service") == "Circuit-AI API"

    r = client.get("/api/health")
    assert r.status_code == 200

    r = client.get("/api/components")
    assert r.status_code == 200

    r = _json_post(client, "/api/validate", {"microcontroller": "arduino_uno", "components": ["bme280", "led"]})
    assert r.status_code == 200
    assert "valid" in (r.get_json() or {})

    r = _json_post(
        client,
        "/api/design",
        {"project_name": "Temp Monitor", "microcontroller": "arduino_uno", "components": ["bme280", "led"]},
    )
    assert r.status_code == 200

    r = _json_post(client, "/api/recipes/analyze-inventory", {"inventory": INVENTORY})
    assert r.status_code == 200

    r = _json_post(client, "/api/recipes/generate", {"inventory": INVENTORY, "top_n": 5})
    assert r.status_code == 200
    recipes = (r.get_json() or {}).get("recipes") or []
    assert recipes
    recipe_name = recipes[0]["name"]

    r = _json_post(client, "/api/recipes/shopping-list", {"inventory": INVENTORY, "recipe_name": recipe_name})
    assert r.status_code == 200

    r = _json_post(client, "/api/recipes/filter", {"inventory": INVENTORY, "max_budget": 20.0, "top_n": 3})
    assert r.status_code == 200

    r = _json_post(client, "/api/recipes/budget-optimize", {"inventory": INVENTORY, "budget": 25.0, "goal": "learning"})
    assert r.status_code == 200

    r = client.get("/api/instructions")
    assert r.status_code == 200
    projects = (r.get_json() or {}).get("available_projects") or []
    assert projects

    r = client.get("/api/instructions/" + urllib.parse.quote(projects[0], safe=""))
    assert r.status_code == 200

    r = client.get("/api/repair-guides")
    assert r.status_code == 200
    guides = (r.get_json() or {}).get("available_guides") or []
    assert guides

    r = client.get("/api/repair-guides/" + urllib.parse.quote(guides[0], safe=""))
    assert r.status_code == 200

    r = _json_post(client, "/api/diagnose", {"symptoms": ["won't charge", "cable loose"]})
    assert r.status_code == 200

    r = client.get("/api/learning-paths")
    assert r.status_code == 200
    paths = (r.get_json() or {}).get("learning_paths") or []
    assert paths

    r = client.get("/api/learning-paths/" + urllib.parse.quote(paths[0]["id"], safe=""))
    assert r.status_code == 200

    r = _json_post(client, "/api/learning-paths/recommend", {"interests": ["iot"], "available_hours": 20})
    assert r.status_code == 200

    r = _json_post(client, "/api/pricing/component", {"components": [{"id": "arduino_uno", "condition": "new", "quantity": 1}]})
    assert r.status_code == 200

    r = client.get("/api/pricing/market/" + urllib.parse.quote(recipe_name, safe=""))
    assert r.status_code == 200


def test_v2_workflow_and_manufacturing_routes_smoke(client):
    r = _json_post(client, "/api/v2/workflow/beginner", {"skill_level": 2, "inventory": INVENTORY, "goal": "learning"})
    assert r.status_code == 200
    beginner = r.get_json() or {}
    assert beginner.get("status") == "success"
    project_name = ((beginner.get("project") or {}).get("name")) or "Air Quality Monitor"

    r = client.get("/api/v2/projects/catalog")
    assert r.status_code == 200

    r = _json_post(
        client,
        "/api/v2/workflow/complete",
        {"user": {"skill_level": 2, "inventory": INVENTORY, "goal": "learning"}, "project_name": project_name},
    )
    assert r.status_code == 200

    with DEMO_NET.open("rb") as nf:
        r = client.post(
            "/api/v2/workflow/validate-kicad",
            data={"kicad_file": (nf, DEMO_NET.name)},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200

    with DEMO_NET.open("rb") as nf:
        r = client.post("/api/v2/manufacture/bom", data={"netlist_file": (nf, DEMO_NET.name)}, content_type="multipart/form-data")
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf:
        r = client.post("/api/v2/manufacture/gerber", data={"pcb_file": (pf, DEMO_PCB.name)}, content_type="multipart/form-data")
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf:
        r = client.post("/api/v2/manufacture/pnp", data={"pcb_file": (pf, DEMO_PCB.name)}, content_type="multipart/form-data")
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf:
        r = client.post("/api/v2/report/dfm", data={"pcb_file": (pf, DEMO_PCB.name)}, content_type="multipart/form-data")
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf, DEMO_NET.open("rb") as nf:
        r = client.post(
            "/api/v2/manufacture/package",
            data={"pcb_file": (pf, DEMO_PCB.name), "netlist_file": (nf, DEMO_NET.name)},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf:
        r = client.post("/api/v2/layout/advice", data={"pcb_file": (pf, DEMO_PCB.name)}, content_type="multipart/form-data")
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf:
        r = client.post("/api/v2/prototype3d/package", data={"pcb_file": (pf, DEMO_PCB.name)}, content_type="multipart/form-data")
    assert r.status_code == 200

    r = client.get("/api/v2/robot/probe-plan/template")
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf:
        r = client.post("/api/v2/robot/probe-plan", data={"pcb_file": (pf, DEMO_PCB.name)}, content_type="multipart/form-data")
    assert r.status_code == 200


def test_v2_intake_machine_and_project_routes_smoke(client):
    r = client.get("/api/v2/intake/template?lane=generic")
    assert r.status_code == 200

    r = _json_post(client, "/api/v2/intake/compile", {"requirements": REQUIREMENTS})
    assert r.status_code == 200
    intake_id = (r.get_json() or {}).get("intake_id")
    assert intake_id

    r = client.get(f"/api/v2/intake/{intake_id}")
    assert r.status_code == 200

    r = _json_post(client, "/api/v2/simulate/spice", {"netlist_text": "* test\n.op\n.end\n"})
    assert r.status_code in (200, 501)

    r = _json_post(client, "/api/v2/report/ee-quality", {"requirements": REQUIREMENTS})
    assert r.status_code == 200

    r = _json_post(client, "/api/v2/mechanical/bom", {"work_area_mm": [120, 80], "accuracy_mm": 0.25, "prefer": "balanced"})
    assert r.status_code == 200

    machine_payload = {
        "machine_name": "SmokeMachine",
        "lane": "generic",
        "design_intent": "prototype",
        "boards": [
            {
                "board_id": "main_ctrl",
                "name": "Main Controller",
                "lane": "generic",
                "design_intent": "prototype",
                "requirements": REQUIREMENTS,
                "pcb_outline_mm": [80, 50, 1.6],
            },
            {
                "board_id": "sensor_io",
                "name": "Sensor IO",
                "lane": "power",
                "design_intent": "prototype",
                "requirements": {
                    **REQUIREMENTS,
                    "meta": {"project_name": "Sensor IO", "lane": "power", "design_intent": "prototype"},
                    "power": {
                        "sources": [{"name": "VIN", "voltage_v": 5.0}],
                        "rails": [{"name": "3V3", "max_current_a": 0.4}],
                        "loads": [{"name": "ESP32", "rail": "3V3", "current_a": 0.24}],
                    },
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

    r = _json_post(client, "/api/v2/machines/compile", machine_payload)
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as f1, DEMO_PCB.open("rb") as f2:
        r = client.post(
            "/api/v2/machines/build-package",
            data={
                "machine_json": json.dumps(
                    {
                        "machine_name": "SmokePkg",
                        "boards": [{"board_id": "main_ctrl", "lane": "generic"}, {"board_id": "sensor_io", "lane": "power"}],
                        "interconnects": [{"from_board": "main_ctrl", "to_board": "sensor_io", "interface": "i2c"}],
                    }
                ),
                "pcb_file_main_ctrl": (f1, "main_ctrl.kicad_pcb"),
                "pcb_file_sensor_io": (f2, "sensor_io.kicad_pcb"),
            },
            content_type="multipart/form-data",
        )
    assert r.status_code == 200

    r = _json_post(
        client,
        "/api/v2/machines/engineer",
        {"machine": machine_payload, "mechanism": {}, "run_mechanism_sim": False, "simulation_fidelity": "starter"},
    )
    assert r.status_code == 200

    r = _json_post(
        client,
        "/api/v2/machines/full-simulate",
        {
            "machine": machine_payload,
            "mechanism": {},
            "board_design_files": {
                "main_ctrl": {"path": str(DEMO_NET), "kind": "netlist"},
                "sensor_io": {"path": str(DEMO_PCB), "kind": "pcb"},
            },
            "strict": False,
            "simulation_fidelity": "starter",
        },
    )
    assert r.status_code == 200

    r = _json_post(client, "/api/v2/projects", {"name": "Smoke Project", "lane": "generic", "design_intent": "prototype"})
    assert r.status_code == 200
    project_id = (r.get_json() or {}).get("project_id")
    assert project_id

    r = client.get(f"/api/v2/projects/{project_id}")
    assert r.status_code == 200

    r = _json_post(client, f"/api/v2/projects/{project_id}/revisions", {"requirements": REQUIREMENTS, "notes": "initial"})
    assert r.status_code == 200
    revision_id = (r.get_json() or {}).get("revision_id")
    assert revision_id

    r = client.get(f"/api/v2/projects/{project_id}/revisions")
    assert r.status_code == 200

    with DEMO_PCB.open("rb") as pf, DEMO_NET.open("rb") as nf:
        r = client.post(
            f"/api/v2/projects/{project_id}/build-package",
            data={"revision_id": revision_id, "pcb_file": (pf, DEMO_PCB.name), "netlist_file": (nf, DEMO_NET.name)},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200

    r = _json_post(client, f"/api/v2/projects/{project_id}/revisions", {"notes": "template-based"})
    assert r.status_code == 200
    revision_id_2 = (r.get_json() or {}).get("revision_id")
    assert revision_id_2

    r = client.get(f"/api/v2/projects/{project_id}/diff?from={revision_id}&to={revision_id_2}")
    assert r.status_code == 200


def test_support_admin_and_payment_routes_fail_cleanly(client):
    r = client.get("/api/v2/usage")
    assert r.status_code == 200

    r = _json_post(client, "/api/v2/support/tickets", {"email": "smoke@example.com", "subject": "Smoke", "message": "Testing support intake"})
    assert r.status_code == 200

    for path in ("/api/v2/admin/keys", "/api/v2/admin/ops"):
        r = client.get(path)
        assert r.status_code == 404
        assert (r.get_json() or {}).get("error") == "admin_disabled"

    r = _json_post(client, "/api/payment/create-checkout", {"product_type": "guide_onetime"})
    assert r.status_code == 400

    r = client.get("/api/payment/verify")
    assert r.status_code == 400

    r = _json_post(client, "/api/payment/check-access", {"user_identifier": "smoke@example.com"})
    assert r.status_code == 400

    r = client.get("/api/payment/analytics")
    assert r.status_code == 200

    r = client.post("/api/v2/webhooks/stripe", data="{}", content_type="application/json")
    assert r.status_code == 404
