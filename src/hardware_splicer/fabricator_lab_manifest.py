"""Bounded MCP/OpenAPI projection for fabrication-lab scheduling."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_TASK = "fabricator_lab"
_ROUTES = (
    ("GET", "/v1/fabricator/lab/resources"),
    ("POST", "/v1/fabricator/lab/workflows"),
    ("GET", "/v1/fabricator/lab/workflows/{plan_id}"),
    ("POST", "/v1/fabricator/lab/workflows/{plan_id}/tasks/{task_id}/lease"),
    ("GET", "/v1/fabricator/lab/leases"),
    ("POST", "/v1/fabricator/lab/leases/{lease_id}/release"),
)


def fabricator_lab_manifest(app: FastAPI | None = None) -> dict[str, Any]:
    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in _ROUTES if route not in by_route]
    if missing:
        raise ValueError(f"canonical fabricator-lab routes are missing: {missing}")
    rows = [by_route[route] for route in _ROUTES]
    return {
        "schema_version": "hardware_splicer.fabricator_lab_manifest.v1",
        "task": _TASK,
        "workflow": [
            "discover server-registered fabrication/lab resources by capability",
            "submit a dependency DAG with capability requirements and relative durations",
            "receive a content-addressed resource/time allocation plan",
            "acquire short-lived plan-bound leases before occupying shared resources",
            "use the separate physical-fabrication workflow for any actuation grant/dispatch",
            "release leases after the scheduled task is complete or abandoned",
        ],
        "operation_ids": [row["operation_id"] for row in rows],
        "operations": [describe_operation(row["operation_id"], app) for row in rows],
        "authority_contract": {
            "schedule_grants_physical_authority": False,
            "lease_grants_physical_authority": False,
            "lease_starts_machine": False,
            "agent_can_change_machine_credentials": False,
            "resource_selection_is_capability_driven": True,
            "physical_actuation_uses_separate_plan_grant_dispatch": True,
        },
    }
