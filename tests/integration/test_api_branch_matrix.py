from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server

DEMO_PCB = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"
DEMO_NET = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.net"

EXPECTED_FLASK_ROUTES = {
    "/",
    "/api/components",
    "/api/design",
    "/api/diagnose",
    "/api/export/fritzing",
    "/api/health",
    "/api/instructions",
    "/api/instructions/<project_name>",
    "/api/learning-paths",
    "/api/learning-paths/<path_id>",
    "/api/learning-paths/recommend",
    "/api/payment/analytics",
    "/api/payment/check-access",
    "/api/payment/create-checkout",
    "/api/payment/verify",
    "/api/pricing/component",
    "/api/pricing/market/<project_name>",
    "/api/recipes/analyze-inventory",
    "/api/recipes/budget-optimize",
    "/api/recipes/filter",
    "/api/recipes/generate",
    "/api/recipes/shopping-list",
    "/api/repair-guides",
    "/api/repair-guides/<path:issue_name>",
    "/api/validate",
    "/api/v2/admin/fulfill",
    "/api/v2/admin/keys",
    "/api/v2/admin/keys/issue",
    "/api/v2/admin/keys/<key_hash>/revoke",
    "/api/v2/admin/ops",
    "/api/v2/intake/<intake_id>",
    "/api/v2/intake/compile",
    "/api/v2/intake/template",
    "/api/v2/layout/advice",
    "/api/v2/machines/build-package",
    "/api/v2/machines/compile",
    "/api/v2/machines/engineer",
    "/api/v2/machines/full-simulate",
    "/api/v2/manufacture/bom",
    "/api/v2/manufacture/download-gerber/<filename>",
    "/api/v2/manufacture/download-package/<filename>",
    "/api/v2/manufacture/gerber",
    "/api/v2/manufacture/package",
    "/api/v2/manufacture/pnp",
    "/api/v2/mechanical/bom",
    "/api/v2/projects",
    "/api/v2/projects/<project_id>",
    "/api/v2/projects/<project_id>/build-package",
    "/api/v2/projects/<project_id>/diff",
    "/api/v2/projects/<project_id>/revisions",
    "/api/v2/projects/catalog",
    "/api/v2/prototype3d/package",
    "/api/v2/report/dfm",
    "/api/v2/report/ee-quality",
    "/api/v2/robot/probe-plan",
    "/api/v2/robot/probe-plan/template",
    "/api/v2/system/extract-board",
    "/api/v2/system/extract-machine",
    "/api/v2/simulate/spice",
    "/api/v2/support/tickets",
    "/api/v2/usage",
    "/api/v2/webhooks/stripe",
    "/api/v2/workflow/beginner",
    "/api/v2/workflow/complete",
    "/api/v2/workflow/validate-kicad",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.delenv("CIRCUIT_AI_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("CIRCUIT_AI_USAGE_DB", str(tmp_path / "usage.sqlite"))
    return api_server.app.test_client()


def _json_post(client, path: str, payload: dict, **kwargs):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **kwargs)


def test_flask_route_inventory_matches_contract():
    routes = {
        rule.rule
        for rule in api_server.app.url_map.iter_rules()
        if rule.rule != "/static/<path:filename>"
    }
    assert routes == EXPECTED_FLASK_ROUTES


def test_flask_export_support_and_stripe_branches(client, monkeypatch):
    r = _json_post(client, "/api/export/fritzing", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "No design provided"

    r = _json_post(
        client,
        "/api/export/fritzing",
        {"project_name": "Branch Test", "microcontroller": "arduino_uno", "components": ["led", "resistor"]},
    )
    assert r.status_code == 200
    assert r.content_type == "application/zip"
    assert "attachment;" in (r.headers.get("Content-Disposition") or "")
    assert len(r.data) > 0

    r = _json_post(
        client,
        "/api/design",
        {"project_name": "Design Branch Test", "microcontroller": "arduino_uno", "components": ["led"], "export": True},
    )
    assert r.status_code == 200
    design = r.get_json() or {}
    assert design.get("validation") is not None
    assert design.get("export_url") == "/api/export/fritzing"

    r = _json_post(client, "/api/v2/support/tickets", {"email": "user@example.com"})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "email_and_message_required"

    r = _json_post(
        client,
        "/api/v2/support/tickets",
        {"email": "user@example.com", "subject": "Help", "message": "Need setup help"},
    )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("ticket_id")

    r = client.post("/api/v2/webhooks/stripe", data="{}", content_type="application/json")
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "stripe_not_configured"

    monkeypatch.setenv("CIRCUIT_AI_STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("CIRCUIT_AI_STRIPE_WEBHOOK_SECRET", "whsec_fake")
    r = client.post(
        "/api/v2/webhooks/stripe",
        data="{}",
        content_type="application/json",
        headers={"Stripe-Signature": "bad"},
    )
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "invalid_signature"


def test_flask_api_key_transport_and_quota_branches(client, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "test_key_123")

    r = client.get("/api/v2/usage")
    assert r.status_code == 401
    assert (r.get_json() or {}).get("error") == "missing_api_key"

    r = client.get("/api/v2/usage", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 403
    assert (r.get_json() or {}).get("error") == "invalid_api_key"

    for headers, url in (
        ({"Authorization": "Bearer test_key_123"}, "/api/v2/usage"),
        ({"X-API-Key": "test_key_123"}, "/api/v2/usage"),
        ({}, "/api/v2/usage?api_key=test_key_123"),
    ):
        r = client.get(url, headers=headers)
        assert r.status_code == 200
        assert (r.get_json() or {}).get("ok") is True

    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.setenv("CIRCUIT_AI_ADMIN_TOKEN", "admin-token")
    admin_headers = {"Authorization": "Bearer admin-token"}

    r = _json_post(
        client,
        "/api/v2/admin/keys",
        {"label": "quota-test", "plan": "custom", "quotas": {"default": 1}, "active": True},
        headers=admin_headers,
    )
    assert r.status_code == 200
    key = (r.get_json() or {}).get("api_key")
    assert key

    r = client.get("/api/v2/usage", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    assert r.headers.get("X-CircuitAI-Quota-Limit") == "1"
    assert r.headers.get("X-CircuitAI-Quota-Remaining") == "0"

    r = client.get("/api/v2/usage", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 429
    payload = r.get_json() or {}
    assert payload.get("error") == "quota_exceeded"
    assert payload.get("action") == "usage"


def test_flask_admin_operator_and_download_branches(client, monkeypatch):
    r = client.get("/api/v2/admin/keys")
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "admin_disabled"

    monkeypatch.setenv("CIRCUIT_AI_ADMIN_TOKEN", "admin-token")

    r = client.get("/api/v2/admin/keys")
    assert r.status_code == 401
    assert (r.get_json() or {}).get("error") == "missing_admin_token"

    r = client.get("/api/v2/admin/keys", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 403
    assert (r.get_json() or {}).get("error") == "invalid_admin_token"

    admin_headers = {"X-Admin-Token": "admin-token"}

    r = _json_post(client, "/api/v2/admin/keys/issue", {"plan": "nope"}, headers=admin_headers)
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "invalid_plan"

    r = _json_post(client, "/api/v2/admin/keys/issue", {"plan": "free", "label": "free-user"}, headers=admin_headers)
    assert r.status_code == 200
    issued = r.get_json() or {}
    key_hash = issued.get("key_hash")
    assert issued.get("api_key")
    assert key_hash

    r = client.get("/api/v2/admin/keys", headers=admin_headers)
    assert r.status_code == 200
    keys = (r.get_json() or {}).get("keys") or []
    assert any(k.get("key_hash") == key_hash for k in keys)

    r = _json_post(
        client,
        "/api/v2/admin/keys",
        {"label": "custom-user", "plan": "custom", "quotas": {"default": 5}, "active": True},
        headers=admin_headers,
    )
    assert r.status_code == 200
    custom = r.get_json() or {}
    assert custom.get("api_key")
    assert custom.get("key_hash")

    r = client.post(f"/api/v2/admin/keys/{key_hash}/revoke", headers=admin_headers)
    assert r.status_code == 200
    assert (r.get_json() or {}).get("active") is False

    r = _json_post(client, "/api/v2/admin/fulfill", {"plan": "pro"}, headers=admin_headers)
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "email_required"

    r = _json_post(
        client,
        "/api/v2/admin/fulfill",
        {"plan": "pro", "email": "buyer@example.com", "payment_ref": "invoice-123"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    fulfill = r.get_json() or {}
    assert fulfill.get("api_key")
    assert fulfill.get("emailed") is False
    assert fulfill.get("mcp_env", {}).get("CIRCUIT_AI_API_KEY")

    _json_post(
        client,
        "/api/v2/support/tickets",
        {"email": "buyer@example.com", "subject": "Ops", "message": "Please help"},
    )
    r = client.get("/api/v2/admin/ops", headers=admin_headers)
    assert r.status_code == 200
    ops = r.get_json() or {}
    assert ops.get("ok") is True
    assert len(ops.get("fulfillments") or []) >= 1
    assert len(ops.get("tickets") or []) >= 1


def test_flask_generated_download_branches(client, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "pro-key")
    auth = {"Authorization": "Bearer pro-key"}

    with DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/manufacture/gerber",
            data={"pcb_file": (pf, DEMO_PCB.name)},
            content_type="multipart/form-data",
            headers=auth,
        )
    assert r.status_code == 200
    gerber = r.get_json() or {}
    gerber_name = Path(gerber["zip_file"]).name

    r = client.get(f"/api/v2/manufacture/download-gerber/{gerber_name}", headers=auth)
    assert r.status_code == 200
    assert r.content_type == "application/zip"
    assert len(r.data) > 0

    r = client.get("/api/v2/manufacture/download-gerber/missing.zip", headers=auth)
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "File not found"

    with DEMO_PCB.open("rb") as pf, DEMO_NET.open("rb") as nf:
        r = client.post(
            "/api/v2/manufacture/package",
            data={"pcb_file": (pf, DEMO_PCB.name), "netlist_file": (nf, DEMO_NET.name)},
            content_type="multipart/form-data",
            headers=auth,
        )
    assert r.status_code == 200
    package = r.get_json() or {}
    package_name = Path(package["package_file"]).name

    r = client.get(f"/api/v2/manufacture/download-package/{package_name}", headers=auth)
    assert r.status_code == 200
    assert r.content_type == "application/zip"
    assert len(r.data) > 0

    r = client.get("/api/v2/manufacture/download-package/missing.zip", headers=auth)
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "File not found"
