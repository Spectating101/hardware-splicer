"""Conservative component-geometry provenance for HS builds.

A usable KiCad text export does NOT certify that board positions, footprints or
component heights are sourced from a manufacturer. Keep this distinct from
electrical DRC and from physical build authorization.
"""
from __future__ import annotations

from collections.abc import Mapping

from .pcb.module_registry import (
    find_module, resolve_module_body_mm, resolve_module_footprint, resolve_module_pads,
)

SCHEMA = "hardware_splicer.component_geometry_provenance.v1"
MAX_NODES = 1000


def assess_build_graph_geometry(graph: Mapping) -> dict:
    if not isinstance(graph, Mapping):
        raise ValueError("build graph must be an object")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise ValueError("bounded build graph nodes required")
    rows = []
    missing = []
    fallback = []
    explicit = []
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            raise ValueError("build node must be an object")
        module_id = node.get("moduleId")
        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError("moduleId missing from build graph node")
        spec = find_module(module_id)
        named = resolve_module_footprint(module_id)
        body = resolve_module_body_mm(module_id)
        pad_data = resolve_module_pads(module_id, spec=spec)
        if spec is None:
            geometry = "unknown_module"
            missing.append(module_id)
        elif body is None or named.startswith("Circuit.AI:"):
            geometry = "synthetic_fallback"
            fallback.append(module_id)
        else:
            geometry = "curated_unverified"
            explicit.append(module_id)
        rows.append({
            "node_id": str(node.get("id") or f"n{index + 1}"),
            "module_id": module_id,
            "geometry_class": geometry,
            "footprint_identifier": named,
            "has_declared_body_dimensions": body is not None,
            "pad_definition_count": len(pad_data or []),
            "vendor_footprint_authenticated": False,
            "physical_component_height_verified": False,
            "pinout_physically_verified": False,
        })
    status = (
        "missing_module_identity" if missing else
        "synthetic_geometry_present" if fallback else
        "curated_geometry_requires_validation"
    )
    actions = []
    if missing:
        actions.append("Identify unsupported module and obtain an authoritative electrical and mechanical data package.")
    if fallback:
        actions.append("Replace synthetic footprint and pad layout with validated manufacturer datasheet or source CAD/footprint.")
    if explicit:
        actions.append("Compare curated footprints, pin 1, pinout, dimensions and heights against actual purchased component variants.")
    actions.append("Verify connector mating, mounting holes, assembly clearances and physical test evidence before fabrication.")
    return {
        "schema": SCHEMA,
        "status": status,
        "node_count": len(rows),
        "curated_unverified_count": len(explicit),
        "synthetic_fallback_count": len(fallback),
        "missing_module_count": len(missing),
        "modules": rows,
        "required_actions": actions,
        "electrical_drc_equivalent_to_manufacturing_validation": False,
        "source_geometry_authenticated": False,
        "mechanical_assembly_verified": False,
        "fabrication_authorized": False,
        "production_release_authorized": False,
    }
