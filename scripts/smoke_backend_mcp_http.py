#!/usr/bin/env python3
"""Exercise canonical HS mutation/readback over a real Streamable HTTP MCP transport."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mcp import Client


_REQUIRED_TOOLS = {
    "hs_backend_status",
    "hs_backend_list_operations",
    "hs_backend_describe_operation",
    "hs_backend_call",
}


def _json_text(result) -> dict:
    if getattr(result, "is_error", False):
        raise AssertionError(f"MCP tool returned an error result: {result}")
    for block in result.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return json.loads(text)
    raise AssertionError("MCP result contained no JSON text block")


def _operation_id(rows: list[dict], method: str, path: str) -> str:
    matches = [
        row["operation_id"]
        for row in rows
        if row.get("method") == method and row.get("path") == path
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {method} {path} operation, got {matches}")
    return matches[0]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen[str], timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(
                "Streamable HTTP MCP server exited before accepting connections:\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"Streamable HTTP MCP server did not listen on port {port}")


async def _exercise(url: str) -> dict:
    async with Client(url, read_timeout_seconds=20) as client:
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        missing = sorted(_REQUIRED_TOOLS.difference(names))
        if missing:
            raise AssertionError(f"canonical backend MCP missing tools: {missing}")

        status = _json_text(await client.call_tool("hs_backend_status", {}))
        if status.get("surface") != "canonical_product_api":
            raise AssertionError(f"unexpected MCP backend surface: {status}")
        if status.get("operation_count", 0) <= 0:
            raise AssertionError("MCP backend exposed zero canonical operations")
        authority = status.get("authority_contract") or {}
        if authority.get("mcp_grants_physical_authority") is not False:
            raise AssertionError("MCP backend must remain authority-neutral")

        project_ops = _json_text(
            await client.call_tool(
                "hs_backend_list_operations",
                {"path_prefix": "/v1/projects", "limit": 100},
            )
        ).get("operations") or []
        save_operation_id = _operation_id(project_ops, "PUT", "/v1/projects/{project_id}/snapshot")
        load_operation_id = _operation_id(project_ops, "GET", "/v1/projects/{project_id}")
        delete_operation_id = _operation_id(project_ops, "DELETE", "/v1/projects/{project_id}")

        described = _json_text(
            await client.call_tool(
                "hs_backend_describe_operation",
                {"operation_id": save_operation_id},
            )
        )
        if described.get("path") != "/v1/projects/{project_id}/snapshot":
            raise AssertionError(f"operation description drift: {described}")

        project_id = "mcp-http-contract-smoke"
        save_result = _json_text(
            await client.call_tool(
                "hs_backend_call",
                {
                    "operation_id": save_operation_id,
                    "path_params": {"project_id": project_id},
                    "json_body": {
                        "snapshot": {
                            "name": "MCP Streamable HTTP contract smoke",
                            "mode": "contract_test",
                            "current_stage": "remote_mcp",
                            "physical_authority_granted": False,
                        },
                        "expected_revision": 0,
                        "metadata": {"source": "mcp_streamable_http_contract"},
                    },
                },
            )
        )
        if save_result.get("status_code") != 200 or save_result.get("ok") is not True:
            raise AssertionError(f"project save failed through remote MCP: {save_result}")

        load_result = _json_text(
            await client.call_tool(
                "hs_backend_call",
                {
                    "operation_id": load_operation_id,
                    "path_params": {"project_id": project_id},
                },
            )
        )
        loaded_project = (load_result.get("body") or {}).get("project") or {}
        if load_result.get("status_code") != 200 or loaded_project.get("revision") != 1:
            raise AssertionError(f"project readback failed through remote MCP: {load_result}")
        if (loaded_project.get("snapshot") or {}).get("name") != "MCP Streamable HTTP contract smoke":
            raise AssertionError(f"remote MCP readback did not preserve canonical state: {load_result}")

        delete_result = _json_text(
            await client.call_tool(
                "hs_backend_call",
                {
                    "operation_id": delete_operation_id,
                    "path_params": {"project_id": project_id},
                },
            )
        )
        if delete_result.get("status_code") != 200 or delete_result.get("ok") is not True:
            raise AssertionError(f"project cleanup failed through remote MCP: {delete_result}")

        return {
            "mcp_connection": "pass",
            "transport": "streamable-http",
            "negotiated_protocol_version": str(client.protocol_version),
            "mcp_tool_discovery": "pass",
            "canonical_operation_count": status["operation_count"],
            "operation_description": "pass",
            "canonical_stateful_write_read_delete": "pass",
            "physical_authority_granted": False,
        }


def main() -> int:
    port = _free_port()
    with tempfile.TemporaryDirectory(prefix="hs-mcp-http-contract-") as project_root:
        env = os.environ.copy()
        env.update(
            {
                "HARDWARE_SPLICER_PROJECT_ROOT": project_root,
                "HS_MCP_TRANSPORT": "streamable-http",
                "HS_MCP_REMOTE_EXPERIMENT": "1",
                "HS_MCP_HOST": "127.0.0.1",
                "HS_MCP_PORT": str(port),
            }
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "hardware_splicer.backend_mcp_server"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for_port(port, process)
            result = asyncio.run(_exercise(f"http://127.0.0.1:{port}/mcp"))
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
