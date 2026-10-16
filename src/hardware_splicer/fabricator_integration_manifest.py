"""Bounded MCP/OpenAPI projection for the broader fabricator toolchain."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_ROUTES = (
    ("GET", "/v1/fabricator/capabilities"),
    ("POST", "/v1/fabricator/capabilities/match"),
    ("POST", "/v1/fabricator/kicad/{project_id}/verify"),
    ("POST", "/v1/fabricator/kicad/{project_id}/manufacturing"),
    ("POST", "/v1/fabricator/ngspice/{circuit_id}"),
    ("GET", "/v1/fabricator/mtconnect/{source_id}/probe"),
    ("GET", "/v1/fabricator/mtconnect/{source_id}/current"),
    ("POST", "/v1/fabricator/mtconnect/{source_id}/sample"),
    ("POST", "/v1/fabricator/machine-jobs/{analyzer_id}/dry-run"),
    ("GET", "/v1/fabricator/openpnp/{job_id}/simulation-package"),
    ("GET", "/v1/fabricator/benchmarks"),
    ("POST", "/v1/fabricator/benchmarks/{benchmark_id}/assess"),
    ("POST", "/v1/fabricator/projects/{project_id}/missions/{mission_id}/revision-proposal"),
)


def fabricator_integration_manifest(app: FastAPI | None = None) -> dict[str, Any]:
    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in _ROUTES if route not in by_route]
    if missing:
        raise ValueError(f"canonical fabricator integration routes are missing: {missing}")
    rows = [by_route[route] for route in _ROUTES]
    return {
        "schema_version": "hardware_splicer.fabricator_integration_manifest.v1",
        "task": "fabricator_integrations",
        "operation_ids": [row["operation_id"] for row in rows],
        "operations": [describe_operation(row["operation_id"], app) for row in rows],
        "workflow": [
            "match a required engineering/fabrication capability to a server-registered operator",
            "run deterministic EDA or simulation checks and retain tool receipts",
            "observe manufacturing equipment through read-only telemetry",
            "dry-run machine jobs and OpenPnP packages before any live machine authority exists",
            "feed failed retained physical evidence into a reviewable revision proposal",
            "use the separate physical_fabrication manifest for human-gated actuation",
        ],
        "authority_contract": {
            "projection_grants_physical_authority": False,
            "arbitrary_process_execution": False,
            "arbitrary_filesystem_paths": False,
            "arbitrary_network_targets": False,
            "live_cnc_or_laser_motion": False,
            "live_openpnp_motion": False,
            "mtconnect_is_read_only": True,
            "physical_correctness_from_simulation": "UNPROVEN",
        },
    }
