#!/usr/bin/env python3
"""Scripted real-MCP reuse control, NOT a live agent or physical validation.

Host prepares a software-only accepted mission; the MCP client receives no human
credential. Output includes the actual runnable ZIP and request/response trace.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import zipfile

from fastapi.testclient import TestClient
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from hardware_splicer.operator_identity import hash_operator_token
from hardware_splicer.product_api import create_product_app
from hardware_splicer.project_store import ProjectStore


async def exercise(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    packet = Path(__file__).resolve().parents[1] / "docs/status/generated/cold-usb-mouse-2026-10-19/SOURCES.md"
    packet_bytes = packet.read_bytes()
    trace = []
    with tempfile.TemporaryDirectory(prefix="hs-intact-mcp-") as temp:
        store = ProjectStore(Path(temp) / "projects")
        store.save("mouse-reuse", {"name": "Document-only reuse software control"}, expected_revision=0)
        token = secrets.token_urlsafe(48)
        old_registry = os.environ.get("HARDWARE_SPLICER_OPERATOR_TOKENS")
        os.environ["HARDWARE_SPLICER_OPERATOR_TOKENS"] = json.dumps({hash_operator_token(token): {"kind": "human", "id": "software-control-host"}})
        try:
            with TestClient(create_product_app(store)) as host:
                admitted = host.post("/v1/projects/mouse-reuse/sources/ingest-file", files={"file": ("public-packet.md", packet_bytes, "text/markdown")}, data={"expected_revision": "1", "authority_ceiling": "declared"})
                admitted.raise_for_status()
                opened = host.post("/v1/projects/mouse-reuse/missions", json={"author": {"kind": "agent", "id": "software-control-preparer"}, "intake": {
                    "goal": "Develop an intact wired-mouse foot-control software review bundle, not a physical build",
                    "inventory": ["Unobserved ordinary wired USB mouse"],
                    "donors": [{"donor_id": "donor:usb-mouse:controller", "label": "Unobserved mouse"}]}})
                opened.raise_for_status()
                mid = opened.json()["mission"]["mission_id"]
                host.post(f"/v1/projects/mouse-reuse/missions/{mid}/accept", headers={"X-HS-Operator-Token": token}).raise_for_status()
        finally:
            if old_registry is None:
                os.environ.pop("HARDWARE_SPLICER_OPERATOR_TOKENS", None)
            else:
                os.environ["HARDWARE_SPLICER_OPERATOR_TOKENS"] = old_registry
        del token
        params = StdioServerParameters(command=sys.executable, args=["-m", "hardware_splicer.backend_mcp_server"],
                                       env={"HARDWARE_SPLICER_PROJECT_ROOT": str(store.root), "HARDWARE_SPLICER_OPERATOR_TOKENS": "{}"})
        async with Client(stdio_client(params), read_timeout_seconds=30) as client:
            async def call(tool, arguments):
                result = await client.call_tool(tool, arguments)
                assert not result.is_error, str(result)
                data = json.loads(next(block.text for block in result.content if getattr(block, "text", None)))
                trace.append({"tool": tool, "arguments": arguments, "response": data})
                assert data.get("ok") is not False, data
                return data
            await call("hs_backend_status", {})
            manifest = await call("hs_backend_task_manifest", {"task": "salvage_fabrication"})
            def operation(method, ending):
                return next(row["operation_id"] for row in manifest["operations"] if row["method"] == method and row["path"].endswith(ending))
            ids = {"project_id": "mouse-reuse", "mission_id": mid}
            await call("hs_backend_describe_operation", {"operation_id": operation("POST", "/events")})
            discovery = await call("hs_backend_call", {"operation_id": operation("GET", "/intact-reuse-spec"), "path_params": ids})
            spec = discovery["body"]["example"]
            await call("hs_backend_call", {"operation_id": operation("POST", "/events"), "path_params": ids,
                       "json_body": {"author": {"kind": "agent", "id": "scripted-mcp-control"}, "event": {
                           "type": "candidate_proposed", "candidate": {"id": "intact_mouse", "kind": "reclaim_heavy", "label": "Intact mouse reuse",
                               "spec": spec, "rationale": "Software control uses the discoverable proposal template; no model inference or measurements."}}}})
            await call("hs_backend_describe_operation", {"operation_id": operation("POST", "/run")})
            run = await call("hs_backend_call", {"operation_id": operation("POST", "/run"), "path_params": {**ids, "candidate_id": "intact_mouse"}, "json_body": {"operation": "intact_reuse"}})
            assert run["body"]["evaluation"]["result"]["errors"] == 0
            name = run["body"]["evaluation"]["artifact"].split("/")[1]
            recorded = await call("hs_backend_call", {"operation_id": operation("GET", "/runs/{name}"), "path_params": {**ids, "name": name}})
            bundle = await call("hs_backend_call", {"operation_id": operation("GET", "/runs/{name}/bundle"), "path_params": {**ids, "name": name}, "response_mode": "base64"})
            data = base64.b64decode(bundle["body_base64"], validate=True)
            report = recorded["body"]["run"]
            assert hashlib.sha256(data).hexdigest() == report["package_sha256"] == bundle["sha256"]
            (output / "intact-input-review.zip").write_bytes(data)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert archive.testzip() is None
                for row in report["files"]:
                    assert hashlib.sha256(archive.read(row["name"])).hexdigest() == row["sha256"]
                delivered = Path(temp) / "delivered"
                archive.extractall(delivered)
            checks = subprocess.run([sys.executable, "-I", str(delivered / "test_adapter.py")], capture_output=True, text=True, timeout=10, check=True)
            assert json.loads(checks.stdout) == report["offline_checks"]
            result = {"kind": "scripted_real_mcp_control_not_live_agent", "project_id": ids["project_id"], "mission_id": mid,
                      "source_packet_sha256": hashlib.sha256(packet_bytes).hexdigest(), "mcp_calls": len(trace),
                      "package_sha256": report["package_sha256"], "package_bytes": len(data), "delivered_checks_replayed": True,
                      "scenario_count": len(report["offline_checks"]["scenarios"]), "recorded_artifact": run["body"]["evaluation"]["artifact"],
                      "project_revision_unchanged_by_checks": store.load("mouse-reuse")["revision"] == 2,
                      "physical_correctness": "UNPROVEN", "physical_authority_granted": False, "trace": trace}
            repo = Path(__file__).resolve().parents[1]
            revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=False)
            result["implementation_commit"] = revision.stdout.strip() if revision.returncode == 0 else None
            result["implementation_file_sha256"] = {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [repo / "src/hardware_splicer/intact_reuse.py", repo / "src/hardware_splicer/intact_reuse_adapter.py",
                             repo / "src/hardware_splicer/mission_executor.py", Path(__file__).resolve()]}
            (output / "RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            return {key: value for key, value in result.items() if key != "trace"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; never overwrite prior evidence")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(exercise(args.output.resolve())), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
