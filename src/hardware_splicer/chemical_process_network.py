"""Bounded standalone chemical flowsheet topology and declared stream conservation.

This is a multi-operation, species-resolved accounting validator, not a
flowsheet simulator that predicts outlet streams or plant behavior.
"""
from __future__ import annotations

from collections import defaultdict, deque
import math
from typing import Any, Mapping

from .chemical_engineering import NON_AUTHORITY, SCHEMA_VERSION, mass_balance_report

_KINDS = frozenset({"mixer", "splitter", "transfer"})


def validate_process_network(
    *, units: list[Mapping[str, Any]], streams: list[Mapping[str, Any]],
) -> dict[str, Any]:
    if not 1 <= len(units) <= 40 or not 2 <= len(streams) <= 150:
        raise ValueError("Process graph size must be 1-40 units and 2-150 streams")
    unit_ids: set[str] = set()
    kinds: dict[str, str] = {}
    for row in units:
        uid = row.get("unit_id")
        kind = row.get("kind")
        if not isinstance(uid, str) or not 1 <= len(uid) <= 128 or uid in unit_ids:
            raise ValueError("Invalid or duplicate unit ID")
        if kind not in _KINDS:
            raise ValueError("Unsupported process unit kind")
        unit_ids.add(uid)
        kinds[uid] = kind

    stream_ids: set[str] = set()
    upstream: dict[str, list[dict[str, Any]]] = defaultdict(list)
    downstream: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edges: dict[str, list[str]] = defaultdict(list)
    incoming_edges = dict.fromkeys(unit_ids, 0)
    external_inlets: list[dict[str, Any]] = []
    external_outlets: list[dict[str, Any]] = []
    for row in streams:
        sid = row.get("stream_id")
        if not isinstance(sid, str) or not 1 <= len(sid) <= 128 or sid in stream_ids:
            raise ValueError("Invalid or duplicate stream ID")
        stream_ids.add(sid)
        source = row.get("source_unit_id")
        target = row.get("target_unit_id")
        if source is None and target is None:
            raise ValueError("Orphan stream has neither source nor target")
        if (source is not None and source not in unit_ids) or (target is not None and target not in unit_ids):
            raise ValueError("Stream references a non-existent process unit")
        if source == target and source is not None:
            raise ValueError("A stream cannot loop back to its own unit")
        components = row.get("components_kg_h")
        if not isinstance(components, Mapping) or not 1 <= len(components) <= 25:
            raise ValueError("A stream needs 1-25 component mass flow entries")
        checked: dict[str, float] = {}
        for name, value in components.items():
            if not isinstance(name, str) or not 1 <= len(name) <= 128:
                raise ValueError("Component identifier missing or invalid")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Non-numeric component mass flow")
            amount = float(value)
            if not math.isfinite(amount) or not 0 <= amount <= 1e8:
                raise ValueError("Nonfinite, negative or excessive component flow")
            checked[name] = amount
        mass = sum(checked.values())
        if not math.isfinite(mass) or mass <= 0 or mass > 1e8:
            raise ValueError("Each declared stream must have a positive bounded total mass flow")
        stream = {
            "stream_id": sid, "source_unit_id": source,
            "target_unit_id": target, "mass_flow_kg_h": mass,
            "components_kg_h": checked,
        }
        if source is None:
            external_inlets.append(stream)
        else:
            downstream[source].append(stream)
        if target is None:
            external_outlets.append(stream)
        else:
            upstream[target].append(stream)
        if source is not None and target is not None:
            edges[source].append(target)
            incoming_edges[target] += 1
    if not external_inlets or not external_outlets:
        raise ValueError("A standalone process must have boundary inlet and outlet streams")

    queue = deque(sorted(u for u, count in incoming_edges.items() if count == 0))
    topological_order: list[str] = []
    while queue:
        uid = queue.popleft()
        topological_order.append(uid)
        for downstream_unit in edges[uid]:
            incoming_edges[downstream_unit] -= 1
            if incoming_edges[downstream_unit] == 0:
                queue.append(downstream_unit)
    if len(topological_order) != len(unit_ids):
        raise ValueError("Recycle/cyclic flowsheet not supported by this bounded graph validator")

    unit_results: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for unit_id in topological_order:
        inputs = upstream[unit_id]
        outputs = downstream[unit_id]
        kind = kinds[unit_id]
        if not inputs or not outputs:
            raise ValueError(f"Unit {unit_id} must have both inlet and outlet streams")
        if kind == "mixer" and (len(inputs) < 2 or len(outputs) != 1):
            raise ValueError(f"Mixer {unit_id} requires >=2 inlets and exactly one outlet")
        if kind == "splitter" and (len(inputs) != 1 or len(outputs) < 2):
            raise ValueError(f"Splitter {unit_id} requires one inlet and >=2 outlets")
        if kind == "transfer" and (len(inputs) != 1 or len(outputs) != 1):
            raise ValueError(f"Transfer {unit_id} requires one inlet and one outlet")
        result = mass_balance_report(
            [
                {"stream_id": row["stream_id"], "direction": "inlet",
                 "mass_flow_kg_h": row["mass_flow_kg_h"],
                 "components_kg_h": row["components_kg_h"]}
                for row in inputs
            ] + [
                {"stream_id": row["stream_id"], "direction": "outlet",
                 "mass_flow_kg_h": row["mass_flow_kg_h"],
                 "components_kg_h": row["components_kg_h"]}
                for row in outputs
            ],
        )
        if result["result"] != "consistent_declared_flows":
            blockers.append({
                "unit_id": unit_id,
                "code": "unit_declared_component_balance_failed",
            })
        unit_results.append({
            "unit_id": unit_id, "kind": kind,
            "incoming_stream_ids": [row["stream_id"] for row in inputs],
            "outgoing_stream_ids": [row["stream_id"] for row in outputs],
            "conservation_result": result["result"],
            "total_mass_residual_kg_h": result["overall"]["residual_kg_h"],
            "components": result["component_checks"],
        })

    global_balance = mass_balance_report([
        {"stream_id": row["stream_id"], "direction": "inlet",
         "mass_flow_kg_h": row["mass_flow_kg_h"],
         "components_kg_h": row["components_kg_h"]}
        for row in external_inlets
    ] + [
        {"stream_id": row["stream_id"], "direction": "outlet",
         "mass_flow_kg_h": row["mass_flow_kg_h"],
         "components_kg_h": row["components_kg_h"]}
        for row in external_outlets
    ])
    if global_balance["result"] != "consistent_declared_flows":
        blockers.append({"code": "external_declared_mass_balance_failed"})
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "hs-declared-chemical-flowsheet-conservation",
        "topological_unit_order": topological_order,
        "unit_results": unit_results,
        "global_balance": global_balance,
        "feed_streams": [row["stream_id"] for row in external_inlets],
        "product_streams": [row["stream_id"] for row in external_outlets],
        "blocking_findings": blockers,
        "result": "declared_network_consistent_but_unverified" if not blockers else "declared_network_blocked",
        "network_graph_is_cyclic": False,
        "process_behavior_simulated": False,
        "reaction_stoichiometry_modeled": False,
        "unknown_or_recycle_units_supported": False,
        "limitations": [
            "Stream quantities are declarations, NOT solved stream states or process predictions.",
            "No reaction/separation thermodynamics, heat duties, pressure drop, vapor/liquid splits or optimization.",
            "Recycle loops and non-conserving process operations are not supported in this initial graph.",
            "Plant operation, laboratory safety and release are not authorized.",
        ],
        **NON_AUTHORITY,
    }
