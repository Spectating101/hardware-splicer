#!/usr/bin/env python3
"""Prove real MCP SDK traffic traverses the Astra governor into canonical HS.

No Codex or model is used. Budget-exhaustion process termination is tested separately in
``tests/test_codex_budgeted_mcp_proxy_process.py`` so this smoke can end cleanly.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from hardware_splicer.codex_budgeted_mcp_proxy import (
    ASTRA_MAX_BACKEND_CALLS,
    ASTRA_MAX_MCP_TOOL_CALLS,
)
from hardware_splicer.mcp_backend_gateway import operation_catalog


def _operation_id(method: str, path: str) -> str:
    matches = [
        row["operation_id"]
        for row in operation_catalog()
        if row["method"] == method and row["path"] == path
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one canonical {method} {path} operation, got {matches!r}")
    return str(matches[0])


def _environment(project_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "HARDWARE_SPLICER_PROJECT_ROOT": str(project_root),
            "HARDWARE_SPLICER_OFFLINE_LLM": "1",
            "HARDWARE_SPLICER_OFFLINE_VISION": "1",
            "HARDWARE_SPLICER_OFFLINE_SALVAGE": "1",
            "HARDWARE_SPLICER_OFFLINE_COMPOSE": "1",
            "HARDWARE_SPLICER_SKIP_VISION_LIVE": "1",
            "HARDWARE_SPLICER_AUTOROUTE": "0",
            "HARDWARE_SPLICER_JLC_ENRICH": "0",
            "QWEN_DISABLED": "1",
        }
    )
    for name in (
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "ANTHROPIC_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        env.pop(name, None)
    return env


def _server_params(project_root: Path) -> StdioServerParameters:
    backend = shutil.which("hs-backend-mcp")
    if not backend:
        raise RuntimeError("hs-backend-mcp is not installed")
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "hardware_splicer.codex_budgeted_mcp_proxy",
            "--backend-command",
            str(Path(backend).resolve()),
        ],
        env=_environment(project_root),
    )


def _assert_ok(result, label: str) -> None:
    if getattr(result, "isError", False) or getattr(result, "is_error", False):
        raise AssertionError(f"{label} returned MCP error: {result!r}")


async def main_async() -> int:
    with tempfile.TemporaryDirectory(prefix="hs-astra-governor-relay-") as temp:
        project_root = Path(temp) / "projects"
        params = _server_params(project_root)
        capability_id = _operation_id("GET", "/v1/vision/capabilities")
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                expected = {
                    "hs_backend_status",
                    "hs_backend_list_operations",
                    "hs_backend_describe_operation",
                    "hs_backend_call",
                }
                if names != expected:
                    raise AssertionError(f"unexpected governed MCP tools: {sorted(names)!r}")

                status = await session.call_tool("hs_backend_status", {})
                _assert_ok(status, "status")
                listed = await session.call_tool(
                    "hs_backend_list_operations",
                    {"path_prefix": "/v1/vision", "limit": 100},
                )
                _assert_ok(listed, "operation-list")
                described = await session.call_tool(
                    "hs_backend_describe_operation",
                    {"operation_id": capability_id},
                )
                _assert_ok(described, "operation-describe")
                called = await session.call_tool(
                    "hs_backend_call",
                    {"operation_id": capability_id},
                )
                _assert_ok(called, "backend-call")

        print(
            {
                "schema_version": "hardware_splicer.astra_resource_guard_relay.v1",
                "canonical_backend": "hs-backend-mcp",
                "tool_surface_exact": True,
                "status_through_governor": "pass",
                "operation_discovery_through_governor": "pass",
                "operation_description_through_governor": "pass",
                "canonical_backend_call_through_governor": "pass",
                "tool_calls_used": 4,
                "tool_calls_hard_max": ASTRA_MAX_MCP_TOOL_CALLS,
                "backend_calls_used": 1,
                "backend_calls_hard_max": ASTRA_MAX_BACKEND_CALLS,
                "model_inference_performed": False,
                "provider_api_call_performed": False,
                "api_fallback": False,
                "physical_authority_granted": False,
            }
        )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
