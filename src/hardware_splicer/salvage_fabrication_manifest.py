"""Bounded canonical-operation projection for the salvage fabrication agent loop."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_TASK = "salvage_fabrication"
_ROUTES = (
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}/salvage-fabrication"),
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}/intact-reuse-spec"),
    ("GET", "/v1/devices/spec-schema"),
    ("POST", "/v1/devices/parts-reading"),
    ("POST", "/v1/devices/draft"),
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/events"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/candidates/{candidate_id}/run"),
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}/runs/{name}"),
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}/runs/{name}/bundle"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/package"),
    ("GET", "/v1/projects/{project_id}/missions/{mission_id}/package"),
    ("POST", "/v1/projects/{project_id}/missions/{mission_id}/stage"),
    ("POST", "/v1/fabricator/intelligence/vision/inspect"),
    ("POST", "/v1/fabricator/intelligence/vision/donor-drafts"),
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


def salvage_fabrication_manifest(
    app: FastAPI | None = None, *, include_schemas: bool = False,
) -> dict[str, Any]:
    """Expose only canonical operations needed to progress a salvage mission.

    Human acceptance, human evidence submission, donor-draft confirmation,
    physical approval decisions and raw/unchecked actuation are intentionally absent.
    Start compact; fetch exact schemas for the operation being attempted, not
    every specialist operation on every turn.
    """
    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in _ROUTES if route not in by_route]
    if missing:
        raise ValueError(f"canonical salvage-fabrication routes are missing: {missing}")
    rows = [by_route[route] for route in _ROUTES]
    return {
        "schema_version": "hardware_splicer.salvage_fabrication_manifest.v2",
        "task": _TASK,
        "detail": "full" if include_schemas else "compact",
        "start_here": {
            "operation_id": rows[0]["operation_id"],
            "path_params": ["project_id", "mission_id"],
            "instructions": "Read this mission context first; reuse its last_event_seq for proposals. Never invent IDs.",
        },
        "request_contracts": {
            "tool": "hs_backend_describe_operation",
            "argument": "operation_id",
            "instructions": "Describe an unfamiliar operation before calling it. Mission events expose named JSON examples and a discriminated event schema.",
        },
        "related_workflows": [
            {"task": "document_grounded_pre_fabrication",
             "when": "Admit document bytes and record hash-bound/page-addressed claims in the canonical source graph."},
            {"task": "engineering_assurance",
             "when": "Inspect evidence dependencies and claim support without promoting authority."},
        ],
        "recovery": {
            "409": "Reload mission context. If busy, wait for the current operation; if stale, rebuild the proposal from the fresh event sequence. Do not blindly replay mutations.",
            "422": "Read the error message and the operation schema/examples; correct the request instead of repeating it.",
            "403": "Check the human/authority boundary. Do not impersonate a person or request their operator token.",
            "resume": "Reload context after interruption; read a candidate's full spec from the mission and hashed check output from its run artifact.",
        },
        "workflow": [
            "reload the canonical mission-scoped salvage context at the start of every turn",
            "for intact input-device reuse, discover intact-reuse-spec, propose the actual donor design, run intact_reuse and download its software review bundle without inventing a catalog board or claiming READY",
            "inspect retained images and prefill typed donor drafts while preserving model-inference provenance",
            "leave a visual draft pending human confirmation; continue independent software work without treating the draft as a donor contract",
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
        "operations": (
            [describe_operation(row["operation_id"], app) for row in rows]
            if include_schemas else
            [{key: row[key] for key in ("operation_id", "method", "path", "summary", "mutation")} for row in rows]
        ),
        "excluded_human_or_authority_routes": [
            "POST /v1/projects/{project_id}/missions/{mission_id}/accept",
            "POST /v1/projects/{project_id}/missions/{mission_id}/needs/{need_seq}/evidence",
            "POST /v1/projects/{project_id}/missions/{mission_id}/needs/{need_seq}/answer",
            "POST /v1/fabricator/intelligence/vision/donor-drafts/{draft_artifact_id}/confirm",
            "POST /v1/fabrication/approval-requests/{request_id}/approve",
            "POST /v1/fabrication/approval-requests/{request_id}/reject",
            "POST /v1/fabrication/approval-requests/{request_id}/execute",
        ],
        "authority_contract": {
            "projection_grants_physical_authority": False,
            "context_persists_independent_truth": False,
            "visual_draft_is_donor_contract_truth": False,
            "visual_draft_geometry_is_measured": False,
            "marking_text_establishes_part_identity": False,
            "agent_can_confirm_visual_donor_draft": False,
            "agent_can_accept_mission": False,
            "agent_can_supply_human_measurement": False,
            "agent_can_approve_physical_actuation": False,
            "agent_can_bypass_backend_gates": False,
            "lab_reservation_equals_actuation_authority": False,
        },
    }
