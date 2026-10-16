"""Bounded MCP/OpenAPI projection for frozen fabrication validation."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_TASK = "fabricator_validation"
_ROUTES = (
    ("GET", "/v1/fabricator/validation/procedures"),
    ("POST", "/v1/fabricator/validation/procedures/{procedure_id}/evaluate"),
)


def fabricator_validation_manifest(app: FastAPI | None = None) -> dict[str, Any]:
    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in _ROUTES if route not in by_route]
    if missing:
        raise ValueError(f"canonical fabricator-validation routes are missing: {missing}")
    rows = [by_route[route] for route in _ROUTES]
    return {
        "schema_version": "hardware_splicer.fabricator_validation_manifest.v1",
        "task": _TASK,
        "workflow": [
            "list server/human-owned frozen validation procedures",
            "capture/promote physical evidence through the separate physical-evidence workflow",
            "evaluate retained evidence ids against the exact frozen procedure hash",
            "use a failed scope as revision input rather than rewriting thresholds",
        ],
        "operation_ids": [row["operation_id"] for row in rows],
        "operations": [describe_operation(row["operation_id"], app) for row in rows],
        "authority_contract": {
            "agent_can_create_procedure": False,
            "agent_can_change_criteria": False,
            "agent_can_supply_measurement_values_to_evaluator": False,
            "evidence_must_match_candidate_revision": True,
            "evidence_must_match_procedure_hash": True,
            "assessment_grants_physical_authority": False,
            "scope_pass_implies_whole_device_correctness": False,
        },
    }
