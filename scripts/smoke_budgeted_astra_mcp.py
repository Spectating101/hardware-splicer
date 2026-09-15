#!/usr/bin/env python3
"""Exercise the Astra MCP governor against the real canonical HS MCP server.

This smoke performs no Codex or model inference. It proves the governor relays valid MCP
traffic to ``hs-backend-mcp`` and hard-disconnects at both configured call ceilings.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Running a script from ``scripts/`` would otherwise import the sibling
# ``scripts/hardware_splicer.py`` instead of the package under ``src``.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT / "src"),
    *[entry for entry in sys.path if Path(entry or os.curdir).resolve() != _SCRIPT_DIR],
]

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


async def _expect_disconnect(awaitable, *, label: str) -> str:
    try:
        result = await awaitable
    except BaseException as exc:  # MCP SDK may wrap transport closure in an ExceptionGroup.
        return f"{label}:disconnect:{type(exc).__name__}"
    # A JSON-RPC error may be represented as a result object by future SDK versions. Either
    # way, the governor process is required to terminate immediately after the denial; a
    # successful ordinary tool result is not acceptable here.
    if getattr(result, "isError", False) or getattr(result, "is_error", False):
        return f"{label}:error-result"
    raise AssertionError(f"{label}: over-budget MCP call unexpectedly succeeded: {result!r}")


async def _total_call_budget_smoke(project_root: Path) -> dict[str, object]:
    params = _server_params(project_root)
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            expected = {
                "hs_backend_status",
                "hs_backend_task_manifest",
                "hs_backend_list_operations",
                "hs_backend_describe_operation",
                "hs_backend_call",
            }
            if names != expected:
                raise AssertionError(f"unexpected governed MCP tools: {sorted(names)!r}")
            for _ in range(ASTRA_MAX_MCP_TOOL_CALLS):
                result = await session.call_tool("hs_backend_status", {})
                if getattr(result, "isError", False) or getattr(result, "is_error", False):
                    raise AssertionError("allowed status call returned an MCP error")
            refusal = await _expect_disconnect(
                session.call_tool("hs_backend_status", {}),
                label="total-tool-budget",
            )
            return {
                "allowed_calls": ASTRA_MAX_MCP_TOOL_CALLS,
                "next_call_refused": True,
                "refusal_mode": refusal,
            }


async def _backend_call_budget_smoke(project_root: Path) -> dict[str, object]:
    params = _server_params(project_root)
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            catalog = await session.call_tool(
                "hs_backend_list_operations",
                {"path_prefix": "/v1/vision", "limit": 100},
            )
            if getattr(catalog, "isError", False) or getattr(catalog, "is_error", False):
                raise AssertionError("operation discovery failed through governed MCP")

            # Resolve from canonical OpenAPI rather than duplicating FastAPI's generated ID.
            operation_id = _operation_id("GET", "/v1/vision/capabilities")
            described = await session.call_tool(
                "hs_backend_describe_operation",
                {"operation_id": operation_id},
            )
            if getattr(described, "isError", False) or getattr(described, "is_error", False):
                raise AssertionError(
                    "canonical /v1/vision/capabilities operation id changed; update smoke from OpenAPI"
                )

            for _ in range(ASTRA_MAX_BACKEND_CALLS):
                result = await session.call_tool(
                    "hs_backend_call",
                    {"operation_id": operation_id},
                )
                if getattr(result, "isError", False) or getattr(result, "is_error", False):
                    raise AssertionError("allowed canonical backend call returned an MCP error")
            refusal = await _expect_disconnect(
                session.call_tool("hs_backend_call", {"operation_id": operation_id}),
                label="backend-call-budget",
            )
            return {
                "allowed_backend_calls": ASTRA_MAX_BACKEND_CALLS,
                "next_backend_call_refused": True,
                "refusal_mode": refusal,
            }


async def main_async() -> int:
    with tempfile.TemporaryDirectory(prefix="hs-astra-governor-smoke-") as temp:
        root = Path(temp)
        total = await _total_call_budget_smoke(root / "total-projects")
        backend = await _backend_call_budget_smoke(root / "backend-projects")
        print(
            {
                "schema_version": "hardware_splicer.astra_resource_guard_smoke.v1",
                "canonical_backend": "hs-backend-mcp",
                "model_inference_performed": False,
                "provider_api_call_performed": False,
                "total_tool_budget": total,
                "backend_call_budget": backend,
                "api_fallback": False,
                "physical_authority_granted": False,
            }
        )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
