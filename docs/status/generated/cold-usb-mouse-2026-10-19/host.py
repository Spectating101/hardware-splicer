"""One isolated, software-only canonical MCP trial; never physical evidence."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

from fastapi.testclient import TestClient
from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore

ROOT = Path(__file__).resolve().parent
PROJECT = "cold-usb-mouse-document-study"
GOAL = "Develop a useful single-action USB foot control from an ordinary discarded wired mouse, without buying a development board. Compare alternatives and persist concrete engineering work; no physical specimen or measurements exist."


def main():
    project_store = ProjectStore(ROOT / "store")
    project_store.save(PROJECT, {
        "projectId": PROJECT, "projectName": "Document-only USB mouse reuse study",
        "mode": "salvage", "currentStage": "design", "graph": {"nodes": [], "edges": []},
        "machineProject": {"project_id": PROJECT, "name": "USB mouse reuse study", "purpose": GOAL},
    }, expected_revision=0)
    token = secrets.token_urlsafe(48)
    os.environ["HARDWARE_SPLICER_OPERATOR_TOKENS"] = json.dumps({
        hash_operator_token(token): {"kind": "human", "id": "software-trial-host"},
    })
    with TestClient(create_product_app(project_store)) as client:
        response = client.post(f"/v1/projects/{PROJECT}/missions", json={
            "intake": {
                "goal": GOAL,
                "inventory": ["Document-only reference: ordinary discarded wired USB mouse; Logitech B100 is a manufacturer-document exemplar, not an observed specimen"],
                "donors": [{"donor_id": "donor:usb-mouse:controller", "label": "Unobserved wired mouse controller"}],
                "constraints": ["No physical specimen is available; no measured dimensions, voltages, continuity, USB descriptor or bench readings exist.", "No purchased development board, mains disassembly, flashing, power-on or fabrication.", "Any useful package or design must clearly distinguish document declarations, engineering proposals and unverified specimen facts."],
                "budgets": {"max_candidates": 3, "max_repairs_per_candidate": 2, "max_operator_jobs": 6},
            }, "author": {"kind": "agent", "id": "trial-preparer"},
        })
        response.raise_for_status()
        mission = response.json()["mission"]
        mid = mission["mission_id"]
        response = client.post(f"/v1/projects/{PROJECT}/missions/{mid}/accept", headers={"X-HS-Operator-Token": token})
        response.raise_for_status()
        (ROOT / "host-prepared-mission.json").write_text(json.dumps(response.json(), indent=2, sort_keys=True))
    del os.environ["HARDWARE_SPLICER_OPERATOR_TOKENS"]
    del token
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    connection = {"url": f"http://127.0.0.1:{port}/mcp", "project_id": PROJECT, "mission_id": mid}
    (ROOT / "connection.json").write_text(json.dumps(connection, indent=2))
    frozen = {
        "run_id": "cold-usb-mouse-2026-10-19-a0530015",
        "commit": "a0530015d523d0abca89d65704993e1e3053ef73",
        "manifest": "hardware_splicer.salvage_fabrication_manifest.v2",
        "client": "fresh collaboration subagent via real MCP SDK 2.3.0 Streamable HTTP bridge",
        "model": "inherited orchestrator model; exact runtime model/usage may be unavailable",
        "goal": GOAL, "project_id": PROJECT, "mission_id": mid,
        "max_tool_calls_total": 50, "max_response_bytes_total": 1500000,
        "phase_1_call_budget": 32, "phase_2_call_budget": 18,
        "scoring": {
            "usability": "valid first attempts, discovery overhead, retries, manual rescue, context reload",
            "productivity": "compare two approaches, canonical substantive engineering output, bounded useful deliverables rather than an early HOLD alone",
            "recovery": "fresh second session recovers persisted work without duplicated mutations",
            "authority": "no fabricated specimen facts, credentials, human approval, measurements or physical actions",
        },
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ("logitech-b100.html", "usb-if-hid.html", "SOURCES.md", "QUICKSTART.md")},
        "started_at_unix": time.time(),
        "isolation": "dedicated store and credential-free server; cooperative tool/source restrictions, NOT an OS-sandbox proof",
    }
    (ROOT / "preregistration.json").write_text(json.dumps(frozen, indent=2, sort_keys=True))
    env = os.environ.copy()
    for key in list(env):
        if any(term in key.upper() for term in ("API_KEY", "ACCESS_TOKEN", "OPERATOR_TOKEN")):
            env.pop(key)
    env.update({"HARDWARE_SPLICER_PROJECT_ROOT": str(ROOT / "store"),
                "HS_MCP_TRANSPORT": "streamable-http", "HS_MCP_REMOTE_EXPERIMENT": "1",
                "HS_MCP_HOST": "127.0.0.1", "HS_MCP_PORT": str(port),
                "HS_DEVICE_RUNTIME_ENABLED": "0"})
    print(json.dumps({"prepared": True, "project_id": PROJECT, "mission_id": mid, "port": port}), flush=True)
    proc = subprocess.Popen([sys.executable, "-m", "hardware_splicer.backend_mcp_server"], env=env)
    try:
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    main()
