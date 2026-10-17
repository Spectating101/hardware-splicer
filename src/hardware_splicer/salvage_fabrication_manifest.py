"""Bounded canonical-operation projection for the salvage fabrication agent loop."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_TASK = "salvage_fabrication"
_ROUTES = (
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}/salvage-fabrication"),
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/events"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/candidates/{candidate_id}/run"),
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}/runs/{name}"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/package"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/stage"),
    ("POST", "/v1/fabricator/intelligence/vision/inspect"),
    ("GET", "/v1/fabricator/intelligence/procurement/quotes"),
    ("POST", "/v1/fabricator/intelligence/procurement/estimate"),
    ("POST", "/v1/fabricator/intelligence/architecture/tradeoffs"),
    ("GET", "/v1/fabricator/lab/resources"),
    ("POST", "/v1/fabricator/lab/workflows"),
    ("GET", "/v1/fabricator/lab/workflows/{plan_id}"),
    ("GET", "/v1/fabrication/operators"),
    ("GET", "/v1/fabrication/artifacts"),
    ("POST", "/v1/fabrication/non-actuating"),
    ("POST", "/v1/fabrication/approval-requests"),
    ("GET", "/v1/fabrication/approval-requests/{request_id}"),
    ("POST", "/v1/fabricator/projects/{project_id}/missions/{mission_id}/revision-proposal"),
)


def salvage_fabrication_manifest(app: FastAPI | None = None) -> dict[str, Any]:
    """Expose only canonical operations needed to progress a salvage mission.

    Human acceptance, human evidence submission, physical approval decisions and
    raw/unchecked actuation are intentionally absent.
    """
    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in _ROUTES if route not in by_route]
    if missing:
        raise ValueError(f"canonical salvage-fabrication routes are missing: {missing}")
    rows = [by_route[route] for route in _ROUTES]
    return {
        "schema_version": "hardware_splicer.salvage_fabrication_manifest.v1",
        "task": _TASK,
        "workflow": [
            "reload the canonical mission-scoped salvage context at the start of every turn",
            "inspect retained hypotheses/resources and propose findings or a bounded evidence need when uncertain",
            "propose and deterministically evaluate multiple architecture candidates",
            "compare clean-sheet, reclaim-heavy and hybrid options against the canonical resource graph",
            "generate or inspect bounded artifacts through canonical specialist operations",
            "schedule required lab capabilities without treating reservation as physical authority",
            "request exact physical approval when an actuation plan is ready, but never approve it as the agent",
            "ingest resulting evidence through canonical human/evidence workflows outside this agent manifest",
            "propose a grounded revision when retained physical evidence invalidates the current design",
        ],
        "operation_ids": [row["operation_id"] for row in rows],
        "operations": [describe_operation(row["operation_id"], app) for row in rows],
        "excluded_human_or_authority_routes": [
            "POST /v1/projects/{project_id}/missions/{mission_id}/accept",
            "POST /v1/projects/{project_id}/missions/{mission_id}/needs/{need_seq}/evidence",
            "POST /v1/fabrication/approval-requests/{request_id}/approve",
            "POST /v1/fabrication/approval-requests/{request_id}/reject",
            "POST /v1/fabrication/approval-requests/{request_id}/execute",
        ],
        "authority_contract": {
            "projection_grants_physical_authority": False,
            "context_persists_independent_truth": False,
            "agent_can_accept_mission": False,
            "agent_can_supply_human_measurement": False,
            "agent_can_approve_physical_actuation": False,
            "agent_can_bypass_backend_gates": False,
            "lab_reservation_equals_actuation_authority": False,
        },
    }
