"""Canonical FastAPI-to-MCP gateway primitives.

This module deliberately contains no MCP SDK dependency.  It treats the canonical
``product_api`` OpenAPI document as the discovery contract, then dispatches calls
back through the same ASGI application.  The MCP transport is only an adapter: it
must not duplicate project truth, verification logic, evidence state, or authority.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections import Counter
from typing import Any, Iterable, Mapping

import httpx
from fastapi import FastAPI

from .product_api import create_product_app

_HTTP_METHODS = ("get", "post", "put", "patch", "delete")
_PATH_PARAM_RE = re.compile(r"\{([^{}]+)\}")
_SUPPORTED_PARAMETER_LOCATIONS = {"path", "query", "header", "cookie"}


def _app(app: FastAPI | None = None) -> FastAPI:
    return app or create_product_app()


def _openapi_operations(app: FastAPI | None = None) -> Iterable[tuple[str, str, dict[str, Any]]]:
    document = _app(app).openapi()
    for path, path_item in sorted(document.get("paths", {}).items()):
        if not isinstance(path_item, Mapping):
            continue
        for method in _HTTP_METHODS:
            operation = path_item.get(method)
            if isinstance(operation, Mapping):
                yield method.upper(), path, dict(operation)


def canonical_openapi_document(app: FastAPI | None = None) -> dict[str, Any]:
    """Return the exact generated OpenAPI contract for the canonical product app."""

    return _app(app).openapi()


def operation_catalog(app: FastAPI | None = None) -> list[dict[str, Any]]:
    """Return a compact, deterministic catalog of every canonical HTTP operation."""

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for method, path, operation in _openapi_operations(app):
        operation_id = str(operation.get("operationId") or "").strip()
        if not operation_id:
            raise ValueError(f"canonical OpenAPI operation lacks operationId: {method} {path}")
        if operation_id in seen_ids:
            raise ValueError(f"duplicate canonical OpenAPI operationId: {operation_id}")
        seen_ids.add(operation_id)
        parameters = [
            parameter
            for parameter in operation.get("parameters", [])
            if isinstance(parameter, Mapping)
        ]
        rows.append(
            {
                "operation_id": operation_id,
                "method": method,
                "path": path,
                "summary": operation.get("summary") or "",
                "tags": list(operation.get("tags") or []),
                "mutation": method != "GET",
                "has_request_body": "requestBody" in operation,
                "parameter_names": [
                    str(parameter.get("name"))
                    for parameter in parameters
                    if parameter.get("name")
                ],
                "parameter_locations": sorted(
                    {
                        str(parameter.get("in"))
                        for parameter in parameters
                        if parameter.get("in")
                    }
                ),
            }
        )
    rows.sort(key=lambda row: (row["path"], row["method"], row["operation_id"]))
    return rows


def _operation_lookup(app: FastAPI | None = None) -> dict[str, tuple[str, str, dict[str, Any]]]:
    lookup: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for method, path, operation in _openapi_operations(app):
        operation_id = str(operation.get("operationId") or "").strip()
        if not operation_id:
            raise ValueError(f"canonical OpenAPI operation lacks operationId: {method} {path}")
        if operation_id in lookup:
            raise ValueError(f"duplicate canonical OpenAPI operationId: {operation_id}")
        lookup[operation_id] = (method, path, operation)
    return lookup


def _schema_ref_names(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.rsplit("/", 1)[-1])
        for child in value.values():
            refs.update(_schema_ref_names(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_schema_ref_names(child))
    return refs


def describe_operation(operation_id: str, app: FastAPI | None = None) -> dict[str, Any]:
    """Describe one operation and include the transitive component schemas it references."""

    resolved_app = _app(app)
    lookup = _operation_lookup(resolved_app)
    try:
        method, path, operation = lookup[operation_id]
    except KeyError as exc:
        raise ValueError(f"unknown canonical operation_id: {operation_id}") from exc

    document = resolved_app.openapi()
    all_schemas = document.get("components", {}).get("schemas", {})
    wanted = _schema_ref_names(operation)
    selected: dict[str, Any] = {}
    pending = list(sorted(wanted))
    while pending:
        name = pending.pop(0)
        if name in selected:
            continue
        schema = all_schemas.get(name)
        if schema is None:
            continue
        selected[name] = schema
        for dependency in sorted(_schema_ref_names(schema)):
            if dependency not in selected:
                pending.append(dependency)

    return {
        "operation_id": operation_id,
        "method": method,
        "path": path,
        "operation": operation,
        "referenced_schemas": selected,
    }


def backend_contract(app: FastAPI | None = None) -> dict[str, Any]:
    """Summarize the canonical surface used by the MCP bridge."""

    rows = operation_catalog(app)
    method_counts = Counter(row["method"] for row in rows)
    tag_counts: Counter[str] = Counter()
    parameter_locations: set[str] = set()
    for row in rows:
        tag_counts.update(row["tags"])
        parameter_locations.update(row["parameter_locations"])
    unsupported_parameter_locations = sorted(
        parameter_locations.difference(_SUPPORTED_PARAMETER_LOCATIONS)
    )
    return {
        "surface": "canonical_product_api",
        "discovery_source": "FastAPI OpenAPI generated from hardware_splicer.product_api",
        "operation_count": len(rows),
        "read_operation_count": sum(1 for row in rows if not row["mutation"]),
        "mutation_operation_count": sum(1 for row in rows if row["mutation"]),
        "method_counts": dict(sorted(method_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
        "parameter_locations": sorted(parameter_locations),
        "unsupported_parameter_locations": unsupported_parameter_locations,
        "request_transport": {
            "path": True,
            "query": True,
            "headers": True,
            "cookies": True,
            "json": True,
            "form": True,
            "multipart_base64_files": True,
            "raw_body_base64": True,
        },
        "authority_contract": {
            "mcp_grants_physical_authority": False,
            "adapter_bypasses_backend_gates": False,
            "statement": (
                "MCP dispatch re-enters the canonical ASGI handlers. Existing revision, evidence, "
                "deterministic-verification and human-authorization rules remain authoritative."
            ),
        },
    }


def filtered_operations(
    *,
    method: str | None = None,
    tag: str | None = None,
    path_prefix: str | None = None,
    text: str | None = None,
    app: FastAPI | None = None,
) -> list[dict[str, Any]]:
    """Filter the compact operation catalog for agent discovery."""

    rows = operation_catalog(app)
    method_norm = method.upper() if method else None
    text_norm = text.casefold() if text else None
    result: list[dict[str, Any]] = []
    for row in rows:
        if method_norm and row["method"] != method_norm:
            continue
        if tag and tag not in row["tags"]:
            continue
        if path_prefix and not row["path"].startswith(path_prefix):
            continue
        if text_norm:
            haystack = " ".join(
                [row["operation_id"], row["path"], row["summary"], *row["tags"]]
            ).casefold()
            if text_norm not in haystack:
                continue
        result.append(row)
    return result


def _render_path(template: str, path_params: Mapping[str, Any] | None) -> str:
    params = dict(path_params or {})
    required = _PATH_PARAM_RE.findall(template)
    missing = [name for name in required if name not in params]
    if missing:
        raise ValueError(f"missing path parameters for {template}: {', '.join(missing)}")
    extra = sorted(set(params).difference(required))
    if extra:
        raise ValueError(f"unexpected path parameters for {template}: {', '.join(extra)}")
    rendered = template
    for name in required:
        value = str(params[name])
        if "/" in value:
            raise ValueError(f"path parameter {name} must not contain '/'")
        rendered = rendered.replace("{" + name + "}", value)
    return rendered


def _decode_base64(value: str, *, field_name: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{field_name} is invalid base64") from exc


def _prepare_files(files: list[Mapping[str, Any]] | None) -> list[tuple[str, tuple[str, bytes, str]]]:
    prepared: list[tuple[str, tuple[str, bytes, str]]] = []
    for index, item in enumerate(files or []):
        field = item.get("field")
        filename = item.get("filename")
        content_base64 = item.get("content_base64")
        content_type = item.get("content_type") or "application/octet-stream"
        if not isinstance(field, str) or not field:
            raise ValueError(f"files[{index}].field must be a non-empty string")
        if not isinstance(filename, str) or not filename:
            raise ValueError(f"files[{index}].filename must be a non-empty string")
        if not isinstance(content_base64, str):
            raise ValueError(f"files[{index}].content_base64 must be a base64 string")
        content = _decode_base64(content_base64, field_name=f"files[{index}].content_base64")
        prepared.append((field, (filename, content, str(content_type))))
    return prepared


def _decode_response(response: httpx.Response, response_mode: str) -> dict[str, Any]:
    raw = response.content
    content_type = response.headers.get("content-type", "")
    result: dict[str, Any] = {
        "ok": response.is_success,
        "status_code": response.status_code,
        "content_type": content_type,
        "byte_length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "headers": {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "content-length", "content-disposition", "etag"}
        },
    }
    if response_mode == "metadata":
        return result

    is_json = "application/json" in content_type or "+json" in content_type
    is_text = content_type.startswith("text/")
    if is_json:
        try:
            result["body"] = response.json()
        except json.JSONDecodeError:
            result["body_text"] = response.text
    elif is_text:
        result["body_text"] = response.text
    elif response_mode == "base64":
        result["body_base64"] = base64.b64encode(raw).decode("ascii")
    else:
        result["binary_body_omitted"] = True
        result["hint"] = "repeat with response_mode='base64' only when the binary bytes are needed"
    return result


async def dispatch_operation(
    operation_id: str,
    *,
    path_params: Mapping[str, Any] | None = None,
    query: Mapping[str, Any] | None = None,
    headers: Mapping[str, Any] | None = None,
    cookies: Mapping[str, Any] | None = None,
    json_body: Any = None,
    form: Mapping[str, Any] | None = None,
    files: list[Mapping[str, Any]] | None = None,
    body_base64: str | None = None,
    body_content_type: str | None = None,
    response_mode: str = "auto",
    app: FastAPI | None = None,
) -> dict[str, Any]:
    """Invoke one canonical operation through the in-process ASGI application.

    ``operation_id`` is resolved only from the canonical OpenAPI document.  Callers
    cannot use this gateway as an arbitrary HTTP proxy.
    """

    if response_mode not in {"auto", "metadata", "base64"}:
        raise ValueError("response_mode must be one of: auto, metadata, base64")
    body_modes = sum(
        [
            json_body is not None,
            form is not None or bool(files),
            body_base64 is not None,
        ]
    )
    if body_modes > 1:
        raise ValueError("use only one request body mode: json_body, form/files, or body_base64")

    resolved_app = _app(app)
    lookup = _operation_lookup(resolved_app)
    try:
        method, path_template, _operation = lookup[operation_id]
    except KeyError as exc:
        raise ValueError(f"unknown canonical operation_id: {operation_id}") from exc

    path = _render_path(path_template, path_params)
    prepared_files = _prepare_files(files)
    request_headers = {str(key): str(value) for key, value in dict(headers or {}).items()}
    request_cookies = {str(key): str(value) for key, value in dict(cookies or {}).items()}
    raw_body: bytes | None = None
    if body_base64 is not None:
        raw_body = _decode_base64(body_base64, field_name="body_base64")
        if body_content_type and not any(key.lower() == "content-type" for key in request_headers):
            request_headers["content-type"] = body_content_type

    transport = httpx.ASGITransport(app=resolved_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://hardware-splicer.local") as client:
        response = await client.request(
            method,
            path,
            params=dict(query or {}),
            headers=request_headers or None,
            cookies=request_cookies or None,
            json=json_body if json_body is not None else None,
            data=dict(form or {}) if form is not None else None,
            files=prepared_files or None,
            content=raw_body,
        )
    payload = _decode_response(response, response_mode)
    payload.update({"operation_id": operation_id, "method": method, "path": path})
    return payload
