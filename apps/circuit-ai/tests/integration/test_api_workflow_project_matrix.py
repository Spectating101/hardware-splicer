from __future__ import annotations

import json
import subprocess
import sys
import tempfile
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


def _json_post(client, path: str, payload, **kwargs):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **kwargs)


def test_flask_workflow_and_manufacturing_json_branches(client, monkeypatch):
    class Issue:
        def __init__(self, severity, component, issue, solution, physics=None):
            self.severity = severity
            self.component = component
            self.issue = issue
            self.solution = solution
            self.physics = physics

    class Result:
        def __init__(self, status, issues):
            self.status = status
            self.validation_issues = issues
            self.next_steps = ["review"]

    monkeypatch.setattr(
        api_server.workflow_engine,
        "execute_validation_workflow",
        lambda **kwargs: Result("validation_partial", [Issue("warning", "U1", "Warn", "Fix", {"drop": 0.2})]),
    )
    r = _json_post(client, "/api/v2/workflow/validate-kicad", {"kicad_file": str(DEMO_NET), "hints": {"lane": "generic"}})
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "validation_partial"
    assert payload.get("manufacturing_ready") is False
    assert (payload.get("validation") or {}).get("warnings") == 1

    monkeypatch.setattr(api_server.workflow_engine, "execute_validation_workflow", lambda **kwargs: Result("validation_ok", []))
    r = _json_post(client, "/api/v2/workflow/validate-kicad", {"kicad_file": str(DEMO_NET)})
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("manufacturing_ready") is True
    assert (payload.get("validation") or {}).get("issues_count") == 0

    r = _json_post(client, "/api/v2/manufacture/bom", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "netlist_path required"

    r = _json_post(client, "/api/v2/manufacture/bom", {"netlist_path": str(DEMO_NET), "format": "csv"})
    assert r.status_code == 200
    assert r.headers.get("Content-Type", "").startswith("text/csv")

    r = _json_post(client, "/api/v2/manufacture/gerber", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "pcb_path required"

    r = _json_post(client, "/api/v2/manufacture/gerber", {"pcb_path": str(DEMO_PCB), "quantity": 3})
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "success"

    r = _json_post(client, "/api/v2/manufacture/pnp", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "pcb_path required"

    r = _json_post(client, "/api/v2/manufacture/pnp", {"pcb_path": str(DEMO_PCB)})
    assert r.status_code == 200
    assert (r.get_json() or {}).get("status") == "success"

    r = client.post("/api/v2/report/dfm", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "pcb_file required"

    monkeypatch.setattr(api_server.workflow_engine, "execute_validation_workflow", lambda **kwargs: Result("validation_ok", []))
    with DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/report/dfm",
            data={"pcb_file": (pf, DEMO_PCB.name), "hints": json.dumps({"lane": "generic"})},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    payload = r.get_json() or {}
    assert payload.get("status") == "success"
    assert payload.get("manufacturing_ready") is True

    r = client.post("/api/v2/manufacture/package", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "pcb_file required"

    captured = {}

    def fake_build_package(**kwargs):
        captured.update(kwargs)
        fake_package = Path(tempfile.gettempdir()) / "circuit-ai" / "packages" / "fake-package.zip"
        fake_package.parent.mkdir(parents=True, exist_ok=True)
        fake_package.write_bytes(b"zip")
        return {"status": "success", "package_file": str(fake_package), "manifest": {"ok": True}}

    monkeypatch.setattr(api_server, "_build_manufacturing_package", fake_build_package)
    monkeypatch.setattr(api_server.shutil, "which", lambda name: "/usr/bin/kicad-cli")
    monkeypatch.setattr(api_server.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("cli failed")))
    with DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/manufacture/package",
            data={"pcb_file": (pf, DEMO_PCB.name), "sch_file": (Path(DEMO_NET).open("rb"), "board.kicad_sch")},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    assert captured.get("netlist_export_method") == "failed"
    assert "cli failed" in (captured.get("netlist_export_error") or "")

    strict_seen = {}

    def fake_should_block(readiness, strict):
        strict_seen["strict"] = strict
        return None

    monkeypatch.setattr(api_server, "_should_block_for_intake", fake_should_block)
    monkeypatch.setattr(api_server, "_load_hints_from_intake_id", lambda intake_id: {"hint": True})
    monkeypatch.setattr(api_server, "_load_requirements_from_intake_id", lambda intake_id: {"meta": {"lane": "generic"}})
    with DEMO_PCB.open("rb") as pf:
        r = client.post(
            "/api/v2/manufacture/package",
            data={"pcb_file": (pf, DEMO_PCB.name), "intake_id": "intake123", "allow_incomplete": "true"},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    assert strict_seen["strict"] is False


def test_flask_project_route_branches(client, monkeypatch):
    r = client.post("/api/v2/projects", data="not-json", content_type="text/plain")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "JSON body required"

    r = _json_post(client, "/api/v2/projects", {})
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "name required"

    r = _json_post(client, "/api/v2/projects", {"name": "Bad", "lane": "bad"})
    assert r.status_code == 400
    assert "unknown lane" in ((r.get_json() or {}).get("error") or "")

    r = _json_post(client, "/api/v2/projects", {"name": "Bad", "design_intent": "bad"})
    assert r.status_code == 400
    assert "unknown design_intent" in ((r.get_json() or {}).get("error") or "")

    r = client.get("/api/v2/projects/missing-project")
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "not found"

    r = client.post("/api/v2/projects/missing-project/revisions", data="not-json", content_type="text/plain")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "JSON body required"

    r = _json_post(client, "/api/v2/projects/missing-project/revisions", {})
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "project not found"

    r = _json_post(client, "/api/v2/projects", {"name": "Project Branches"})
    assert r.status_code == 200
    project_id = (r.get_json() or {}).get("project_id")
    assert project_id

    r = client.get(f"/api/v2/projects/{project_id}/diff")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "from and to revision ids required"

    r = client.get(f"/api/v2/projects/{project_id}/diff?from=a&to=b")
    assert r.status_code == 404
    assert (r.get_json() or {}).get("error") == "revision not found or missing intake_id"

    r = client.post(f"/api/v2/projects/{project_id}/build-package", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert (r.get_json() or {}).get("error") == "no revision/intake found"

    monkeypatch.setattr(
        api_server,
        "_db_fetchone",
        lambda query, params=(): ("bad", "bad", "Broken") if "SELECT lane, design_intent, name FROM projects" in query else None,
    )
    r = _json_post(client, f"/api/v2/projects/{project_id}/revisions", {})
    assert r.status_code == 500
    assert (r.get_json() or {}).get("error") == "project has invalid lane/design_intent"
