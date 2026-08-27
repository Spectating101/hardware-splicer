"""MCP facade for the complete canonical Hardware-Splicer product backend.

Unlike :mod:`hardware_splicer.mcp_server`, which is the historical compile-engine
surface, this server discovers operations from ``product_api`` OpenAPI at runtime.
That keeps MCP coverage coupled to the canonical backend instead of duplicating a
large hand-maintained list of wrappers.

This module targets the current MCP Python SDK v2.  The historical ``hs-mcp``
entrypoint remains a separate v1 compatibility surface.

Run locally over stdio from an installed checkout with the canonical MCP optional
dependency::

    hs-backend-mcp

For the deliberately guarded remote-experiment transport, see
``docs/EXTERNAL_MCP_AGENT_PROOF.md``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal

try:
    from mcp.server import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings
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


def _csv_env(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _remote_transport_kwargs() -> dict[str, Any]:
    """Resolve guarded Streamable HTTP settings for an external-agent proof run.

    Remote MCP deliberately requires an explicit experiment acknowledgement and a
    dedicated project root.  The canonical gateway can mutate normal project state,
    so accidentally publishing a developer's default store would invalidate both
    the safety posture and the evidence value of the experiment.
    """

    if os.getenv("HS_MCP_REMOTE_EXPERIMENT", "").strip() != "1":
        raise SystemExit(
            "Refusing remote MCP without HS_MCP_REMOTE_EXPERIMENT=1. "
            "Use stdio for normal local operation."
        )

    project_root = os.getenv("HARDWARE_SPLICER_PROJECT_ROOT", "").strip()
    if not project_root:
        raise SystemExit(
            "Remote MCP requires HARDWARE_SPLICER_PROJECT_ROOT to point at an isolated "
            "experiment store."
        )

    host = os.getenv("HS_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        port = int(os.getenv("HS_MCP_PORT", "8000"))
    except ValueError as exc:
        raise SystemExit("HS_MCP_PORT must be an integer") from exc
    if port < 1 or port > 65535:
        raise SystemExit("HS_MCP_PORT must be between 1 and 65535")

    path = os.getenv("HS_MCP_PATH", "/mcp").strip() or "/mcp"
    if not path.startswith("/"):
        raise SystemExit("HS_MCP_PATH must start with '/'")

    allowed_hosts = _csv_env("HS_MCP_ALLOWED_HOSTS")
    allowed_origins = _csv_env("HS_MCP_ALLOWED_ORIGINS")
    security: TransportSecuritySettings | None = None
    if allowed_hosts or allowed_origins:
        if not allowed_hosts:
            raise SystemExit(
                "HS_MCP_ALLOWED_HOSTS is required whenever an explicit transport-security "
                "allowlist is configured."
            )
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )
    elif host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(
            "Refusing a non-local bind without HS_MCP_ALLOWED_HOSTS. Bind locally behind an "
            "authenticated tunnel/reverse proxy or configure an explicit Host allowlist."
        )

    return {
        "host": host,
        "port": port,
        "streamable_http_path": path,
        "stateless_http": True,
        "json_response": True,
        "transport_security": security,
    }


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
    headers: dict[str, Any] | None = None,
    cookies: dict[str, Any] | None = None,
    json_body: Any | None = None,
    form: dict[str, Any] | None = None,
    files: list[dict[str, Any]] | None = None,
    body_base64: str | None = None,
    body_content_type: str | None = None,
    response_mode: Literal["auto", "metadata", "base64"] = "auto",
) -> str:
    """Invoke one canonical backend operation by OpenAPI ``operation_id``.

    The call is dispatched through the same stateful in-process FastAPI application
    used by the product.  Path/query/header/cookie parameters are supported.  JSON,
    form/multipart, and arbitrary base64 raw request bodies are supported; ``files``
    accepts ``field``, ``filename``, ``content_base64`` and optional ``content_type``.
    This is not an arbitrary HTTP proxy and it cannot bypass backend evidence,
    revision or physical-authority gates.
    """

    if not operation_id:
        raise ValueError("operation_id is required")
    payload = await dispatch_operation(
        operation_id,
        path_params=path_params,
        query=query,
        headers=headers,
        cookies=cookies,
        json_body=json_body,
        form=form,
        files=files,
        body_base64=body_base64,
        body_content_type=body_content_type,
        response_mode=response_mode,
        app=_product_app,
    )
    return _render(payload)


def main() -> None:
    """Run stdio by default, or a guarded Streamable HTTP experiment endpoint."""

    transport = os.getenv("HS_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run()
        return
    if transport in {"http", "streamable-http", "streamable_http"}:
        mcp.run(transport="streamable-http", **_remote_transport_kwargs())
        return
    raise SystemExit(
        "HS_MCP_TRANSPORT must be 'stdio' or 'streamable-http' (alias: 'http')."
    )


if __name__ == "__main__":
    main()
