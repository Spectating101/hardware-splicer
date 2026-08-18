#!/usr/bin/env python3
"""Exercise the canonical backend through a real MCP stdio client/session."""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


_REQUIRED_TOOLS = {
    "hs_backend_status",
    "hs_backend_list_operations",
    "hs_backend_describe_operation",
    "hs_backend_call",
}


def _json_text(result) -> dict:
    for block in result.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return json.loads(text)
    raise AssertionError("MCP result contained no JSON text block")


async def run() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "hardware_splicer.backend_mcp_server"],
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            missing = sorted(_REQUIRED_TOOLS.difference(names))
            if missing:
                raise AssertionError(f"canonical backend MCP missing tools: {missing}")

            status = _json_text(await session.call_tool("hs_backend_status", {}))
            if status.get("surface") != "canonical_product_api":
                raise AssertionError(f"unexpected MCP backend surface: {status}")
            if status.get("operation_count", 0) <= 0:
                raise AssertionError("MCP backend exposed zero canonical operations")
            authority = status.get("authority_contract") or {}
            if authority.get("mcp_grants_physical_authority") is not False:
                raise AssertionError("MCP backend must remain authority-neutral")

            discovered = _json_text(
                await session.call_tool(
                    "hs_backend_list_operations",
                    {"method": "GET", "path_prefix": "/v1/vision/capabilities"},
                )
            )
            operations = discovered.get("operations") or []
            if len(operations) != 1:
                raise AssertionError(f"expected one vision capabilities operation, got {operations}")
            operation_id = operations[0]["operation_id"]

            described = _json_text(
                await session.call_tool(
                    "hs_backend_describe_operation",
                    {"operation_id": operation_id},
                )
            )
            if described.get("path") != "/v1/vision/capabilities":
                raise AssertionError(f"operation description drift: {described}")

            invoked = _json_text(
                await session.call_tool(
                    "hs_backend_call",
                    {"operation_id": operation_id},
                )
            )
            if invoked.get("status_code") != 200 or invoked.get("ok") is not True:
                raise AssertionError(f"canonical route failed through MCP: {invoked}")

            print(
                json.dumps(
                    {
                        "mcp_initialize": "pass",
                        "mcp_tool_discovery": "pass",
                        "canonical_operation_count": status["operation_count"],
                        "operation_discovery": "pass",
                        "operation_description": "pass",
                        "canonical_route_invocation": "pass",
                        "physical_authority_granted": False,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )


if __name__ == "__main__":
    asyncio.run(run())
