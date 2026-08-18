"""MCP facade for the complete canonical Hardware-Splicer product backend.

Unlike :mod:`hardware_splicer.mcp_server`, which is the historical compile-engine
surface, this server discovers operations from ``product_api`` OpenAPI at runtime.
That keeps MCP coverage coupled to the canonical backend instead of duplicating a
large hand-maintained list of wrappers.

This module targets the current MCP Python SDK v2.  The historical ``hs-mcp``
entrypoint remains a separate v1 compatibility surface.

Run from an installed checkout with the canonical MCP optional dependency::

    hs-backend-mcp

or::

    python -m hardware_splicer.backend_mcp_server
"""

from __future__ import annotations

import json
from typing import Any, Literal

try:
    from mcp.server import MCPServer
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit(
        "Hardware-Splicer canonical backend MCP requires MCP Python SDK v2.\n"
        "  pip install -e '.[backend-mcp]'"
    ) from exc

from .mcp_backend_gateway import (
    backend_contract,
    describe_operation,
    dispatch_operation,
    filtered_operations,
)
from .product_api import create_product_app

mcp = MCPServer(
    "hardware-splicer-canonical-backend",
    instructions=(
        "Use hs_backend_status first. Discover operations with hs_backend_list_operations, "
        "inspect unfamiliar request contracts with hs_backend_describe_operation, then invoke "
        "only canonical operations with hs_backend_call. MCP does not grant physical authority; "
        "all revision, evidence, deterministic-verification and human-authorization gates remain "
        "owned by the Hardware-Splicer backend."
    ),
)

# One canonical application/store for the lifetime of the MCP process.  Multi-step
# agent workflows must observe the same state rather than recreating a backend per call.
_product_app = create_product_app()


def _render(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


@mcp.tool(structured_output=False)
async def hs_backend_status() -> str:
    """Summarize the complete canonical backend exposed through this MCP gateway.

    Start here.  The returned authority contract must remain fail-closed: this
    adapter discovers and invokes backend handlers but owns no project or physical
    truth and grants no fabrication, flashing, power, motion, operation or release
    authority.
    """

    return _render(backend_contract(_product_app))


@mcp.tool(structured_output=False)
async def hs_backend_list_operations(
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] | None = None,
    tag: str | None = None,
    path_prefix: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> str:
    """Discover canonical FastAPI operations from the live OpenAPI contract.

    Filter by HTTP method, OpenAPI tag, path prefix or free text.  Use the returned
    ``operation_id`` with ``hs_backend_describe_operation`` before calling an
    unfamiliar operation.  Results are paginated locally so large backends do not
    flood an agent's context.
    """

    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    rows = filtered_operations(
        method=method,
        tag=tag,
        path_prefix=path_prefix,
        text=text,
        app=_product_app,
    )
    return _render(
        {
            "total": len(rows),
            "offset": offset,
            "limit": limit,
            "operations": rows[offset : offset + limit],
        }
    )


@mcp.tool(structured_output=False)
async def hs_backend_describe_operation(operation_id: str) -> str:
    """Return one exact OpenAPI operation plus all referenced component schemas."""

    if not operation_id:
        raise ValueError("operation_id is required")
    return _render(describe_operation(operation_id, _product_app))


@mcp.tool(structured_output=False)
async def hs_backend_call(
    operation_id: str,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    json_body: Any | None = None,
    form: dict[str, Any] | None = None,
    files: list[dict[str, Any]] | None = None,
    response_mode: Literal["auto", "metadata", "base64"] = "auto",
) -> str:
    """Invoke one canonical backend operation by OpenAPI ``operation_id``.

    The call is dispatched through the same stateful in-process FastAPI application
    used by the product.  ``files`` accepts objects with ``field``, ``filename``,
    ``content_base64`` and optional ``content_type``.  This is not an arbitrary HTTP
    proxy and it cannot bypass backend evidence, revision or physical-authority gates.
    """

    if not operation_id:
        raise ValueError("operation_id is required")
    payload = await dispatch_operation(
        operation_id,
        path_params=path_params,
        query=query,
        json_body=json_body,
        form=form,
        files=files,
        response_mode=response_mode,
        app=_product_app,
    )
    return _render(payload)


def main() -> None:
    """Run the canonical whole-backend MCP server over stdio."""

    mcp.run()


if __name__ == "__main__":
    main()
