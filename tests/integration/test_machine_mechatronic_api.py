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
DEMO_NET = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.net"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.setenv("CIRCUIT_AI_USAGE_DB", str(tmp_path / "usage.sqlite"))
    return api_server.app.test_client()


def _json_post(client, path: str, payload: dict):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def test_machine_engineer_emits_mechatronic_context_from_board_files(client):
    machine = {
        "machine_name": "MechaBench",
        "lane": "generic",
        "design_intent": "prototype",
        "boards": [
            {"board_id": "main_ctrl", "name": "Main Control"},
            {"board_id": "sensor_io", "name": "Sensor IO", "pcb_outline_mm": [60, 40, 1.6]},
        ],
    }
    payload = {
        "machine": machine,
        "mechanism": {},
        "run_mechanism_sim": False,
        "board_design_files": {
            "main_ctrl": {"path": str(DEMO_NET), "kind": "netlist"},
            "sensor_io": {"path": str(DEMO_PCB), "kind": "pcb"},
        },
    }

    response = _json_post(client, "/api/v2/machines/engineer", payload)
    assert response.status_code == 200
    result = ((response.get_json() or {}).get("result") or {})
    analysis = result.get("analysis") or {}
    ctx = analysis.get("mechatronic_context") or {}

    assert ctx.get("primary_board_id")
    assert len(ctx.get("electronics_bundle") or []) == 2
    board_rows = {row["board_id"]: row for row in (ctx.get("boards") or [])}
    assert (board_rows["sensor_io"]["prototype3d"] or {}).get("scad")
    assert (board_rows["main_ctrl"]["controller_runtime"] or {}).get("controllers")
    compiled_boards = {row["board_id"]: row for row in ((result.get("compiled") or {}).get("boards") or [])}
    assert compiled_boards["sensor_io"]["ports"]


def test_machine_full_simulate_preserves_mechatronic_context(client):
    machine = {
        "machine_name": "MechaBench",
        "lane": "generic",
        "design_intent": "prototype",
        "boards": [
            {
                "board_id": "main_ctrl",
                "name": "Main Control",
                "requirements": {
                    "meta": {"project_name": "MechaBench::Main", "lane": "generic", "design_intent": "prototype"},
                    "power": {
                        "sources": [{"name": "USB", "voltage_v": 5.0}],
                        "rails": [{"name": "3V3", "max_current_a": 0.6}],
                        "loads": [{"name": "MCU", "rail": "3V3", "current_a": 0.22}],
                    },
                },
            }
        ],
    }
    payload = {
        "machine": machine,
        "mechanism": {},
        "strict": False,
        "board_design_files": {
            "main_ctrl": {"path": str(DEMO_NET), "kind": "netlist"},
        },
    }

    response = _json_post(client, "/api/v2/machines/full-simulate", payload)
    assert response.status_code == 200
    result = ((response.get_json() or {}).get("result") or {})
    engineering = result.get("engineering") or {}
    ctx = ((engineering.get("analysis") or {}).get("mechatronic_context") or {})
    assert ctx.get("primary_board_id") == "main_ctrl"
    assert len(ctx.get("electronics_bundle") or []) == 1
