"""Bounded MCP/OpenAPI projection for the fabricator digital-thread workflow."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .mcp_backend_gateway import describe_operation, operation_catalog

_TASK = "fabricator_digital_thread"
_ROUTES = (
    ("GET", "/v1/fabricator/digital/artifacts"),
    ("GET", "/v1/fabricator/digital/mechanics/geometries"),
    ("GET", "/v1/fabricator/digital/mechanics/profiles"),
    ("POST", "/v1/fabricator/digital/mechanics/print-artifacts"),
    ("GET", "/v1/fabricator/digital/freecad/models"),
    ("POST", "/v1/fabricator/digital/freecad/exports"),
    ("GET", "/v1/fabricator/digital/opcua/{source_id}/measurements"),
    ("POST", "/v1/fabricator/digital/opcua/{source_id}/read"),
    ("GET", "/v1/fabricator/digital/ros2/{source_id}/graph"),
    ("POST", "/v1/fabricator/digital/motion-plans/{analyzer_id}/dry-run"),
    ("POST", "/v1/fabricator/digital/pcb/{project_id}/requests"),
    ("POST", "/v1/fabricator/digital/handoffs"),
    ("GET", "/v1/fabricator/digital/threads/{thread_id}"),
    ("GET", "/v1/fabricator/digital/threads/{thread_id}/artifacts/{artifact_id}"),
)


def fabricator_digital_thread_manifest(app: FastAPI | None = None) -> dict[str, Any]:
    catalog = operation_catalog(app)
    by_route = {(row["method"], row["path"]): row for row in catalog}
    missing = [route for route in _ROUTES if route not in by_route]
    if missing:
        raise ValueError(f"canonical fabricator digital-thread routes are missing: {missing}")
    rows = [by_route[route] for route in _ROUTES]
    return {
        "schema_version": "hardware_splicer.fabricator_digital_thread_manifest.v1",
        "task": _TASK,
        "workflow": [
            "discover retained engineering artifacts and registered OpenSCAD/FreeCAD geometry",
            "prepare deterministic CAD/EDA/fabrication artifacts without exposing raw paths or commands",
            "render OpenSCAD into slicer-bound G-code or export registered FreeCAD solids into retained STEP/STL",
            "observe OPC UA/ROS 2 through read-only adapters",
            "dry-run motion plans before any workcell actuation is considered",
            "prepare vendor-neutral PCB fabrication requests without selecting a vendor or placing an order",
            "build deterministic handoff bundles from retained artifact ids",
            "inspect the hash-linked digital thread and artifact derivations",
            "use the separate physical_fabrication workflow for any human-approved actuation",
        ],
        "operation_ids": [row["operation_id"] for row in rows],
        "operations": [describe_operation(row["operation_id"], app) for row in rows],
        "authority_contract": {
            "projection_grants_physical_authority": False,
            "creates_human_grants": False,
            "starts_machine_motion": False,
            "submits_pcb_orders": False,
            "writes_opcua": False,
            "publishes_ros2_commands": False,
            "executes_agent_supplied_python": False,
            "raw_filesystem_or_network_targets_exposed": False,
            "physical_correctness_after_tool_execution": "UNPROVEN",
        },
    }
