from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.enhanced_api import app

DEMO_NET = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.net"
DEMO_PCB = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"

EXPECTED_ENHANCED_ROUTES = {
    "/",
    "/analyze",
    "/analyze/netlist",
    "/api/proxy/health",
    "/batch_analyze",
    "/cache/clear",
    "/cache/stats",
    "/components",
    "/docs",
    "/docs/oauth2-redirect",
    "/educational",
    "/generate/bom",
    "/health",
    "/job/{job_id}",
    "/metrics",
    "/openapi.json",
    "/projects",
    "/queue/stats",
    "/redoc",
    "/repair",
    "/statistics",
    "/validate-kicad",
    "/ws/stats",
}

EXPECTED_ENHANCED_WEBSOCKET_ROUTES = {
    "/ws/{client_id}",
}


def test_enhanced_api_route_inventory_matches_contract():
    routes = {
        route.path
        for route in app.routes
        if getattr(route, "methods", None)
    }
    assert routes == EXPECTED_ENHANCED_ROUTES

    websocket_routes = {
        route.path
        for route in app.routes
        if route.__class__.__name__ == "APIWebSocketRoute"
    }
    assert websocket_routes == EXPECTED_ENHANCED_WEBSOCKET_ROUTES


def test_enhanced_api_route_matrix():
    with TestClient(app) as client:
        for path in (
            "/",
            "/health",
            "/statistics",
            "/cache/stats",
            "/queue/stats",
            "/ws/stats",
            "/components",
            "/projects",
            "/educational",
            "/repair",
            "/metrics",
            "/docs",
            "/docs/oauth2-redirect",
            "/openapi.json",
            "/redoc",
            "/api/proxy/health",
        ):
            r = client.get(path)
            assert r.status_code == 200, path

        r = client.post("/cache/clear")
        assert r.status_code == 200
        assert (r.json() or {}).get("message") == "Cache cleared successfully"

        r = client.post("/batch_analyze", json={"image_paths": ["/tmp/a.png"], "analysis_options": {}})
        assert r.status_code == 200
        batch = r.json()
        assert batch.get("job_id")
        assert batch.get("status") == "submitted"

        r = client.get(f"/job/{batch['job_id']}")
        assert r.status_code == 200
        assert (r.json() or {}).get("job_id") == batch["job_id"]

        r = client.get("/job/missing-job")
        assert r.status_code == 200
        assert (r.json() or {}).get("error") == "Job not found"

        r = client.post("/analyze", files={"file": ("x.txt", b"hello", "text/plain")})
        assert r.status_code == 400
        assert (r.json() or {}).get("detail") == "File must be an image"

        image_buf = io.BytesIO()
        Image.new("RGB", (128, 128), "white").save(image_buf, format="PNG")
        r = client.post("/analyze", files={"file": ("blank.png", image_buf.getvalue(), "image/png")})
        assert r.status_code == 200
        analysis = r.json() or {}
        assert analysis.get("success") is True
        assert analysis.get("file_metadata", {}).get("filename") == "blank.png"

        with DEMO_NET.open("rb") as nf:
            r = client.post("/analyze/netlist", files={"file": (DEMO_NET.name, nf, "text/plain")})
        assert r.status_code == 200
        assert (r.json() or {}).get("status") == "success"

        with DEMO_NET.open("rb") as nf:
            r = client.post("/generate/bom", files={"file": (DEMO_NET.name, nf, "text/plain")})
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")

        with DEMO_PCB.open("rb") as pf:
            r = client.post("/validate-kicad", files={"kicad_file": (DEMO_PCB.name, pf, "text/plain")})
        assert r.status_code == 200
        validate = r.json() or {}
        assert validate.get("status")
        assert "manufacturing_ready" in validate
        assert "validation" in validate


def test_enhanced_api_websocket_matrix():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/test-client") as websocket:
            message = json.loads(websocket.receive_text())
            assert message["type"] == "connection_established"
            assert message["client_id"] == "test-client"

            stats = client.get("/ws/stats")
            assert stats.status_code == 200
            stats_payload = stats.json() or {}
            assert stats_payload.get("active_connections") == 1

            websocket.send_text(json.dumps({"type": "ping"}))
            message = json.loads(websocket.receive_text())
            assert message["type"] == "pong"
            assert message.get("timestamp")

            websocket.send_text(json.dumps({"type": "subscribe_analysis", "analysis_id": "analysis-1"}))
            message = json.loads(websocket.receive_text())
            assert message == {"type": "subscription_confirmed", "analysis_id": "analysis-1"}

            stats = client.get("/ws/stats")
            assert stats.status_code == 200
            stats_payload = stats.json() or {}
            assert stats_payload.get("active_connections") == 1
            assert stats_payload.get("total_subscriptions") == 1
            assert stats_payload.get("active_analyses") == 1

            websocket.send_text(json.dumps({"type": "unsubscribe_analysis", "analysis_id": "analysis-1"}))
            message = json.loads(websocket.receive_text())
            assert message == {"type": "unsubscription_confirmed", "analysis_id": "analysis-1"}

        stats = client.get("/ws/stats")
        assert stats.status_code == 200
        stats_payload = stats.json() or {}
        assert stats_payload.get("active_connections") == 0
