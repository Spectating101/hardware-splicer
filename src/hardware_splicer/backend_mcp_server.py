"""MCP facade for the complete canonical Hardware-Splicer product backend.

Unlike :mod:`hardware_splicer.mcp_server`, which is the historical compile-engine
surface, this server discovers operations from ``product_api`` OpenAPI at runtime.
That keeps MCP coverage coupled to the canonical backend instead of duplicating a
large hand-maintained list of wrappers.

Run from an installed checkout with the optional MCP dependency::

    hs-backend-mcp

or::

    python -m hardware_splicer.backend_mcp_server
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as exc:  # pragma: no cover - optional dependency
    print(
        "Hardware-Splicer canonical backend MCP requires the 'mcp' package.\n"
        "  pip install -e '.[mcp]'\n",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

from .mcp_backend_gateway import (
    backend_contract,
    describe_operation,
    dispatch_operation,
    filtered_operations,
)
from .product_api import create_product_app

app = Server("hardware-splicer-canonical-backend")
_product_app = create_product_app()


def _result(payload: Any) -> list[TextContent]:
    return [
        TextContent(
            type="text",
            text=json.dumps(payload, indent=2, sort_keys=True, default=str),
        )
    ]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hs_backend_status",
            description=(
                "Start here. Summarize the canonical Hardware-Splicer FastAPI surface that this MCP "
                "gateway can reach. The MCP adapter grants no physical authority and never bypasses "
                "backend evidence/revision/human-authorization gates."
            ),
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        Tool(
            name="hs_backend_list_operations",
            description=(
                "Discover canonical backend operations from live FastAPI OpenAPI. Filter by HTTP "
                "method, tag, path prefix, or text; then call hs_backend_describe_operation before "
                "invoking unfamiliar operations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                    "tag": {"type": "string"},
                    "path_prefix": {"type": "string"},
                    "text": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                },
                "additionalProperties": False,
            },
        ),
        Tool(
            name="hs_backend_describe_operation",
            description=(
                "Return the exact OpenAPI definition for one canonical operation_id plus every "
                "referenced component schema needed to construct its request."
            ),
            inputSchema={
                "type": "object",
                "properties": {"operation_id": {"type": "string"}},
                "required": ["operation_id"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name="hs_backend_call",
            description=(
                "Invoke one canonical backend operation by OpenAPI operation_id through the same "
                "stateful in-process FastAPI handlers used by the product. Supports path/query/JSON "
                "and multipart form+base64 file input. This is not an arbitrary HTTP proxy and does "
                "not grant fabrication, flashing, power, motion, operation, release, or other physical authority."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string"},
                    "path_params": {"type": "object", "additionalProperties": True},
                    "query": {"type": "object", "additionalProperties": True},
                    "json_body": {},
                    "form": {"type": "object", "additionalProperties": True},
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "filename": {"type": "string"},
                                "content_base64": {"type": "string"},
                                "content_type": {"type": "string"},
                            },
                            "required": ["field", "filename", "content_base64"],
                            "additionalProperties": False,
                        },
                    },
                    "response_mode": {
                        "type": "string",
                        "enum": ["auto", "metadata", "base64"],
                        "default": "auto",
                        "description": (
                            "auto returns JSON/text and only metadata for binary; base64 returns binary bytes; "
                            "metadata suppresses all response bodies"
                        ),
                    },
                },
                "required": ["operation_id"],
                "additionalProperties": False,
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    args = dict(arguments or {})
    if name == "hs_backend_status":
        return _result(backend_contract(_product_app))

    if name == "hs_backend_list_operations":
        offset = int(args.pop("offset", 0) or 0)
        limit = int(args.pop("limit", 100) or 100)
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        rows = filtered_operations(
            method=args.get("method"),
            tag=args.get("tag"),
            path_prefix=args.get("path_prefix"),
            text=args.get("text"),
            app=_product_app,
        )
        return _result(
            {
                "total": len(rows),
                "offset": offset,
                "limit": limit,
                "operations": rows[offset : offset + limit],
            }
        )

    if name == "hs_backend_describe_operation":
        operation_id = args.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("operation_id is required")
        return _result(describe_operation(operation_id, _product_app))

    if name == "hs_backend_call":
        operation_id = args.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            raise ValueError("operation_id is required")
        payload = await dispatch_operation(
            operation_id,
            path_params=args.get("path_params"),
            query=args.get("query"),
            json_body=args.get("json_body"),
            form=args.get("form"),
            files=args.get("files"),
            response_mode=args.get("response_mode", "auto"),
            app=_product_app,
        )
        return _result(payload)

    raise ValueError(f"unknown Hardware-Splicer backend MCP tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
