from __future__ import annotations

import asyncio

import pytest

from hardware_splicer.mcp_backend_gateway import (
    backend_contract,
    describe_operation,
    dispatch_operation,
    operation_catalog,
)
from hardware_splicer.product_api import create_product_app


_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _openapi_pairs(app):
    pairs = set()
    for path, path_item in app.openapi()["paths"].items():
        for method in _HTTP_METHODS:
            if method in path_item:
                pairs.add((method.upper(), path))
    return pairs


def test_mcp_catalog_exactly_tracks_canonical_product_openapi():
    app = create_product_app()
    expected = _openapi_pairs(app)
    rows = operation_catalog(app)
    actual = {(row["method"], row["path"]) for row in rows}

    assert actual == expected
    assert len({row["operation_id"] for row in rows}) == len(rows)
    assert len(rows) == len(expected)


def test_mcp_catalog_contains_current_capability_reuse_surface():
    app = create_product_app()
    paths = {row["path"] for row in operation_catalog(app)}

    assert {
        "/v1/capabilities/freeze",
        "/v1/capabilities/derive",
        "/v1/capabilities/derive/adjudicate",
        "/v1/capabilities/derivative-metrics",
        "/v1/capabilities/derivative-economics",
    }.issubset(paths)


def test_describe_operation_returns_referenced_request_schemas():
    app = create_product_app()
    rows = operation_catalog(app)
    candidate = next(row for row in rows if row["has_request_body"])

    described = describe_operation(candidate["operation_id"], app)

    assert described["operation_id"] == candidate["operation_id"]
    assert described["method"] == candidate["method"]
    assert described["path"] == candidate["path"]
    assert "operation" in described
    assert isinstance(described["referenced_schemas"], dict)


def test_backend_contract_is_authority_neutral_and_transport_complete():
    app = create_product_app()
    contract = backend_contract(app)

    assert contract["operation_count"] == len(operation_catalog(app))
    assert contract["unsupported_parameter_locations"] == []
    assert all(contract["request_transport"].values())
    assert contract["authority_contract"]["mcp_grants_physical_authority"] is False
    assert contract["authority_contract"]["adapter_bypasses_backend_gates"] is False


def test_gateway_can_invoke_safe_canonical_get_operation_in_process():
    app = create_product_app()
    row = next(
        row
        for row in operation_catalog(app)
        if row["method"] == "GET" and row["path"] == "/v1/vision/capabilities"
    )

    result = asyncio.run(dispatch_operation(row["operation_id"], app=app))

    assert result["status_code"] == 200
    assert result["ok"] is True
    assert result["operation_id"] == row["operation_id"]
    assert "body" in result


def test_gateway_rejects_unknown_operation_instead_of_becoming_http_proxy():
    app = create_product_app()

    with pytest.raises(ValueError, match="unknown canonical operation_id"):
        asyncio.run(dispatch_operation("definitely_not_a_real_operation", app=app))


def test_gateway_rejects_invalid_raw_base64_before_backend_dispatch():
    app = create_product_app()
    row = next(row for row in operation_catalog(app) if row["method"] == "GET")

    with pytest.raises(ValueError, match="body_base64 is invalid base64"):
        asyncio.run(
            dispatch_operation(
                row["operation_id"],
                body_base64="%%%not-base64%%%",
                app=app,
            )
        )
