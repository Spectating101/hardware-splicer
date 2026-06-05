from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))


def test_splice_endpoint_returns_script_fallback_when_cadquery_is_unavailable(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src.api.main import app
    import src.api.routes.splice as splice_route

    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, *args, **kwargs):
        if name == "cadquery":
            return None
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(splice_route.importlib.util, "find_spec", fake_find_spec)

    response = TestClient(app).post(
        "/v1/splice",
        json={
            "version": "v1",
            "device": "api_fallback_board",
            "pcb": {"width_mm": 80, "height_mm": 50, "thickness_mm": 1.6, "corner_radius_mm": 3},
            "enclosure": {"wall_mm": 2.4, "clearance_mm": 0.5, "lip_mm": 2.0, "fillet_mm": 1.0},
            "ports": [],
            "mounts": [{"x_mm": 6, "y_mm": 6, "diameter_mm": 2.2}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["ok"] is False
    assert data["mode"] == "script_fallback"
    assert data["validation"]["reason"] == "cadquery_unavailable"
    assert "import cadquery" in data["script"]
    assert "result = case" in data["script"]
