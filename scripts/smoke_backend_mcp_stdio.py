#!/usr/bin/env python3
"""Exercise canonical HS discovery, mutation, persistence, and readback over MCP stdio."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


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


async def run() -> None:
    with tempfile.TemporaryDirectory(prefix="hs-mcp-contract-") as project_root:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "hardware_splicer.backend_mcp_server"],
            env={"HARDWARE_SPLICER_PROJECT_ROOT": project_root},
        )
        transport = stdio_client(params)
        async with Client(transport, read_timeout_seconds=20) as client:
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

            # Read-only discovery/description/invocation path.
            discovered = _json_text(
                await client.call_tool(
                    "hs_backend_list_operations",
                    {"method": "GET", "path_prefix": "/v1/vision/capabilities"},
                )
            )
            operations = discovered.get("operations") or []
            if len(operations) != 1:
                raise AssertionError(f"expected one vision capabilities operation, got {operations}")
            vision_operation_id = operations[0]["operation_id"]

            described = _json_text(
                await client.call_tool(
                    "hs_backend_describe_operation",
                    {"operation_id": vision_operation_id},
                )
            )
            if described.get("path") != "/v1/vision/capabilities":
                raise AssertionError(f"operation description drift: {described}")

            invoked = _json_text(
                await client.call_tool(
                    "hs_backend_call",
                    {"operation_id": vision_operation_id},
                )
            )
            if invoked.get("status_code") != 200 or invoked.get("ok") is not True:
                raise AssertionError(f"canonical route failed through MCP: {invoked}")

            # Stateful mutation/readback path.  This proves the MCP process keeps one
            # canonical backend/store alive across tool calls instead of recreating it.
            project_ops = _json_text(
                await client.call_tool(
                    "hs_backend_list_operations",
                    {"path_prefix": "/v1/projects", "limit": 100},
                )
            ).get("operations") or []
            save_operation_id = _operation_id(project_ops, "PUT", "/v1/projects/{project_id}/snapshot")
            load_operation_id = _operation_id(project_ops, "GET", "/v1/projects/{project_id}")
            delete_operation_id = _operation_id(project_ops, "DELETE", "/v1/projects/{project_id}")

            project_id = "mcp-contract-smoke"
            save_result = _json_text(
                await client.call_tool(
                    "hs_backend_call",
                    {
                        "operation_id": save_operation_id,
                        "path_params": {"project_id": project_id},
                        "json_body": {
                            "snapshot": {
                                "name": "MCP contract smoke",
                                "mode": "contract_test",
                                "current_stage": "backend_mcp",
                                "physical_authority_granted": False,
                            },
                            "expected_revision": 0,
                            "metadata": {"source": "mcp_stdio_contract"},
                        },
                    },
                )
            )
            if save_result.get("status_code") != 200 or save_result.get("ok") is not True:
                raise AssertionError(f"project save failed through MCP: {save_result}")
            saved_project = (save_result.get("body") or {}).get("project") or {}
            if saved_project.get("revision") != 1:
                raise AssertionError(f"unexpected saved project revision: {save_result}")

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
                raise AssertionError(f"project readback failed through MCP: {load_result}")
            if (loaded_project.get("snapshot") or {}).get("name") != "MCP contract smoke":
                raise AssertionError(f"MCP readback did not preserve canonical state: {load_result}")

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
                raise AssertionError(f"project cleanup failed through MCP: {delete_result}")

            print(
                json.dumps(
                    {
                        "mcp_connection": "pass",
                        "negotiated_protocol_version": str(client.protocol_version),
                        "mcp_tool_discovery": "pass",
                        "canonical_operation_count": status["operation_count"],
                        "operation_discovery": "pass",
                        "operation_description": "pass",
                        "canonical_read_invocation": "pass",
                        "canonical_stateful_write_read_delete": "pass",
                        "physical_authority_granted": False,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )


if __name__ == "__main__":
    asyncio.run(run())
