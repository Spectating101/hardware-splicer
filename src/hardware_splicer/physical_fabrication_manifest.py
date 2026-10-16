"""Bounded agent projection for Hardware Splicer's physical-fabrication workflow.

This module does not create a second control surface.  It selects a deliberately
small subset of the canonical FastAPI/OpenAPI operations already enforced by the
backend gateway.  In particular, discovery and non-actuating work are agent-safe;
approval is a request/status workflow; human approval still requires the canonical
operator-token route; execution re-enters the same backend and consumes the same
one-shot physical authority.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_TASK = "physical_fabrication"
_ROUTES = (
    ("GET", "/v1/fabrication/operators"),
    ("GET", "/v1/fabrication/artifacts"),
    ("POST", "/v1/fabrication/non-actuating"),
    ("POST", "/v1/fabrication/approval-requests"),
    ("GET", "/v1/fabrication/approval-requests/{request_id}"),
    ("POST", "/v1/fabrication/approval-requests/{request_id}/execute"),
)
_HUMAN_ONLY_ROUTES = (
    ("POST", "/v1/fabrication/approval-requests/{request_id}/approve"),
    ("POST", "/v1/fabrication/approval-requests/{request_id}/reject"),
)


def physical_fabrication_manifest(app: FastAPI | None = None) -> dict[str, Any]:
    """Return the exact canonical operations an AI needs for bounded fabrication.

    Human-only approval/rejection routes are described separately so a model can
    understand the workflow without being told that it possesses those permissions.
    """

    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in (*_ROUTES, *_HUMAN_ONLY_ROUTES) if route not in by_route]
    if missing:
        raise ValueError(f"canonical physical-fabrication routes are missing: {missing}")

    agent_rows = [by_route[route] for route in _ROUTES]
    human_rows = [by_route[route] for route in _HUMAN_ONLY_ROUTES]
    return {
        "schema_version": "hardware_splicer.physical_fabrication_manifest.v1",
        "task": _TASK,
        "workflow": [
            "discover configured operators/artifacts",
            "perform observation/preparation/risk-reducing operations through canonical non-actuating route",
            "request approval for one exact server-created actuation plan",
            "wait for a human decision made outside agent authority",
            "execute only the approved request; backend consumes one-shot authority before actuation",
            "retain resulting observation/dispatch receipts; physical correctness remains independently assessed",
        ],
        "agent_operation_ids": [row["operation_id"] for row in agent_rows],
        "agent_operations": [describe_operation(row["operation_id"], app) for row in agent_rows],
        "human_only_operation_ids": [row["operation_id"] for row in human_rows],
        "human_only_operations": [describe_operation(row["operation_id"], app) for row in human_rows],
        "authority_contract": {
            "projection_grants_physical_authority": False,
            "agent_can_mint_grants": False,
            "agent_can_approve_requests": False,
            "agent_can_register_operators": False,
            "agent_can_set_endpoints_or_credentials": False,
            "agent_can_submit_raw_machine_commands": False,
            "backend_gates_bypassed": False,
            "automatic_execution": False,
            "physical_correctness_after_execution": "UNPROVEN",
        },
        "fallback": (
            "Use generic backend operation discovery only when this manifest lacks a required read-only or "
            "preparatory capability. Do not infer authority from operation discoverability."
        ),
    }
