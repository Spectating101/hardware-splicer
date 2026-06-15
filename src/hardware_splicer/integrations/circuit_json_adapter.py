"""Adapter: CircuitNetlist / build graph → tscircuit circuit-json subset."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Mapping

from ..netlist.ir import CircuitNetlist
from ..netlist.lower import build_graph_to_netlist


def _id() -> str:
    return f"hs_{uuid.uuid4().hex[:12]}"


def netlist_to_circuit_json(
    netlist: CircuitNetlist,
    *,
    source_build_id: str = "hardware_splicer",
) -> List[Dict[str, Any]]:
    """Return circuit-json array (subset) for viewers / external autorouters."""
    docs: List[Dict[str, Any]] = [
        {
            "type": "source_project_metadata",
            "source_project_metadata_id": _id(),
            "software_used_string": "hardware-splicer",
            "file_created_at": "",
        },
        {
            "type": "source_group",
            "source_group_id": _id(),
            "name": source_build_id,
        },
    ]

    ref_to_source: Dict[str, str] = {}
    for comp in netlist.components:
        sid = _id()
        ref_to_source[comp.ref] = sid
        docs.append(
            {
                "type": "source_component",
                "source_component_id": sid,
                "name": comp.ref,
                "supplier_part_numbers": {},
                "pin_information": [],
            }
        )
        docs.append(
            {
                "type": "schematic_component",
                "schematic_component_id": _id(),
                "source_component_id": sid,
                "center": {"x": 0, "y": 0},
                "size": {"width": 4, "height": 2},
                "rotation": 0,
                "port_arrangement": None,
                "pin_styles": {},
            }
        )

    for net in netlist.nets:
        if len(net.pins) < 2:
            continue
        for a, b in zip(net.pins, net.pins[1:]):
            docs.append(
                {
                    "type": "schematic_trace",
                    "schematic_trace_id": _id(),
                    "source_net_id": net.name,
                    "connected_source_port_ids": [
                        f"{a.component_ref}.{a.pin}",
                        f"{b.component_ref}.{b.pin}",
                    ],
                }
            )

    return docs


def build_graph_to_circuit_json(
    graph: Mapping[str, Any],
    *,
    source_build_id: str = "hardware_splicer",
) -> List[Dict[str, Any]]:
    netlist = build_graph_to_netlist(graph, source="build_graph")
    return netlist_to_circuit_json(netlist, source_build_id=source_build_id)
