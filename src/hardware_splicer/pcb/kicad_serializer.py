"""BuildGraph + PcbGeometry → .kicad_pcb serializer (Python engine port)."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Optional

from .build_to_geometry import build_graph_to_geometry
from .footprint_sizes import infer_footprint_size

HEADER = """(kicad_pcb (version 20241229) (generator "hardware-splicer")
  (generator_version "9.0")
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (40 "Edge.Cuts" user)
  )
  (setup
    (pad_to_mask_clearance 0)
  )
"""

FOOTER = ")\n"


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _n(v: float) -> str:
    return f"{v:.4f}" if isinstance(v, (int, float)) and v == v else "0"


def _build_net_table(geo: Mapping[str, Any]) -> tuple[str, Callable[[Optional[int]], int], Callable[[Optional[int]], str]]:
    by_geo_id: Dict[int, Dict[str, Any]] = {}
    decls = ['  (net 0 "")']
    kid = 1
    for net in geo.get("nets") or []:
        net_id = net.get("id")
        if net_id is None or net_id in by_geo_id:
            continue
        by_geo_id[int(net_id)] = {"kid": kid, "name": net.get("name") or ""}
        decls.append(f"  (net {kid} {_quote(str(net.get('name') or ''))})")
        kid += 1

    def kid_of(net_id: Optional[int]) -> int:
        if net_id is None:
            return 0
        return by_geo_id.get(int(net_id), {}).get("kid", 0)

    def name_of(net_id: Optional[int]) -> str:
        if net_id is None:
            return ""
        return by_geo_id.get(int(net_id), {}).get("name", "")

    return "\n".join(decls), kid_of, name_of


def _resolve_footprint_lib(fp: Mapping[str, Any]) -> str:
    named = str(fp.get("footprint") or "").strip()
    if named and not re.search(r"PinHeader_", named, re.I):
        return named
    pin_count = len(fp.get("pads") or []) or 1
    return f"Connector_PinHeader_2.54mm:PinHeader_1x{pin_count:02d}_P2.54mm_Vertical"


def _footprint_body_outline(fp: Mapping[str, Any], lib: str) -> str:
    size = infer_footprint_size(lib, str(fp.get("ref") or "U"))
    hw_v = float(size["w_mm"]) / 2
    hh_v = float(size["h_mm"]) / 2
    return (
        f'    (fp_rect (start {_n(-hw_v)} {_n(-hh_v)}) (end {_n(hw_v)} {_n(hh_v)}) '
        f'(stroke (width 0.12) (type default)) (fill none) (layer "F.Fab"))'
    )


def _footprint_block(
    fp: Mapping[str, Any],
    idx: int,
    kid_of: Callable[[Optional[int]], int],
    name_of: Callable[[Optional[int]], str],
) -> str:
    lib = _resolve_footprint_lib(fp)
    body = _footprint_body_outline(fp, lib)
    pad_lines = []
    for pad in fp.get("pads") or []:
        lx = _n(float(pad["wx"]) - float(fp["at"]["x"]))
        ly = _n(float(pad["wy"]) - float(fp["at"]["y"]))
        w = _n(float(pad.get("size_w_mm") or 1.7))
        h = _n(float(pad.get("size_h_mm") or 1.7))
        drill = f" (drill {_n(float(pad['drill_mm']))})" if pad.get("drill_mm") else ""
        net = pad.get("net") or {}
        kid = kid_of(net.get("id"))
        net_str = "" if kid == 0 else f" (net {kid} {_quote(name_of(net.get('id')))})"
        shape = pad.get("shape") or "circle"
        pad_type = pad.get("type") or "thru_hole"
        layers = '"F.Cu" "F.Paste" "F.Mask"' if pad_type == "smd" else '"*.Cu" "*.Mask"'
        pad_lines.append(
            f"    (pad {_quote(str(pad.get('num')))} {pad_type} {shape} (at {lx} {ly}) (size {w} {h}){drill} (layers {layers}){net_str})"
        )
    pads = "\n".join(pad_lines)
    at = fp.get("at") or {}
    return f"""  (footprint {_quote(lib)} (layer "{fp.get('layer', 'F.Cu')}")
    (at {_n(float(at.get('x', 0)))} {_n(float(at.get('y', 0)))} {_n(float(at.get('rot_deg', 0)))})
    (attr through_hole)
    (fp_text reference {_quote(str(fp.get('ref') or f'U{idx + 1}'))} (at 0 -3) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
    (fp_text value {_quote(str(fp.get('value') or fp.get('ref') or ''))} (at 0 3) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
{body}
{pads}
  )"""


def serialize_build_to_kicad_pcb(graph: Mapping[str, Any], geometry: Optional[Mapping[str, Any]] = None) -> str:
    geo = dict(geometry) if geometry is not None else build_graph_to_geometry(dict(graph))
    decls, kid_of, name_of = _build_net_table(geo)

    footprints = "\n".join(
        _footprint_block(fp, i, kid_of, name_of) for i, fp in enumerate(geo.get("footprints") or [])
    )

    segments = "\n".join(
        f'  (segment (start {_n(s["start"]["x"])} {_n(s["start"]["y"])}) (end {_n(s["end"]["x"])} {_n(s["end"]["y"])}) (width {_n(float(s.get("width_mm") or 0.25))}) (layer "{s["layer"]}") (net {kid_of((s.get("net") or {}).get("id"))}))'
        for s in geo.get("segments") or []
        if not (s["start"]["x"] == s["end"]["x"] and s["start"]["y"] == s["end"]["y"])
    )

    vias = "\n".join(
        f'  (via (at {_n(v["x"])} {_n(v["y"])}) (size {_n(float(v.get("size_mm") or 0.8))}) (drill {_n(float(v.get("drill_mm") or 0.4))}) (layers "F.Cu" "B.Cu") (net {kid_of(v.get("net", {}).get("id"))}))'
        for v in geo.get("vias") or []
    )

    edges = "\n".join(
        f'  (gr_line (start {_n(e["start"]["x"])} {_n(e["start"]["y"])}) (end {_n(e["end"]["x"])} {_n(e["end"]["y"])}) (layer "Edge.Cuts") (width 0.1))'
        for e in geo.get("edgeLines") or []
    )

    silk_parts: List[str] = []
    for line in geo.get("silkLines") or []:
        silk_parts.append(
            f'  (gr_line (start {_n(line["start"]["x"])} {_n(line["start"]["y"])}) (end {_n(line["end"]["x"])} {_n(line["end"]["y"])}) (layer "{line["layer"]}") (width {_n(float(line.get("width_mm") or 0.15))}))'
        )
    for text in geo.get("silkText") or []:
        at = text.get("at") or {}
        silk_parts.append(
            f'  (gr_text {_quote(str(text.get("text") or ""))} (at {_n(float(at.get("x", 0)))} {_n(float(at.get("y", 0)))} {_n(float(at.get("rot_deg", 0)))}) (layer "{text.get("layer", "F.SilkS")}") (effects (font (size {_n(float(text.get("size_mm") or 1))} {_n(float(text.get("size_mm") or 1))}) (thickness 0.15))))'
        )
    silk = "\n".join(silk_parts)

    return HEADER + decls + "\n" + "\n".join(x for x in [footprints, segments, vias, edges, silk] if x) + "\n" + FOOTER
