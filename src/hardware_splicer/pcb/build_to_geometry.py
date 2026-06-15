"""Converts a BuildGraph (user's wiring of salvaged/breakout modules) into a
PcbGeometry that a PCB viewport can render as a real board — green solder mask,
copper traces, gold pads, drilled vias.  Layout is deterministic and cosmetic,
not fabrication-grade: the point is to let a beginner see their wiring as an
actual board.

Faithfully ported from apps/circuit-ai/circuit-ai-frontend/lib/pcb/build-to-geometry.ts.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Optional

from .module_registry import (
    bounds_from_pads,
    find_module,
    resolve_module_body_mm,
    resolve_module_footprint,
    resolve_module_pads,
)

# ---------------------------------------------------------------------------
# Constants (mirrors TS)
# ---------------------------------------------------------------------------
PITCH = 2.54
PAD_DRILL = 1.0
PAD_SIZE = 1.8
MODULE_MARGIN_X = 6
MODULE_MARGIN_Y = 4
MODULE_GAP = 14
BOARD_MARGIN = 3
COLS = sys.maxsize  # single row; see TS comment

# ---------------------------------------------------------------------------
# Internal types (plain dicts; type aliases for readability)
# ---------------------------------------------------------------------------
# PadLayoutKind = "dual" | "row" | "general"
# Placed = {nodeId, spec, x, y, hw, hh, padMinX, padMaxX, padPos, pinOrder, padLayout}


def _detect_pad_layout(pad_defs: list[dict]) -> str:
    if len(pad_defs) < 2:
        return "general"
    ys = [p["y"] for p in pad_defs]
    xs = [p["x"] for p in pad_defs]
    y_span = max(ys) - min(ys)
    x_span = max(xs) - min(xs)
    if y_span < PITCH * 0.75 and x_span >= PITCH:
        return "row"
    has_left  = any(p["x"] < -PITCH * 0.25 for p in pad_defs)
    has_right = any(p["x"] >  PITCH * 0.25 for p in pad_defs)
    if has_left and has_right and y_span >= PITCH * 0.5:
        return "dual"
    return "general"


def _synthetic_dual_column_pads(
    spec: dict, center_x: float, center_y: float
) -> tuple[dict[str, dict], list[str]]:
    """Returns (pad_pos, pin_order) for a synthetic dual-column layout."""
    pins = spec["pins"]
    half = math.ceil(len(pins) / 2)
    pad_w = 2 * PITCH
    left  = pins[:half]
    right = pins[half:]
    pad_pos: dict[str, dict] = {}
    left_x  = center_x - pad_w / 2
    right_x = center_x + pad_w / 2
    top_y   = center_y - ((half - 1) * PITCH) / 2
    for i, pin in enumerate(left):
        pad_pos[pin["id"]] = {"x": left_x, "y": top_y + i * PITCH}
    for i, pin in enumerate(right):
        pad_pos[pin["id"]] = {"x": right_x, "y": top_y + i * PITCH}
    pin_order = [p["id"] for p in left] + [p["id"] for p in right]
    return pad_pos, pin_order


def _pick_escape_edge(
    pad: dict, pl: dict, layout: str
) -> str:  # "left" | "right" | "bottom"
    if layout in ("row", "dual"):
        return "left" if pad["x"] < pl["x"] else "right"
    d_left   = pad["x"] - (pl["x"] - pl["hw"])
    d_right  = pl["x"] + pl["hw"] - pad["x"]
    d_bottom = pl["y"] + pl["hh"] - pad["y"]
    d_top    = pad["y"] - (pl["y"] - pl["hh"])
    if d_bottom <= d_left and d_bottom <= d_right and d_bottom <= d_top:
        return "bottom"
    return "left" if d_left <= d_right else "right"


def _union_find(
    pairs: list[tuple[str, str]], nodes: list[str]
) -> dict[str, str]:
    parent: dict[str, str] = {n: n for n in nodes}

    def find(x: str) -> str:
        p = parent.get(x, x)
        if p == x:
            return x
        r = find(p)
        parent[x] = r
        return r

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in pairs:
        if a not in parent:
            parent[a] = a
        if b not in parent:
            parent[b] = b
        union(a, b)

    return {n: find(n) for n in parent}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_graph_to_geometry(graph: dict) -> dict:
    """Convert a BuildGraph dict into a PcbGeometry dict.

    graph = {
        "nodes": [{"id": str, "moduleId": str}, ...],
        "wires": [{"id": str,
                   "from": {"nodeId": str, "pinId": str},
                   "to":   {"nodeId": str, "pinId": str}}, ...],
    }
    """
    nodes = list(graph.get("nodes") or [])
    fixup = dict(graph.get("drc_fixup") or {})
    edge_pad_extra = float(fixup.get("edge_pad_extra_mm") or 0.0)
    module_gap = MODULE_GAP + float(fixup.get("module_gap_extra_mm") or 0.0)
    via_clearance_mm = float(fixup.get("via_clearance_mm") or 0.21)
    if os.environ.get("HARDWARE_SPLICER_HPWL_PLACE", "1").strip().lower() in ("1", "true", "yes", "on"):
        from .placement_hpwl import reorder_nodes_for_placement

        nodes = reorder_nodes_for_placement(graph)
    # --- 1) Place each module on a grid ---
    placed: list[dict] = []
    cursor_x = BOARD_MARGIN
    cursor_y = BOARD_MARGIN
    row_max_h = 0.0
    col_idx = 0

    for node in nodes:
        spec = find_module(node["moduleId"])
        if spec is None:
            from .arbitrary_placement import synthetic_module_spec

            spec = synthetic_module_spec(
                str(node.get("moduleId") or ""),
                footprint=str(node.get("footprint") or ""),
                value=str(node.get("value") or ""),
                ref=str(node.get("ref") or node.get("id") or ""),
                pin_ids=list(node.get("pinIds") or []) or None,
            )

        pad_defs = resolve_module_pads(spec["id"], spec) or []
        use_custom_pads = len(pad_defs) > 0

        half = math.ceil(len(spec["pins"]) / 2)
        rows = half
        pad_w = 2 * PITCH
        body = resolve_module_body_mm(spec["id"])
        if body is None and spec.get("_body_mm"):
            body = spec["_body_mm"]
        from_pads = bounds_from_pads(pad_defs, MODULE_MARGIN_X)

        if use_custom_pads:
            footprint_w = body["w"] if body else from_pads["w"]
            footprint_h = body["h"] if body else from_pads["h"]
        else:
            footprint_w = pad_w + 2 * MODULE_MARGIN_X
            footprint_h = (rows - 1) * PITCH + 2 * MODULE_MARGIN_Y + PITCH

        center_x = cursor_x + footprint_w / 2
        center_y = cursor_y + footprint_h / 2
        pad_layout = _detect_pad_layout(pad_defs) if use_custom_pads else "dual"

        if use_custom_pads:
            pad_pos: dict[str, dict] = {}
            for d in pad_defs:
                pad_pos[d["pinId"]] = {
                    "x": center_x + d["x"],
                    "y": center_y + d["y"],
                }
            pin_order = [d["pinId"] for d in pad_defs]
        else:
            pad_pos, pin_order = _synthetic_dual_column_pads(spec, center_x, center_y)

        pad_xs = [p["x"] for p in pad_pos.values()]
        pad_min_x = min(pad_xs)
        pad_max_x = max(pad_xs)

        placed.append({
            "nodeId":    node["id"],
            "spec":      spec,
            "x":         center_x,
            "y":         center_y,
            "hw":        footprint_w / 2,
            "hh":        footprint_h / 2,
            "padMinX":   pad_min_x,
            "padMaxX":   pad_max_x,
            "padPos":    pad_pos,
            "pinOrder":  pin_order,
            "padLayout": pad_layout,
        })

        row_max_h = max(row_max_h, footprint_h)
        col_idx += 1
        if col_idx >= COLS:
            col_idx = 0
            cursor_x = BOARD_MARGIN
            cursor_y += row_max_h + module_gap
            row_max_h = 0.0
        else:
            cursor_x += footprint_w + module_gap

    if not placed:
        return {"board": {"bbox_mm": None}, "nets": [], "footprints": [], "segments": []}

    # --- 2) Board bbox ---
    min_x =  math.inf
    max_x = -math.inf
    min_y =  math.inf
    max_y = -math.inf
    for p in placed:
        min_x = min(min_x, p["x"] - p["hw"])
        max_x = max(max_x, p["x"] + p["hw"])
        min_y = min(min_y, p["y"] - p["hh"])
        max_y = max(max_y, p["y"] + p["hh"])
    min_x -= BOARD_MARGIN
    max_x += BOARD_MARGIN
    min_y -= BOARD_MARGIN
    max_y += BOARD_MARGIN

    # --- 3) Compute nets via union-find over wires ---
    pairs: list[tuple[str, str]] = [
        (f"{w['from']['nodeId']}|{w['from']['pinId']}",
         f"{w['to']['nodeId']}|{w['to']['pinId']}")
        for w in graph["wires"]
    ]
    all_pin_ids: list[str] = [
        f"{p['nodeId']}|{pid}"
        for p in placed
        for pid in p["pinOrder"]
    ]
    roots = _union_find(pairs, all_pin_ids)

    # Build helper: key → (placed, pinId)
    pad_by_key: dict[str, dict] = {}
    for p in placed:
        for pin_id in p["pinOrder"]:
            pad_by_key[f"{p['nodeId']}|{pin_id}"] = {"placed": p, "pinId": pin_id}

    # Name nets; GND / +3V3 / +5V / Net-N
    root_to_net: dict[str, dict] = {}
    net_counter = 1

    # Group keys by root
    root_members: dict[str, list[str]] = {}
    for key, root in roots.items():
        root_members.setdefault(root, []).append(key)

    for root, members in root_members.items():
        if root in root_to_net:
            continue
        roles = []
        voltages = []
        for m in members:
            hit = pad_by_key.get(m)
            if hit is None:
                roles.append(None)
                voltages.append(None)
                continue
            pin = next((pp for pp in hit["placed"]["spec"]["pins"] if pp["id"] == hit["pinId"]), None)
            roles.append(pin.get("role") if pin else None)
            voltages.append(pin.get("voltage") if pin else None)

        if "gnd" in roles:
            name = "GND"
        else:
            v = next((x for x in voltages if x is not None), None)
            if v == "3.3V":
                name = "+3V3"
            elif v == "5V":
                name = "+5V"
            else:
                name = f"Net-{net_counter}"

        root_to_net[root] = {"id": net_counter, "name": name}
        net_counter += 1

    # Deduplicate net names (e.g. two GND clusters → GND, GND-2)
    seen: dict[str, int] = {}
    for net in root_to_net.values():
        base = net["name"]
        c = seen.get(base, 0)
        if c > 0:
            net["name"] = f"{base}-{c + 1}"
        seen[base] = c + 1

    # --- 4) Build footprints with pads ---
    footprints = []
    for idx, p in enumerate(placed):
        pad_defs = resolve_module_pads(p["spec"]["id"], p["spec"]) or []
        pads = []
        for i, pin_id in enumerate(p["pinOrder"]):
            def_entry = next((d for d in pad_defs if d["pinId"] == pin_id), None)
            if def_entry:
                pos = {"x": p["x"] + def_entry["x"], "y": p["y"] + def_entry["y"]}
            else:
                pos = p["padPos"][pin_id]
            net_key = f"{p['nodeId']}|{pin_id}"
            root = roots.get(net_key, net_key)
            net = root_to_net.get(root, {"id": 0, "name": ""})
            pads.append({
                "num":        str(i + 1),
                "wx":         pos["x"],
                "wy":         pos["y"],
                "net":        net,
                "shape":      "circle",
                "size_w_mm":  PAD_SIZE,
                "size_h_mm":  PAD_SIZE,
                "drill_mm":   PAD_DRILL,
                "type":       "thru_hole",
            })
        footprints.append({
            "ref":       f"U{idx + 1}",
            "value":     p["spec"]["label"],
            "footprint": resolve_module_footprint(p["spec"]["id"]),
            "layer":     "F.Cu",
            "at":        {"x": p["x"], "y": p["y"], "rot_deg": 0},
            "pads":      pads,
        })

    # --- 5) Correct-by-construction 2-layer router ---
    # HV-split: horizontals on F.Cu, verticals on B.Cu.
    # Each net gets a unique horizontal rail Y and unique convergence column X.
    # Per-pad unique jog lanes; no two different-net features share layer+coord.
    segments: list[dict] = []
    vias: list[dict] = []
    RT_W = 0.25
    TRK  = 1.0
    GAP  = 6
    KICAD_CLEARANCE_MM = via_clearance_mm
    VIA_RADIUS = 0.4  # size_mm 0.8
    PAD_RADIUS = PAD_SIZE / 2
    single_layer_preview = os.environ.get("HARDWARE_SPLICER_SINGLE_LAYER_PREVIEW", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    def seg(
        start: dict, end: dict,
        layer: str,
        net: dict,
    ) -> None:
        if start["x"] == end["x"] and start["y"] == end["y"]:
            return
        segments.append({"start": start, "end": end, "width_mm": RT_W, "layer": layer, "net": net})

    def via(x: float, y: float, net: dict) -> None:
        # Nudge away from foreign pads so KiCad default 0.2 mm clearance passes.
        min_sep = VIA_RADIUS + PAD_RADIUS + KICAD_CLEARANCE_MM
        for pl in placed:
            for pid, pos in pl["padPos"].items():
                root = roots.get(f"{pl['nodeId']}|{pid}")
                if root is None:
                    continue
                if root_to_net.get(root, {}).get("id") == net.get("id"):
                    continue
                dx = x - pos["x"]
                dy = y - pos["y"]
                dist = math.hypot(dx, dy)
                if dist < min_sep and dist > 1e-6:
                    scale = min_sep / dist
                    x += dx * (scale - 1.0)
                    y += dy * (scale - 1.0)
                elif dist <= 1e-6:
                    y += min_sep
        vias.append({"x": x, "y": y, "size_mm": 0.8, "drill_mm": 0.4, "net": net})

    # Only nets with >= 2 pads are routed; each gets a unique rail Y.
    net_size: dict[str, int] = {}
    for r in roots.values():
        net_size[r] = net_size.get(r, 0) + 1

    seen_roots: list[str] = []
    seen_set: set[str] = set()
    for r in roots.values():
        if r not in seen_set:
            seen_roots.append(r)
            seen_set.add(r)
    ordered_roots = [r for r in seen_roots if net_size.get(r, 0) >= 2]
    k_of: dict[str, int] = {r: i for i, r in enumerate(ordered_roots)}

    routed_pad_count = 0
    for pl in placed:
        for pid in pl["pinOrder"]:
            root = roots.get(f"{pl['nodeId']}|{pid}")
            if root is not None and root in k_of and net_size.get(root, 0) >= 2:
                routed_pad_count += 1

    global_bus_slot = [0]  # mutable cell to allow nested function mutation

    def next_bus_y() -> float:
        y = max_y + 2 + global_bus_slot[0] * TRK
        global_bus_slot[0] += 1
        return y

    rail_y0 = max_y + 2 + routed_pad_count * TRK + GAP

    def rail_y(k: int) -> float:
        return rail_y0 + k * TRK

    last_right = -math.inf
    for p in placed:
        last_right = max(last_right, p["padMaxX"] + PAD_SIZE / 2, p["x"] + p["hw"])

    b_cu_col_slot = [0]

    def alloc_b_cu_x() -> float:
        x = last_right + MODULE_GAP + 2 + b_cu_col_slot[0] * TRK
        b_cu_col_slot[0] += 1
        return x

    conv_x0 = last_right + MODULE_GAP + GAP + routed_pad_count * TRK

    def conv_x(k: int) -> float:
        return conv_x0 + k * TRK

    HALF = MODULE_GAP / 2
    route_min_x = math.inf
    route_max_x = -math.inf
    route_max_y = -math.inf

    def y_eq(a: float, b: float) -> bool:
        return abs(a - b) < 0.05

    def finish_from_channel(
        at: dict,
        net: dict,
        tag: dict,
        k: int,
    ) -> None:
        nonlocal route_min_x, route_max_x, route_max_y
        drop_x = alloc_b_cu_x()
        ry = rail_y(k)
        cx = conv_x(k)
        if at["x"] != drop_x:
            seg(at, {"x": drop_x, "y": at["y"]}, "F.Cu", tag)
        if single_layer_preview:
            seg({"x": drop_x, "y": at["y"]}, {"x": drop_x, "y": ry}, "F.Cu", tag)
            seg({"x": drop_x, "y": ry}, {"x": cx, "y": ry}, "F.Cu", tag)
        else:
            via(drop_x, at["y"], net)
            seg({"x": drop_x, "y": at["y"]}, {"x": drop_x, "y": ry}, "B.Cu", tag)
            via(drop_x, ry, net)
            seg({"x": drop_x, "y": ry}, {"x": cx, "y": ry}, "F.Cu", tag)
            via(cx, ry, net)
        route_min_x = min(route_min_x, drop_x, at["x"], cx)
        route_max_x = max(route_max_x, drop_x, at["x"], cx)
        route_max_y = max(route_max_y, ry, at["y"])

    for pl in placed:
        left_pads:   list[dict] = []
        right_pads:  list[dict] = []
        bottom_pads: list[dict] = []

        for pid in pl["pinOrder"]:
            pos = pl["padPos"][pid]
            if pl["padLayout"] == "row":
                bottom_pads.append({"pid": pid, "x": pos["x"], "y": pos["y"]})
            elif pl["padLayout"] == "general":
                edge = _pick_escape_edge(pos, pl, pl["padLayout"])
                if edge == "left":
                    left_pads.append({"pid": pid, "y": pos["y"]})
                elif edge == "right":
                    right_pads.append({"pid": pid, "y": pos["y"]})
                else:
                    bottom_pads.append({"pid": pid, "x": pos["x"], "y": pos["y"]})
            else:  # "dual"
                if pos["x"] < pl["x"]:
                    left_pads.append({"pid": pid, "y": pos["y"]})
                else:
                    right_pads.append({"pid": pid, "y": pos["y"]})

        def route_side(side: list[dict], outward: str) -> None:
            routed = [
                s for s in side
                if (r := roots.get(f"{pl['nodeId']}|{s['pid']}")) is not None
                and r in k_of
                and net_size.get(r, 0) >= 2
            ]
            m = len(routed)
            if outward == "right":
                pad_edge = pl["padMaxX"] + PAD_SIZE / 2
                ch_lo = pad_edge + 0.6
                ch_hi = pad_edge + HALF - 0.6
            else:
                pad_edge = pl["padMinX"] - PAD_SIZE / 2
                ch_lo = pad_edge - HALF + 0.6
                ch_hi = pad_edge - 0.6

            idx2 = 0
            for entry in routed:
                pid = entry["pid"]
                y   = entry["y"]
                key = f"{pl['nodeId']}|{pid}"
                root = roots[key]
                k    = k_of[root]
                net  = root_to_net[root]
                tag  = {"id": net["id"], "name": net["name"]}
                p_pos = pl["padPos"][pid]
                escape_x = ch_lo + ((idx2 + 1) * (ch_hi - ch_lo)) / (m + 1)
                idx2 += 1

                hop_y = p_pos["y"]
                same_y = [s for s in routed if y_eq(s["y"], y)]
                if len(same_y) > 1:
                    tier = next(i for i, s in enumerate(same_y) if s["pid"] == pid)
                    bump = (-1.3 if tier % 2 == 0 else 1.3) * (tier // 2 + 1)
                    hop_y = p_pos["y"] + bump

                stage_y = next_bus_y()
                if not y_eq(p_pos["y"], hop_y):
                    seg(p_pos, {"x": p_pos["x"], "y": hop_y}, "F.Cu", tag)
                if p_pos["x"] != escape_x:
                    seg({"x": p_pos["x"], "y": hop_y}, {"x": escape_x, "y": hop_y}, "F.Cu", tag)
                if not y_eq(hop_y, stage_y):
                    if single_layer_preview:
                        seg({"x": escape_x, "y": hop_y}, {"x": escape_x, "y": stage_y}, "F.Cu", tag)
                    else:
                        via(escape_x, hop_y, net)
                        seg({"x": escape_x, "y": hop_y}, {"x": escape_x, "y": stage_y}, "B.Cu", tag)
                        via(escape_x, stage_y, net)
                finish_from_channel({"x": escape_x, "y": stage_y}, net, tag, k)

        def route_bottom(side: list[dict]) -> None:
            routed = [
                s for s in side
                if (r := roots.get(f"{pl['nodeId']}|{s['pid']}")) is not None
                and r in k_of
                and net_size.get(r, 0) >= 2
            ]
            m = len(routed)
            ch_lo = pl["padMinX"] - PAD_SIZE / 2 - HALF + 0.6
            ch_hi = pl["padMaxX"] + PAD_SIZE / 2 + HALF - 0.6

            idx2 = 0
            for entry in routed:
                pid = entry["pid"]
                key = f"{pl['nodeId']}|{pid}"
                root = roots[key]
                k    = k_of[root]
                net  = root_to_net[root]
                tag  = {"id": net["id"], "name": net["name"]}
                p_pos = pl["padPos"][pid]
                stage_y = next_bus_y()
                escape_x = ch_lo + ((idx2 + 1) * (ch_hi - ch_lo)) / (m + 1)
                idx2 += 1

                hop_y = p_pos["y"]
                same_y_count = sum(1 for s in routed if y_eq(s["y"], p_pos["y"]))
                if same_y_count > 1:
                    tier = idx2 - 1
                    bump = (-1.3 if tier % 2 == 0 else 1.3) * (tier // 2 + 1)
                    hop_y = p_pos["y"] + bump

                if not y_eq(p_pos["y"], hop_y):
                    seg(p_pos, {"x": p_pos["x"], "y": hop_y}, "F.Cu", tag)
                if p_pos["x"] != escape_x:
                    seg({"x": p_pos["x"], "y": hop_y}, {"x": escape_x, "y": hop_y}, "F.Cu", tag)
                if not y_eq(hop_y, stage_y):
                    if single_layer_preview:
                        seg({"x": escape_x, "y": hop_y}, {"x": escape_x, "y": stage_y}, "F.Cu", tag)
                    else:
                        via(escape_x, hop_y, net)
                        seg({"x": escape_x, "y": hop_y}, {"x": escape_x, "y": stage_y}, "B.Cu", tag)
                        via(escape_x, stage_y, net)
                finish_from_channel({"x": escape_x, "y": stage_y}, net, tag, k)

        route_side(right_pads, "right")
        route_side(left_pads, "left")
        route_bottom(bottom_pads)

    # --- 6) Silkscreen rectangle + label per module ---
    silk_lines: list[dict] = []
    silk_text:  list[dict] = []
    for p in placed:
        x0 = p["x"] - p["hw"]
        x1 = p["x"] + p["hw"]
        y0 = p["y"] - p["hh"]
        y1 = p["y"] + p["hh"]
        silk_lines += [
            {"layer": "F.SilkS", "start": {"x": x0, "y": y0}, "end": {"x": x1, "y": y0}, "width_mm": 0.15},
            {"layer": "F.SilkS", "start": {"x": x1, "y": y0}, "end": {"x": x1, "y": y1}, "width_mm": 0.15},
            {"layer": "F.SilkS", "start": {"x": x1, "y": y1}, "end": {"x": x0, "y": y1}, "width_mm": 0.15},
            {"layer": "F.SilkS", "start": {"x": x0, "y": y1}, "end": {"x": x0, "y": y0}, "width_mm": 0.15},
        ]
        silk_text.append({
            "layer":  "F.SilkS",
            "text":   p["spec"]["label"],
            "at":     {"x": p["x"], "y": y0 - 1.0, "rot_deg": 0},
            "size_mm": 1.0,
        })
    for idx, p in enumerate(placed):
        silk_text.append({
            "layer":  "F.SilkS",
            "text":   f"U{idx + 1}",
            "at":     {"x": p["x"], "y": p["y"] + p["hh"] - 1.2, "rot_deg": 0},
            "size_mm": 1.4,
        })

    # --- 8) Board outline (include routed copper + KiCad 0.5 mm edge clearance) ---
    KICAD_EDGE_CLEARANCE = 0.55
    copper_min_x = min(min_x, route_min_x if route_min_x != math.inf else min_x)
    copper_max_x = max(max_x, route_max_x if route_max_x != -math.inf else max_x)
    copper_min_y = min_y
    copper_max_y = max(route_max_y if route_max_y != -math.inf else max_y, max_y)
    for s in segments:
        copper_min_x = min(copper_min_x, s["start"]["x"], s["end"]["x"])
        copper_max_x = max(copper_max_x, s["start"]["x"], s["end"]["x"])
        copper_min_y = min(copper_min_y, s["start"]["y"], s["end"]["y"])
        copper_max_y = max(copper_max_y, s["start"]["y"], s["end"]["y"])
    for v in vias:
        copper_min_x = min(copper_min_x, v["x"] - VIA_RADIUS)
        copper_max_x = max(copper_max_x, v["x"] + VIA_RADIUS)
        copper_min_y = min(copper_min_y, v["y"] - VIA_RADIUS)
        copper_max_y = max(copper_max_y, v["y"] + VIA_RADIUS)

    edge_pad = KICAD_EDGE_CLEARANCE + RT_W / 2 + 0.15 + edge_pad_extra
    bx0 = copper_min_x - edge_pad
    by0 = copper_min_y - edge_pad
    bx1 = copper_max_x + edge_pad
    by1 = copper_max_y + edge_pad

    return {
        "board": {
            "bbox_mm": {
                "min_x":  bx0,
                "min_y":  by0,
                "max_x":  bx1,
                "max_y":  by1,
                "width":  bx1 - bx0,
                "height": by1 - by0,
            },
        },
        "nets":       list(root_to_net.values()),
        "footprints": footprints,
        "segments":   segments,
        "vias":       vias,
        "silkLines":  silk_lines,
        "silkText":   silk_text,
        "edgeLines": [
            {"start": {"x": bx0, "y": by0}, "end": {"x": bx1, "y": by0}},
            {"start": {"x": bx1, "y": by0}, "end": {"x": bx1, "y": by1}},
            {"start": {"x": bx1, "y": by1}, "end": {"x": bx0, "y": by1}},
            {"start": {"x": bx0, "y": by1}, "end": {"x": bx0, "y": by0}},
        ],
    }
