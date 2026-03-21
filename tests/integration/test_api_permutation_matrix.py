from __future__ import annotations

import io
import json
import sys
import tempfile
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server

DEMO_PCB = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.kicad_pcb"
DEMO_NET = REPO_ROOT / "circuit-ai-frontend" / "public" / "demo" / "usb_esp32_sensor.net"

REQUIREMENTS = {
    "meta": {"project_name": "Permutation Intake", "lane": "generic", "design_intent": "prototype"},
    "manufacturing": {"fab": {"name": "JLCPCB"}, "dnp_policy": "allow"},
    "board": {"layers": 2},
    "risk_and_validation": {"what_good_looks_like": "boots and reports state"},
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.setenv("CIRCUIT_AI_USAGE_DB", str(tmp_path / "usage.sqlite"))
    monkeypatch.delenv("CIRCUIT_AI_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_SUPPORT_FROM_EMAIL", raising=False)
    return api_server.app.test_client()


def _json_post(client, path: str, payload, **kwargs):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **kwargs)


def _raise(exc: Exception):
    raise exc


def test_flask_recipe_repair_and_diagnostic_branches(client, monkeypatch):
    r = _json_post(client, "/api/recipes/generate", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "inventory field required"

    r = _json_post(client, "/api/recipes/shopping-list", {"inventory": []})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "inventory and recipe_name required"

    r = _json_post(client, "/api/recipes/shopping-list", {"inventory": [], "recipe_name": "missing"})
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "Recipe not found"

    r = _json_post(client, "/api/recipes/filter", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "inventory field required"

    r = _json_post(client, "/api/recipes/budget-optimize", {"inventory": []})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "inventory and budget fields required"

    monkeypatch.setattr(api_server.instructions_gen, "generate_instructions", lambda project_name: None)
    r = client.get("/api/instructions/not-a-project")
    assert r.status_code == 404
    assert "Instructions not found" in ((r.get_json() or {}).get("error") or "")

    guide = {"title": "Repair Guide", "steps": [{"n": 1}, {"n": 2}, {"n": 3}, {"n": 4}]}
    monkeypatch.setattr(api_server.repair_guide_gen, "generate_repair_guide", lambda issue_name, device_model=None: dict(guide))
    monkeypatch.setattr(api_server.payment_service, "check_access", lambda user_id, issue_name: {"has_access": False})

    r = client.get("/api/repair-guides/Test%20Guide?user_id=user@example.com")
    assert r.status_code == 402
    payload = r.get_json() or {}
    assert payload.get("preview") is True
    assert payload.get("error") == "Payment required"

    r = client.get("/api/repair-guides/Test%20Guide?preview=true")
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("preview_mode") is True
    assert len(payload.get("steps") or []) == 3

    monkeypatch.setattr(api_server.repair_guide_gen, "generate_repair_guide", lambda issue_name, device_model=None: None)
    r = client.get("/api/repair-guides/Test%20Guide")
    assert r.status_code == 404
    assert "Repair guide not found" in ((r.get_json() or {}).get("error") or "")

    r = _json_post(client, "/api/diagnose", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "Missing required field: symptoms"

    r = _json_post(client, "/api/diagnose", {"symptoms": "not-a-list"})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "symptoms must be a non-empty list"

    monkeypatch.setattr(
        api_server.diagnostic_engine,
        "diagnose_from_symptoms",
        lambda symptoms, device_type: _raise(RuntimeError("diagnostics boom")),
    )
    r = _json_post(client, "/api/diagnose", {"symptoms": ["won't charge"]})
    assert r.status_code == 500
    assert (r.get_json() or {}).get("error") == "diagnostics boom"


def test_flask_payment_support_and_stripe_permutations(client, monkeypatch):
    captured_emails = []

    def fake_send_email(*args, **kwargs):
        captured_emails.append({"args": args, "kwargs": kwargs})
        return True

    monkeypatch.setenv("CIRCUIT_AI_SENDGRID_API_KEY", "sg-test")
    monkeypatch.setenv("CIRCUIT_AI_SUPPORT_FROM_EMAIL", "support@example.com")
    monkeypatch.setattr(api_server, "_send_email_sendgrid", fake_send_email)

    r = _json_post(
        client,
        "/api/v2/support/tickets",
        {"email": "permutation@example.com", "subject": "Need help", "message": "Testing email path"},
    )
    assert r.status_code == 200
    assert captured_emails

    r = _json_post(client, "/api/payment/create-checkout", None)
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "Missing request body"

    r = _json_post(client, "/api/payment/create-checkout", {"product_type": "guide_onetime"})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "repair_guide is required"

    monkeypatch.setattr(
        api_server.payment_service,
        "create_checkout_session",
        lambda **kwargs: {"error": "invalid product"},
    )
    r = _json_post(client, "/api/payment/create-checkout", {"product_type": "guide_onetime", "repair_guide": "Guide A"})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "invalid product"

    monkeypatch.setattr(
        api_server.payment_service,
        "create_checkout_session",
        lambda **kwargs: {"checkout_url": "https://checkout.test/session", "session_id": "cs_test_123"},
    )
    r = _json_post(client, "/api/payment/create-checkout", {"product_type": "guide_onetime", "repair_guide": "Guide A"})
    assert r.status_code == 200
    assert (r.get_json() or {}).get("session_id") == "cs_test_123"

    r = client.get("/api/payment/verify")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "session_id is required"

    monkeypatch.setattr(
        api_server.payment_service,
        "verify_payment",
        lambda session_id: {"access_granted": False, "reason": "unpaid"},
    )
    r = client.get("/api/payment/verify?session_id=cs_test_123")
    assert r.status_code == 402
    assert (r.get_json() or {}).get("reason") == "unpaid"

    monkeypatch.setattr(
        api_server.payment_service,
        "verify_payment",
        lambda session_id: {"access_granted": True, "purchase_id": "purchase_123"},
    )
    r = client.get("/api/payment/verify?session_id=cs_test_123")
    assert r.status_code == 200
    assert (r.get_json() or {}).get("purchase_id") == "purchase_123"

    r = _json_post(client, "/api/payment/check-access", None)
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "Missing request body"

    r = _json_post(client, "/api/payment/check-access", {"user_identifier": "user@example.com"})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "user_identifier and repair_guide are required"

    monkeypatch.setattr(
        api_server.payment_service,
        "check_access",
        lambda user_identifier, repair_guide: {"has_access": False, "reason": "purchase_required"},
    )
    r = _json_post(
        client,
        "/api/payment/check-access",
        {"user_identifier": "user@example.com", "repair_guide": "Guide A"},
    )
    assert r.status_code == 402
    assert (r.get_json() or {}).get("reason") == "purchase_required"

    monkeypatch.setattr(
        api_server.payment_service,
        "check_access",
        lambda user_identifier, repair_guide: {"has_access": True, "type": "pro_subscription"},
    )
    r = _json_post(
        client,
        "/api/payment/check-access",
        {"user_identifier": "user@example.com", "repair_guide": "Guide A"},
    )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("type") == "pro_subscription"

    monkeypatch.setattr(api_server.payment_service, "get_analytics", lambda: _raise(RuntimeError("analytics boom")))
    r = client.get("/api/payment/analytics")
    assert r.status_code == 500
    assert (r.get_json() or {}).get("error") == "analytics boom"

    class FakeStripeModule:
        api_key = ""

        class Webhook:
            @staticmethod
            def construct_event(payload, sig_header, secret):
                return json.loads(payload.decode("utf-8"))

        class checkout:
            class Session:
                @staticmethod
                def list_line_items(session_id, limit=10):
                    return types.SimpleNamespace(data=[{"price": {"id": "price_pro"}}])

    monkeypatch.setitem(sys.modules, "stripe", FakeStripeModule)
    monkeypatch.setenv("CIRCUIT_AI_STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setenv("CIRCUIT_AI_STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(api_server, "_stripe_price_plan_map", lambda: {"price_pro": "pro"})

    r = client.post(
        "/api/v2/webhooks/stripe",
        data=json.dumps({"id": "evt_ignore", "type": "invoice.paid", "data": {"object": {"id": "sess_ignore"}}}),
        content_type="application/json",
        headers={"Stripe-Signature": "sig"},
    )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "ignored"

    r = client.post(
        "/api/v2/webhooks/stripe",
        data=json.dumps({"id": "evt_dup", "type": "invoice.paid", "data": {"object": {"id": "sess_dup"}}}),
        content_type="application/json",
        headers={"Stripe-Signature": "sig"},
    )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "ignored"
    r = client.post(
        "/api/v2/webhooks/stripe",
        data=json.dumps({"id": "evt_dup", "type": "invoice.paid", "data": {"object": {"id": "sess_dup"}}}),
        content_type="application/json",
        headers={"Stripe-Signature": "sig"},
    )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "duplicate_ignored"

    r = client.post(
        "/api/v2/webhooks/stripe",
        data=json.dumps({"id": "evt_missing_email", "type": "checkout.session.completed", "data": {"object": {"id": "sess_missing"}}}),
        content_type="application/json",
        headers={"Stripe-Signature": "sig"},
    )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "pending_manual"
    assert payload.get("reason") == "missing_email"

    monkeypatch.delenv("CIRCUIT_AI_SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("CIRCUIT_AI_SUPPORT_FROM_EMAIL", raising=False)
    r = client.post(
        "/api/v2/webhooks/stripe",
        data=json.dumps(
            {
                "id": "evt_email_config",
                "type": "checkout.session.completed",
                "data": {"object": {"id": "sess_email_config", "customer_details": {"email": "buyer@example.com"}}},
            }
        ),
        content_type="application/json",
        headers={"Stripe-Signature": "sig"},
    )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "pending_manual"
    assert payload.get("reason") == "email_not_configured"

    monkeypatch.setenv("CIRCUIT_AI_SENDGRID_API_KEY", "sg-test")
    monkeypatch.setenv("CIRCUIT_AI_SUPPORT_FROM_EMAIL", "support@example.com")
    monkeypatch.setattr(api_server, "_send_email_sendgrid", lambda **kwargs: True)
    r = client.post(
        "/api/v2/webhooks/stripe",
        data=json.dumps(
            {
                "id": "evt_delivered",
                "type": "checkout.session.completed",
                "data": {"object": {"id": "sess_delivered", "customer_details": {"email": "delivered@example.com"}}},
            }
        ),
        content_type="application/json",
        headers={"Stripe-Signature": "sig"},
    )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "delivered_email"

    monkeypatch.setattr(api_server, "_send_email_sendgrid", lambda **kwargs: False)
    r = client.post(
        "/api/v2/webhooks/stripe",
        data=json.dumps(
            {
                "id": "evt_failed_delivery",
                "type": "checkout.session.completed",
                "data": {"object": {"id": "sess_failed", "customer_details": {"email": "failed@example.com"}}},
            }
        ),
        content_type="application/json",
        headers={"Stripe-Signature": "sig"},
    )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "delivery_failed"


def test_flask_intake_report_and_manual_tooling_permutations(client):
    r = client.get("/api/v2/intake/template?lane=unknown")
    assert r.status_code == 400
    assert "unknown lane" in ((r.get_json() or {}).get("error") or "")

    r = client.get("/api/v2/intake/template?lane=generic&design_intent=bad")
    assert r.status_code == 400
    assert "unknown design_intent" in ((r.get_json() or {}).get("error") or "")

    r = client.get("/api/v2/intake/missing")
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "not found"

    with DEMO_NET.open("rb") as nf:
        r = client.post(
            "/api/v2/intake/compile",
            data={
                "requirements_file": (io.BytesIO(json.dumps(REQUIREMENTS).encode("utf-8")), "requirements.json"),
                "netlist_file": (nf, DEMO_NET.name),
            },
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "success"
    assert payload.get("intake_id")

    r = _json_post(client, "/api/v2/intake/compile", {"requirements": {"meta": {"lane": "bad", "design_intent": "prototype"}}})
    assert r.status_code == 400
    assert "unknown lane" in ((r.get_json() or {}).get("error") or "")

    r = _json_post(
        client,
        "/api/v2/intake/compile",
        {"requirements": {"meta": {"lane": "generic", "design_intent": "bad"}}},
    )
    assert r.status_code == 400
    assert "unknown design_intent" in ((r.get_json() or {}).get("error") or "")

    with DEMO_NET.open("rb") as nf, DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/report/ee-quality",
            data={
                "requirements": json.dumps(REQUIREMENTS),
                "netlist_file": (nf, DEMO_NET.name),
                "pcb_file": (pf, DEMO_PCB.name),
            },
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "success"
    assert "report_md" in payload

    r = client.post("/api/v2/report/ee-quality", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "requirements object required"

    r = client.post("/api/v2/simulate/spice", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "netlist_text required"

    with DEMO_NET.open("rb") as nf:
        r = client.post(
            "/api/v2/simulate/spice",
            data={"netlist_file": (nf, DEMO_NET.name), "timeout_s": "5"},
            content_type="multipart/form-data",
        )
    assert r.status_code in (200, 501)

    r = client.post("/api/v2/mechanical/bom", data="not-json", content_type="text/plain")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "JSON body required"

    r = _json_post(client, "/api/v2/mechanical/bom", {"work_area_mm": [100, 80], "accuracy_mm": 0.3, "prefer": "bad"})
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "success"

    r = client.post("/api/v2/layout/advice", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "pcb_file required"

    r = client.post("/api/v2/prototype3d/package", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "pcb_file required"

    with DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/prototype3d/package",
            data={"pcb_file": (pf, DEMO_PCB.name), "requirements": "{bad json"},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "success"

    r = client.post("/api/v2/robot/probe-plan", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "pcb_file required"

    with DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/robot/probe-plan",
            data={"pcb_file": (pf, DEMO_PCB.name), "plan": "{bad json"},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "success"


def test_flask_machine_permutation_branches(client, monkeypatch):
    r = client.post("/api/v2/machines/compile", data="not-json", content_type="text/plain")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "JSON body required"

    import src.engines.machine_requirements as machine_requirements
    import src.engines.machine_system_engineering as machine_system_engineering

    monkeypatch.setattr(machine_requirements, "compile_machine_requirements", lambda payload: _raise(ValueError("compile bad")))
    r = _json_post(client, "/api/v2/machines/compile", {"machine_name": "Bad", "boards": [{"board_id": "a"}]})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "compile bad"

    r = client.post("/api/v2/machines/build-package", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "machine_json required"

    r = client.post(
        "/api/v2/machines/build-package",
        data={"machine_json": "{bad json"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "invalid machine_json" in ((r.get_json() or {}).get("error") or "")

    r = client.post(
        "/api/v2/machines/build-package",
        data={"machine_json": json.dumps(["not", "an", "object"])},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "machine_json must decode to an object"

    r = client.post(
        "/api/v2/machines/build-package",
        data={"machine_json": json.dumps({"machine_name": "NoBoards", "boards": []})},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "machine_json.boards[] is required"

    monkeypatch.setattr(
        machine_requirements,
        "compile_machine_requirements",
        lambda payload: {
            "machine": {"machine_name": payload.get("machine_name") or "Stub", "board_count": 1},
            "boards": [{"board_id": "main_ctrl", "hints": {"lane": "generic"}}],
            "system": {"sow_md": "# system", "harness_bom_csv": "a,b", "interconnects": [], "power_tree": [], "mecha_electronics_anchors": []},
            "hints": {"machine": "stub"},
        },
    )

    r = client.post(
        "/api/v2/machines/build-package",
        data={"machine_json": json.dumps({"machine_name": "MissingUpload", "boards": [{"board_id": "main_ctrl"}]})},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    payload = r.get_json() or {}
    assert payload.get("error") == "missing board pcb uploads"
    assert (payload.get("missing") or [])[0]["expected_field"] == "pcb_file_main_ctrl"

    fake_board_package = Path(tempfile.gettempdir()) / "circuit-ai" / "fake-board-package.zip"
    fake_board_package.parent.mkdir(parents=True, exist_ok=True)
    fake_board_package.write_bytes(b"fake-zip")

    monkeypatch.setattr(
        api_server,
        "_build_manufacturing_package",
        lambda **kwargs: {
            "status": "success",
            "package_file": str(fake_board_package),
            "manifest": {"generated": True},
        },
    )
    with DEMO_PCB.open("rb") as pf, DEMO_NET.open("rb") as nf:
        r = client.post(
            "/api/v2/machines/build-package",
            data={
                "machine_json": json.dumps(
                    {
                        "machine_name": "StubPkg",
                        "boards": [
                            {
                                "board_id": "main_ctrl",
                                "pcb_form_field": "pcb_main",
                                "netlist_form_field": "net_main",
                            }
                        ],
                    }
                ),
                "pcb_main": (pf, "main_ctrl.kicad_pcb"),
                "net_main": (nf, "main_ctrl.net"),
            },
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "success"
    assert payload.get("machine_package_file")

    r = client.post("/api/v2/machines/engineer", data="not-json", content_type="text/plain")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "JSON body required"

    r = _json_post(client, "/api/v2/machines/engineer", {"machine": "bad"})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "machine object required"

    r = _json_post(client, "/api/v2/machines/engineer", {"machine": {}, "mechanism": "bad"})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "mechanism must be an object"

    monkeypatch.setattr(machine_system_engineering, "engineer_machine_system", lambda *args, **kwargs: _raise(ValueError("engineer bad")))
    r = _json_post(client, "/api/v2/machines/engineer", {"machine": {"boards": []}})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "engineer bad"

    r = client.post(
        "/api/v2/machines/full-simulate",
        data={"machine_json": "{bad json"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "invalid machine_json" in ((r.get_json() or {}).get("error") or "")

    r = client.post(
        "/api/v2/machines/full-simulate",
        data={"machine_json": json.dumps({"boards": [{"board_id": "main_ctrl"}]}), "mechanism_json": "{bad json"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "invalid mechanism_json" in ((r.get_json() or {}).get("error") or "")

    r = _json_post(client, "/api/v2/machines/full-simulate", {"machine": {}})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "machine object required"

    r = _json_post(client, "/api/v2/machines/full-simulate", {"machine": {"boards": []}})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "machine.boards[] is required"

    captured = {}

    def fake_full_simulate(machine, board_design_files, mechanism_spec, simulation_fidelity, strict):
        captured["machine"] = machine
        captured["board_design_files"] = board_design_files
        captured["mechanism_spec"] = mechanism_spec
        captured["simulation_fidelity"] = simulation_fidelity
        captured["strict"] = strict
        return {
            "verdict": "pass",
            "gates": [],
            "board_simulations": [],
            "engineering": {"compiled": {"hints": {"ok": True}}},
            "report_md": "# full sim",
        }

    monkeypatch.setattr(machine_system_engineering, "full_simulate_machine_system", fake_full_simulate)
    with DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/machines/full-simulate",
            data={
                "machine_json": json.dumps({"machine_name": "FullSim", "boards": [{"board_id": "main_ctrl"}]}),
                "mechanism_json": json.dumps({"kind": "gantry"}),
                "strict": "false",
                "simulation_fidelity": "nonsense",
                "pcb_file_main_ctrl": (pf, "main_ctrl.kicad_pcb"),
            },
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "success"
    assert captured["strict"] is False
    assert captured["simulation_fidelity"] == "high"
    assert captured["board_design_files"]["main_ctrl"]["kind"] == "pcb"
