"""Bounded MCP/OpenAPI projection for inspection, visual intake, resources, procurement and tradeoffs."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_TASK = "fabricator_intelligence"
_ROUTES = (
    ("POST", "/v1/fabricator/intelligence/vision/inspect"),
    ("POST", "/v1/fabricator/intelligence/vision/donor-drafts"),
    ("GET", "/v1/fabricator/intelligence/procurement/quotes"),
    ("POST", "/v1/fabricator/intelligence/procurement/estimate"),
    ("POST", "/v1/fabricator/intelligence/resources/project"),
    ("POST", "/v1/fabricator/intelligence/architecture/tradeoffs"),
)


def fabricator_intelligence_manifest(app: FastAPI | None = None) -> dict[str, Any]:
    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in _ROUTES if route not in by_route]
    if missing:
        raise ValueError(f"canonical fabricator-intelligence routes are missing: {missing}")
    rows = [by_route[route] for route in _ROUTES]
    return {
        "schema_version": "hardware_splicer.fabricator_intelligence_manifest.v1",
        "task": _TASK,
        "workflow": [
            "inspect an already-retained image observation and persist model-derived claims as hypotheses",
            "project retained visual inspections into a typed donor-capture prefill whose facts remain model inference",
            "leave donor-draft confirmation/correction to the separate human-token route",
            "read server/provider-ingested supplier quote snapshots",
            "estimate a BOM in one currency without purchasing anything",
            "project canonical donor truth and configured lab capabilities into one read-only salvage resource graph",
            "compare clean-sheet, reclaim-heavy and hybrid options using referenced resource burden and procurement evidence",
            "send physical measurements and human decisions through the separate physical-evidence workflow",
        ],
        "operation_ids": [row["operation_id"] for row in rows],
        "operations": [describe_operation(row["operation_id"], app) for row in rows],
        "excluded_human_routes": [
            "POST /v1/fabricator/intelligence/vision/donor-drafts/{draft_artifact_id}/confirm",
        ],
        "authority_contract": {
            "vision_model_can_pass_physical_validation": False,
            "vision_inference_auto_promotes_evidence": False,
            "visual_draft_is_donor_contract_truth": False,
            "visual_draft_geometry_is_measured": False,
            "marking_text_establishes_part_identity": False,
            "agent_can_confirm_visual_donor_draft": False,
            "resource_graph_persists_independent_truth": False,
            "resource_availability_grants_physical_authority": False,
            "agent_can_ingest_supplier_quotes": False,
            "agent_can_purchase": False,
            "agent_can_select_payment_or_shipping": False,
            "tradeoff_has_automatic_winner": False,
            "projection_grants_physical_authority": False,
        },
    }
