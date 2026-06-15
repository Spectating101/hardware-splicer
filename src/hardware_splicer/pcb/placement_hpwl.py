"""Reorder build-graph nodes to shorten approximate HPWL before grid placement."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Mapping


def reorder_nodes_for_placement(graph: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Greedy connectivity order — places heavily wired neighbors closer on the row."""
    nodes = list(graph.get("nodes") or [])
    wires = list(graph.get("wires") or [])
    if len(nodes) <= 2:
        return nodes

    by_id = {str(n.get("id")): dict(n) for n in nodes if n.get("id")}
    adj: Dict[str, set[str]] = defaultdict(set)
    for wire in wires:
        a = str((wire.get("from") or {}).get("nodeId") or "")
        b = str((wire.get("to") or {}).get("nodeId") or "")
        if a in by_id and b in by_id:
            adj[a].add(b)
            adj[b].add(a)

    if not adj:
        return nodes

    start = max(by_id.keys(), key=lambda nid: len(adj.get(nid, set())))
    ordered_ids: List[str] = []
    seen: set[str] = set()
    queue = [start]
    while queue:
        nid = queue.pop(0)
        if nid in seen:
            continue
        seen.add(nid)
        ordered_ids.append(nid)
        for nb in sorted(adj.get(nid, set()), key=lambda x: (-len(adj.get(x, set())), x)):
            if nb not in seen:
                queue.append(nb)
    for nid in by_id:
        if nid not in seen:
            ordered_ids.append(nid)
    return [by_id[nid] for nid in ordered_ids]
