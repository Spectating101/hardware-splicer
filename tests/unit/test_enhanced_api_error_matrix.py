from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.api.v1.main as enhanced_api

DEMO_PCB = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"
DEMO_NET = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.net"


def _raise(exc: Exception):
    raise exc


def test_enhanced_api_endpoint_error_branches(monkeypatch):
    with TestClient(enhanced_api.app) as client:
        monkeypatch.setattr(enhanced_api, "get_kicad_parser", lambda: lambda path: _raise(RuntimeError("netlist boom")))
        with DEMO_NET.open("rb") as nf:
            r = client.post("/analyze/netlist", files={"file": (DEMO_NET.name, nf, "text/plain")})
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "netlist boom"

        monkeypatch.setattr(enhanced_api, "get_kicad_parser", lambda: lambda path: types.SimpleNamespace(parse=lambda: {}))
        monkeypatch.setattr(enhanced_api, "get_bom_generator", lambda: lambda data: _raise(RuntimeError("bom boom")))
        with DEMO_NET.open("rb") as nf:
            r = client.post("/generate/bom", files={"file": (DEMO_NET.name, nf, "text/plain")})
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "bom boom"

        monkeypatch.setattr(
            enhanced_api,
            "get_enhanced_analyzer",
            lambda: types.SimpleNamespace(submit_batch_analysis_job=lambda *args, **kwargs: _raise(RuntimeError("batch boom"))),
        )
        r = client.post("/batch_analyze", json={"image_paths": ["/tmp/a.png"], "analysis_options": {}})
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "batch boom"

        monkeypatch.setattr(
            enhanced_api,
            "get_enhanced_analyzer",
            lambda: types.SimpleNamespace(get_batch_job_status=lambda job_id: _raise(RuntimeError("job boom"))),
        )
        r = client.get("/job/x")
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "job boom"

        monkeypatch.setattr(
            enhanced_api,
            "get_enhanced_analyzer",
            lambda: types.SimpleNamespace(get_system_health=lambda: _raise(RuntimeError("health boom"))),
        )
        r = client.get("/health")
        assert r.status_code == 200
        payload = r.json() or {}
        assert payload.get("status") == "unhealthy"
        assert payload.get("error") == "health boom"

        monkeypatch.setattr(
            enhanced_api,
            "get_enhanced_analyzer",
            lambda: types.SimpleNamespace(get_analysis_statistics=lambda: _raise(RuntimeError("stats boom"))),
        )
        r = client.get("/statistics")
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "stats boom"

        monkeypatch.setattr(enhanced_api, "get_cache_service", lambda: _raise(RuntimeError("cache boom")))
        r = client.get("/cache/stats")
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "cache boom"
        r = client.post("/cache/clear")
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "cache boom"

        monkeypatch.setattr(enhanced_api, "get_queue_service", lambda: _raise(RuntimeError("queue boom")))
        r = client.get("/queue/stats")
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "queue boom"

        monkeypatch.setattr(enhanced_api, "get_websocket_manager", lambda: _raise(RuntimeError("ws boom")))
        r = client.get("/ws/stats")
        assert r.status_code == 500
        assert (r.json() or {}).get("detail") == "ws boom"

        monkeypatch.setattr(enhanced_api, "get_enhanced_analyzer", lambda: _raise(RuntimeError("component boom")))
        for path in ("/components", "/projects", "/educational", "/repair"):
            r = client.get(path)
            assert r.status_code == 500
            assert (r.json() or {}).get("detail") == "component boom"

        monkeypatch.setattr(
            enhanced_api,
            "get_workflow_engine",
            lambda: types.SimpleNamespace(execute_validation_workflow=lambda **kwargs: _raise(RuntimeError("validate boom"))),
        )
        with DEMO_PCB.open("rb") as pf:
            r = client.post("/validate-kicad", files={"kicad_file": (DEMO_PCB.name, pf, "text/plain")})
        assert r.status_code == 500
        payload = r.json() or {}
        assert payload.get("status") == "error"
        assert payload.get("message") == "validate boom"


def test_enhanced_api_websocket_invalid_message_disconnects():
    with TestClient(enhanced_api.app) as client:
        with client.websocket_connect("/ws/bad-client") as websocket:
            message = json.loads(websocket.receive_text())
            assert message["type"] == "connection_established"
            websocket.send_text("{bad json")
        stats = client.get("/ws/stats")
        assert stats.status_code == 200
        assert (stats.json() or {}).get("active_connections") == 0
