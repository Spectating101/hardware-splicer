"""Post-process cosmetic PCB preview geometry before KiCad serialization.

This does not perform routing. It only removes a specific impossible artifact class from the
preview router: duplicate vias at a coordinate that has copper on one layer only. Such a via
cannot be a layer transition and KiCad correctly reports it as dangling; duplicates at the
same coordinate additionally create co-located-hole warnings.

The pass is deliberately conservative. A unique via is preserved. A duplicate group is also
preserved (collapsed to one) when copper segments from both F.Cu and B.Cu terminate at that
coordinate. Physical/fabrication authority is unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Mapping, Sequence


_EPS = 1e-6


def _same_point(a: Mapping[str, Any], x: float, y: float) -> bool:
    return abs(float(a.get("x") or 0.0) - x) <= _EPS and abs(float(a.get("y") or 0.0) - y) <= _EPS


def _segment_endpoint_layers(
    segments: Sequence[Mapping[str, Any]],
    *,
    x: float,
    y: float,
    net_id: int,
) -> set[str]:
    layers: set[str] = set()
    for row in segments:
        net = row.get("net") or {}
        if int(net.get("id") or 0) != net_id:
            continue
        start = row.get("start") or {}
        end = row.get("end") or {}
        if _same_point(start, x, y) or _same_point(end, x, y):
            layer = str(row.get("layer") or "")
            if layer:
                layers.add(layer)
    return layers


def clean_preview_geometry(geometry: Mapping[str, Any]) -> Dict[str, Any]:
    """Return geometry with redundant non-transition duplicate vias removed."""

    result: Dict[str, Any] = dict(geometry)
    vias = [dict(row) for row in list(geometry.get("vias") or []) if isinstance(row, Mapping)]
    segments = [dict(row) for row in list(geometry.get("segments") or []) if isinstance(row, Mapping)]

    groups: dict[tuple[float, float, int], list[Dict[str, Any]]] = defaultdict(list)
    order: list[tuple[float, float, int]] = []
    for row in vias:
        net = row.get("net") or {}
        key = (round(float(row.get("x") or 0.0), 6), round(float(row.get("y") or 0.0), 6), int(net.get("id") or 0))
        if key not in groups:
            order.append(key)
        groups[key].append(row)

    cleaned: list[Dict[str, Any]] = []
    removed = 0
    collapsed = 0
    findings: list[Dict[str, Any]] = []
    for x, y, net_id in order:
        rows = groups[(x, y, net_id)]
        if len(rows) == 1:
            cleaned.append(rows[0])
            continue

        layers = _segment_endpoint_layers(segments, x=x, y=y, net_id=net_id)
        if "F.Cu" in layers and "B.Cu" in layers:
            cleaned.append(rows[0])
            collapsed += len(rows) - 1
            removed += len(rows) - 1
            findings.append(
                {
                    "code": "DUPLICATE_TRANSITION_VIA_COLLAPSED",
                    "x": x,
                    "y": y,
                    "net_id": net_id,
                    "original_count": len(rows),
                    "layers": sorted(layers),
                }
            )
        else:
            removed += len(rows)
            findings.append(
                {
                    "code": "REDUNDANT_NON_TRANSITION_VIAS_REMOVED",
                    "x": x,
                    "y": y,
                    "net_id": net_id,
                    "original_count": len(rows),
                    "layers": sorted(layers),
                }
            )

    result["vias"] = cleaned
    result["geometry_hygiene"] = {
        "input_via_count": len(vias),
        "output_via_count": len(cleaned),
        "removed_via_count": removed,
        "collapsed_duplicate_count": collapsed,
        "findings": findings,
        "authority_effect": "none",
        "fabrication_authorized": False,
    }
    return result
