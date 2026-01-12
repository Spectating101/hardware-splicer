"""Extract lightweight geometry from a KiCad `.kicad_pcb` file (MVP-level).

This is sufficient for a simple 2.5D/3D viewer:
- board bounding box (Edge.Cuts) (best-effort)
- footprints with reference/value + 2D position + layer
- copper segments with start/end/width/layer/net
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.engines.kicad_sexp import parse_sexp_file, sexp_find_all


def _first_child(node: list, head: str) -> Optional[list]:
    for c in node:
        if isinstance(c, list) and c and c[0] == head:
            return c
    return None


def _extract_nets(ast: Any) -> Dict[int, str]:
    nets: Dict[int, str] = {}
    for n in sexp_find_all(ast, "net"):
        if len(n) >= 3 and isinstance(n[1], int) and isinstance(n[2], str):
            nets[n[1]] = n[2]
        elif len(n) >= 2 and isinstance(n[1], int):
            nets[n[1]] = ""
    return nets


def _extract_layer(node: list) -> str:
    layer = _first_child(node, "layer")
    if layer and len(layer) >= 2 and isinstance(layer[1], str):
        return layer[1]
    return ""


def _find_fp_text(fp: list, kind: str) -> Optional[str]:
    for child in fp:
        if not isinstance(child, list) or len(child) < 3:
            continue
        if child[0] != "fp_text":
            continue
        if str(child[1]) == kind and isinstance(child[2], str):
            return child[2]
    return None


def _find_property(fp: list, name: str) -> Optional[str]:
    for child in fp:
        if not isinstance(child, list) or len(child) < 3:
            continue
        if child[0] != "property":
            continue
        if isinstance(child[1], str) and child[1] == name and isinstance(child[2], str):
            return child[2]
    return None


def _extract_at(fp: list) -> Tuple[float, float, float]:
    at = _first_child(fp, "at")
    if not at or len(at) < 3:
        return 0.0, 0.0, 0.0
    x = float(at[1])
    y = float(at[2])
    rot = float(at[3]) if len(at) >= 4 else 0.0
    return x, y, rot


def extract_pcb_geometry(kicad_pcb_path: str) -> Dict[str, Any]:
    ast = parse_sexp_file(kicad_pcb_path)
    nets = _extract_nets(ast)

    footprints: List[Dict[str, Any]] = []
    segments: List[Dict[str, Any]] = []
    edge_points: List[Tuple[float, float]] = []

    for fp in sexp_find_all(ast, "footprint"):
        footprint_name = fp[1] if len(fp) >= 2 and isinstance(fp[1], str) else "Unknown"
        ref = _find_property(fp, "Reference") or _find_fp_text(fp, "reference") or "?"
        value = _find_property(fp, "Value") or _find_fp_text(fp, "value") or ""
        layer = _extract_layer(fp)
        x, y, rot = _extract_at(fp)

        footprints.append(
            {
                "ref": ref,
                "value": value,
                "footprint": footprint_name,
                "layer": layer,
                "at": {"x": x, "y": y, "rot_deg": rot},
            }
        )

    for seg in sexp_find_all(ast, "segment"):
        start = _first_child(seg, "start")
        end = _first_child(seg, "end")
        width = _first_child(seg, "width")
        layer = _extract_layer(seg)

        net_id = None
        for child in seg:
            if isinstance(child, list) and len(child) >= 2 and child[0] == "net" and isinstance(child[1], int):
                net_id = child[1]
                break

        if not start or not end or len(start) < 3 or len(end) < 3:
            continue

        segments.append(
            {
                "start": {"x": float(start[1]), "y": float(start[2])},
                "end": {"x": float(end[1]), "y": float(end[2])},
                "width_mm": float(width[1]) if width and len(width) >= 2 else None,
                "layer": layer,
                "net": {"id": net_id, "name": nets.get(net_id, "") if net_id is not None else ""},
            }
        )

    for head in ("gr_line", "gr_arc", "gr_rect", "gr_poly"):
        for gr in sexp_find_all(ast, head):
            if _extract_layer(gr) != "Edge.Cuts":
                continue
            for ptag in ("start", "end", "center", "mid"):
                p = _first_child(gr, ptag)
                if p and len(p) >= 3:
                    try:
                        edge_points.append((float(p[1]), float(p[2])))
                    except Exception:
                        pass

    board_bbox = None
    if edge_points:
        xs = [p[0] for p in edge_points]
        ys = [p[1] for p in edge_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        board_bbox = {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": max_x - min_x,
            "height": max_y - min_y,
        }

    return {
        "board": {"bbox_mm": board_bbox},
        "nets": [{"id": k, "name": v} for k, v in sorted(nets.items(), key=lambda kv: kv[0])],
        "footprints": footprints,
        "segments": segments,
    }

