"""Design Rule Check for generated PcbGeometry (Python engine port)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

Pt = Dict[str, float]
PcbGeometry = Dict[str, Any]


@dataclass(frozen=True)
class DrcRules:
    min_trace_width: float = 0.127
    min_clearance: float = 0.127
    min_annular: float = 0.13
    min_drill: float = 0.2
    edge_clearance: float = 0.3


JLCPCB_2LAYER = DrcRules()


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _dist(a: Pt, b: Pt) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def _point_seg_dist(p: Pt, a: Pt, b: Pt) -> float:
    dx = b["x"] - a["x"]
    dy = b["y"] - a["y"]
    len2 = dx * dx + dy * dy
    if len2 == 0:
        return _dist(p, a)
    t = _clamp(((p["x"] - a["x"]) * dx + (p["y"] - a["y"]) * dy) / len2, 0, 1)
    return _dist(p, {"x": a["x"] + t * dx, "y": a["y"] + t * dy})


def _orient(a: Pt, b: Pt, c: Pt) -> float:
    return math.copysign(1.0, (b["y"] - a["y"]) * (c["x"] - b["x"]) - (b["x"] - a["x"]) * (c["y"] - b["y"])) or 0


def _segs_intersect(p1: Pt, p2: Pt, p3: Pt, p4: Pt) -> bool:
    o1 = _orient(p1, p2, p3)
    o2 = _orient(p1, p2, p4)
    o3 = _orient(p3, p4, p1)
    o4 = _orient(p3, p4, p2)
    return o1 != o2 and o3 != o4


def _seg_seg_dist(p1: Pt, p2: Pt, p3: Pt, p4: Pt) -> float:
    if _segs_intersect(p1, p2, p3, p4):
        return 0.0
    return min(
        _point_seg_dist(p1, p3, p4),
        _point_seg_dist(p2, p3, p4),
        _point_seg_dist(p3, p1, p2),
        _point_seg_dist(p4, p1, p2),
    )


def _point_in_polygon(p: Pt, poly: List[Pt]) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        a, b = poly[i], poly[j]
        hit = a["y"] > p["y"] != b["y"] > p["y"] and p["x"] < (b["x"] - a["x"]) * (p["y"] - a["y"]) / (b["y"] - a["y"]) + a["x"]
        if hit:
            inside = not inside
        j = i
    return inside


def _polygon_edge_dist(p: Pt, poly: List[Pt]) -> float:
    m = float("inf")
    j = len(poly) - 1
    for i in range(len(poly)):
        m = min(m, _point_seg_dist(p, poly[i], poly[j]))
        j = i
    return m


def _same_net(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    if a.get("id") not in (None, 0) and b.get("id") not in (None, 0):
        return a.get("id") == b.get("id")
    return bool(a.get("name")) and a.get("name") == b.get("name")


def _has_net(n: Mapping[str, Any]) -> bool:
    return n.get("id") not in (None, 0) or bool(n.get("name"))


def _is_copper_layer(layer: str) -> bool:
    return str(layer).endswith(".Cu")


def _pad_radius(pad: Mapping[str, Any]) -> float:
    w = float(pad.get("size_w_mm") or 0)
    h = float(pad.get("size_h_mm") or 0)
    return max(w, h, 0) / 2


def _pad_on_copper(pad: Mapping[str, Any]) -> bool:
    pad_type = pad.get("type") or "thru_hole"
    return pad_type in ("thru_hole", "np_thru_hole") or float(pad.get("drill_mm") or 0) > 0


def run_drc(geometry: PcbGeometry, rules: DrcRules = JLCPCB_2LAYER) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    segs = geometry.get("segments") or []

    pads: List[Dict[str, Any]] = []
    for fp in geometry.get("footprints") or []:
        for pad in fp.get("pads") or []:
            pads.append({"ref": fp.get("ref"), "pad": pad, "at": {"x": pad["wx"], "y": pad["wy"]}})

    for s in segs:
        if not _is_copper_layer(s.get("layer", "")):
            continue
        width = s.get("width_mm")
        if width is not None and width < rules.min_trace_width - 1e-9:
            violations.append(
                {
                    "rule": "trace-width",
                    "severity": "error",
                    "message": f"Trace on {s['layer']} is {width:.3f} mm — below the {rules.min_trace_width} mm fab minimum.",
                    "at": s["start"],
                }
            )

    for i, a in enumerate(segs):
        if not _is_copper_layer(a.get("layer", "")):
            continue
        if not _has_net(a.get("net") or {}):
            continue
        aw = float(a.get("width_mm") or rules.min_trace_width) / 2
        for b in segs[i + 1 :]:
            if b.get("layer") != a.get("layer"):
                continue
            if not _has_net(b.get("net") or {}):
                continue
            if _same_net(a.get("net") or {}, b.get("net") or {}):
                continue
            bw = float(b.get("width_mm") or rules.min_trace_width) / 2
            edge = _seg_seg_dist(a["start"], a["end"], b["start"], b["end"]) - aw - bw
            if edge < rules.min_clearance - 1e-9:
                shorted = edge <= 0
                an = a["net"]
                bn = b["net"]
                violations.append(
                    {
                        "rule": "trace-short" if shorted else "copper-clearance",
                        "severity": "error" if shorted else "warn",
                        "message": (
                            f'Nets "{an.get("name") or an.get("id")}" and "{bn.get("name") or bn.get("id")}" cross on {a["layer"]} — electrical short.'
                            if shorted
                            else f'Nets "{an.get("name") or an.get("id")}" and "{bn.get("name") or bn.get("id")}" are {edge:.3f} mm apart on {a["layer"]} — under {rules.min_clearance} mm clearance.'
                        ),
                        "at": {"x": (a["start"]["x"] + b["start"]["x"]) / 2, "y": (a["start"]["y"] + b["start"]["y"]) / 2},
                    }
                )

    for item in pads:
        pad, at, ref = item["pad"], item["at"], item["ref"]
        if not _pad_on_copper(pad):
            continue
        if not _has_net(pad.get("net") or {}):
            continue
        r = _pad_radius(pad)
        for s in segs:
            if not _is_copper_layer(s.get("layer", "")):
                continue
            if not _has_net(s.get("net") or {}):
                continue
            if _same_net(pad.get("net") or {}, s.get("net") or {}):
                continue
            sw = float(s.get("width_mm") or rules.min_trace_width) / 2
            edge = _point_seg_dist(at, s["start"], s["end"]) - r - sw
            if edge < rules.min_clearance - 1e-9:
                violations.append(
                    {
                        "rule": "trace-short" if edge <= 0 else "copper-clearance",
                        "severity": "error" if edge <= 0 else "warn",
                        "message": f'Pad {ref}.{pad.get("num")} (net "{pad["net"].get("name") or pad["net"].get("id")}") is {"shorted to" if edge <= 0 else f"{edge:.3f} mm from"} trace net "{s["net"].get("name") or s["net"].get("id")}".',
                        "at": at,
                    }
                )

    for item in pads:
        pad, at, ref = item["pad"], item["at"], item["ref"]
        drill = float(pad.get("drill_mm") or 0)
        if drill <= 0:
            continue
        min_pad = min(float(pad.get("size_w_mm") or 0), float(pad.get("size_h_mm") or 0))
        annular = (min_pad - drill) / 2
        if annular < rules.min_annular - 1e-9:
            violations.append(
                {
                    "rule": "annular-ring",
                    "severity": "error",
                    "message": f"Pad {ref}.{pad.get('num')} annular ring is {annular:.3f} mm (pad {min_pad} mm, drill {drill} mm) — below {rules.min_annular} mm.",
                    "at": at,
                }
            )
        if drill < rules.min_drill - 1e-9:
            violations.append(
                {
                    "rule": "drill-size",
                    "severity": "warn",
                    "message": f"Pad {ref}.{pad.get('num')} drill {drill} mm is below the {rules.min_drill} mm fab minimum.",
                    "at": at,
                }
            )

    edges = geometry.get("edgeLines") or []
    if edges:

        def edge_dist_of(p: Pt) -> float:
            return min(_point_seg_dist(p, e["start"], e["end"]) for e in edges)

        for s in segs:
            if not _is_copper_layer(s.get("layer", "")):
                continue
            d = min(edge_dist_of(s["start"]), edge_dist_of(s["end"])) - float(s.get("width_mm") or rules.min_trace_width) / 2
            if d < rules.edge_clearance - 1e-9:
                violations.append(
                    {
                        "rule": "edge-clearance",
                        "severity": "warn",
                        "message": f'Trace net "{s["net"].get("name") or s["net"].get("id")}" is {d:.3f} mm from the board edge — under {rules.edge_clearance} mm.',
                        "at": s["start"],
                    }
                )
        for item in pads:
            pad, at, ref = item["pad"], item["at"], item["ref"]
            d = edge_dist_of(at) - _pad_radius(pad)
            if d < rules.edge_clearance - 1e-9:
                violations.append(
                    {
                        "rule": "edge-clearance",
                        "severity": "warn",
                        "message": f"Pad {ref}.{pad.get('num')} is {d:.3f} mm from the board edge — under {rules.edge_clearance} mm.",
                        "at": at,
                    }
                )

    for zone in geometry.get("zones") or []:
        if not _is_copper_layer(zone.get("layer", "")):
            continue
        z_net = {"id": zone.get("net_id"), "name": zone.get("net_name")}
        for item in pads:
            pad, at, ref = item["pad"], item["at"], item["ref"]
            if not _pad_on_copper(pad):
                continue
            if not _has_net(pad.get("net") or {}):
                continue
            if _same_net(pad.get("net") or {}, z_net):
                continue
            inside = any(_point_in_polygon(at, poly) for poly in zone.get("polygons") or [])
            near_edge = any(
                _polygon_edge_dist(at, poly) < _pad_radius(pad) + rules.min_clearance
                for poly in zone.get("polygons") or []
            )
            if inside or near_edge:
                violations.append(
                    {
                        "rule": "pour-short",
                        "severity": "error",
                        "message": f'{zone.get("net_name")} pour floods over pad {ref}.{pad.get("num")} (net "{pad["net"].get("name") or pad["net"].get("id")}") with no keepout — that net is shorted to {zone.get("net_name")}.',
                        "at": at,
                    }
                )

    by_rule: Dict[str, int] = {}
    errors = warnings = 0
    for x in violations:
        by_rule[x["rule"]] = by_rule.get(x["rule"], 0) + 1
        if x["severity"] == "error":
            errors += 1
        else:
            warnings += 1

    return {
        "pass": errors == 0,
        "violations": violations,
        "summary": {"errors": errors, "warnings": warnings, "byRule": by_rule},
    }
