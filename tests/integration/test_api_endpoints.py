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
