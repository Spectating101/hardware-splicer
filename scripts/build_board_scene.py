"""Turn a KiCad board into a device scene: the real board outline and one box per footprint.

Run with an interpreter that has KiCad's pcbnew and trimesh (the native CAD venv does):

    python scripts/build_board_scene.py BOARD.kicad_pcb --project projects/<id> [--title T]

Writes, inside the project folder: cad/<board>.glb (millimetres, Z up), BOM.json (each footprint's
reference and value, so parts are labelled "U1 · ESP32-WROOM-32"), geometry-basis.json (the board is
custom geometry; every footprint is an envelope) and footprint-heights.json (the height each box
was given and why). Then build the parts sidecar with scripts/build_parts_sidecar.py.

The board is the Edge.Cuts outline with its holes, extruded to the board's design thickness
(manifold3d), so it is a closed solid. A footprint box covers its pads and graphics in X/Y (KiCad's bounding
box without text). Without the component's 3D model its height is not known: each box takes an
assumed height, recorded as an assumption, so a fit check involving it is a stand-in result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

# Assumed component heights (mm) by footprint family, used only when nothing better is known.
# Each one is recorded in footprint-heights.json as an assumption, never as a measurement.
ASSUMED_HEIGHT_MM = [
    (r"(?i)esp32|wroom|module", 3.2, "typical RF module height"),
    (r"(?i)usb", 3.3, "typical USB receptacle height"),
    (r"(?i)pin_?header|conn|jst|port|terminal", 8.5, "typical 2.54 mm pin header height"),
    (r"(?i)mountinghole|mount|mh\d", 0.0, "a hole, no body"),
    (r"(?i)qfn|qfp|soic|sot|tssop|dfn|cp2102", 1.8, "typical IC package height"),
    (r"(?i)0402|0603|0805|1206|r_|c_|l_|led", 0.9, "typical chip component height"),
]
DEFAULT_HEIGHT = (2.0, "no footprint family matched; a generic 2 mm body")


def assumed_height(footprint_name: str, value: str, reference: str) -> tuple[float, str]:
    text = f"{footprint_name} {value} {reference}"
    for pattern, height, why in ASSUMED_HEIGHT_MM:
        if re.search(pattern, text):
            return height, why
    return DEFAULT_HEIGHT


def board_mesh(board, pcbnew, trimesh, numpy):
    """The Edge.Cuts outline and its holes, extruded to the board thickness as one closed solid."""
    import manifold3d

    outline = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outline):
        raise SystemExit("The board outline (Edge.Cuts) is not a closed shape.")
    thickness = pcbnew.ToMM(board.GetDesignSettings().GetBoardThickness())

    def ring(chain):
        # KiCad's Y grows downwards; flip it so the board reads the right way up in Z-up space.
        return [[pcbnew.ToMM(chain.CPoint(i).x), -pcbnew.ToMM(chain.CPoint(i).y)] for i in range(chain.PointCount())]

    rings = []
    for index in range(outline.OutlineCount()):
        rings.append(ring(outline.Outline(index)))
        rings.extend(ring(outline.Hole(index, hole)) for hole in range(outline.HoleCount(index)))
    section = manifold3d.CrossSection(rings, manifold3d.FillRule.EvenOdd)
    solid = manifold3d.Manifold.extrude(section, thickness).to_mesh()
    slab = trimesh.Trimesh(numpy.asarray(solid.vert_properties)[:, :3], numpy.asarray(solid.tri_verts))
    return slab, thickness


COPPER_MM = 0.035  # 1 oz copper, drawn on the board surface


def copper_meshes(board, pcbnew, trimesh, numpy, thickness):
    """Real copper per net: tracks and arcs as strips, vias as barrels, pads as their outline shapes,
    filled zones from their fill polygons. Returns {net name: [mesh, ...]}. Copper sits on the board
    surface (top side above, bottom side below) so it is visible from either side."""
    import manifold3d

    nets: dict[str, list] = {}
    top, bottom = pcbnew.F_Cu, pcbnew.B_Cu

    def z_for(layer):
        return (thickness, thickness + COPPER_MM) if layer == top else (-COPPER_MM, 0.0)

    def add(net, mesh):
        nets.setdefault(net or "(no net)", []).append(mesh)

    def xy(point):
        return pcbnew.ToMM(point.x), -pcbnew.ToMM(point.y)

    def strip(a, b, width, layer, net):
        (x0, y0), (x1, y1) = xy(a), xy(b)
        length = float(numpy.hypot(x1 - x0, y1 - y0))
        z0, z1 = z_for(layer)
        box = trimesh.creation.box(extents=[length + width, width, z1 - z0])
        angle = float(numpy.arctan2(y1 - y0, x1 - x0))
        box.apply_transform(trimesh.transformations.rotation_matrix(angle, [0, 0, 1]))
        box.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
        add(net, box)

    for item in board.GetTracks():
        net = item.GetNetname()
        via = item.GetClass() == "PCB_VIA"
        width = pcbnew.ToMM(item.GetWidth(top) if via else item.GetWidth())
        if via:
            x, y = xy(item.GetPosition())
            barrel = trimesh.creation.cylinder(radius=width / 2, height=thickness + 2 * COPPER_MM, sections=16)
            barrel.apply_translation([x, y, thickness / 2])
            add(net, barrel)
        elif item.GetClass() == "PCB_ARC":
            start, mid, end = item.GetStart(), item.GetMid(), item.GetEnd()
            strip(start, mid, width, item.GetLayer(), net)
            strip(mid, end, width, item.GetLayer(), net)
        elif item.GetLayer() in (top, bottom):
            strip(item.GetStart(), item.GetEnd(), width, item.GetLayer(), net)

    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            sx, sy = pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)
            x, y = xy(pad.GetPosition())
            angle = numpy.radians(pad.GetOrientationDegrees())
            for layer in (top, bottom):
                if not pad.IsOnLayer(layer):
                    continue
                z0, z1 = z_for(layer)
                if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
                    shape = trimesh.creation.cylinder(radius=sx / 2, height=z1 - z0, sections=24)
                else:
                    shape = trimesh.creation.box(extents=[sx, sy, z1 - z0])
                shape.apply_transform(trimesh.transformations.rotation_matrix(angle, [0, 0, 1]))
                shape.apply_translation([x, y, (z0 + z1) / 2])
                add(pad.GetNetname(), shape)

    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue
        for layer in (top, bottom):
            if not zone.IsOnLayer(layer) or not zone.HasFilledPolysForLayer(layer):
                continue
            fill = zone.GetFilledPolysList(layer)
            rings = []
            for index in range(fill.OutlineCount()):
                for chain in [fill.Outline(index)] + [fill.Hole(index, h) for h in range(fill.HoleCount(index))]:
                    rings.append([[pcbnew.ToMM(chain.CPoint(i).x), -pcbnew.ToMM(chain.CPoint(i).y)]
                                  for i in range(chain.PointCount())])
            if not rings:
                continue
            z0, z1 = z_for(layer)
            solid = manifold3d.Manifold.extrude(manifold3d.CrossSection(rings, manifold3d.FillRule.EvenOdd),
                                                z1 - z0).translate([0, 0, z0]).to_mesh()
            add(zone.GetNetname(), trimesh.Trimesh(numpy.asarray(solid.vert_properties)[:, :3], numpy.asarray(solid.tri_verts)))
    return nets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("board", type=Path)
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()

    import numpy
    import pcbnew
    import trimesh

    board = pcbnew.LoadBoard(str(args.board))
    project = args.project
    (project / "cad").mkdir(parents=True, exist_ok=True)
    slab, thickness = board_mesh(board, pcbnew, trimesh, numpy)
    scene = trimesh.Scene()
    scene.add_geometry(slab, node_name="board", geom_name="board")
    # One copper node per net, named "net:<net>", so a DRC short can highlight both nets' copper.
    copper = copper_meshes(board, pcbnew, trimesh, numpy, thickness)
    for net in sorted(copper):
        merged = trimesh.util.concatenate(copper[net])
        scene.add_geometry(merged, node_name=f"net:{net}", geom_name=f"net:{net}")
    bom, heights = [], {}
    for footprint in sorted(board.GetFootprints(), key=lambda fp: fp.GetReference()):
        reference = footprint.GetReference()
        value = footprint.GetValue()
        name = footprint.GetFPIDAsString()
        height, why = assumed_height(name, value, reference)
        heights[reference] = {"height_mm": height, "state": "assumed", "why": why, "footprint": name}
        box = footprint.GetBoundingBox(False, False)
        # KiCad coordinates (mm, Y down), so a DRC/ERC position can be traced to its footprint.
        bom.append({"id": reference, "name": f"{reference} · {value}", "footprint": name,
                    "bbox_kicad_mm": [round(pcbnew.ToMM(v), 4) for v in (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())]})
        if height <= 0:
            continue
        x0, x1 = pcbnew.ToMM(box.GetLeft()), pcbnew.ToMM(box.GetRight())
        y0, y1 = -pcbnew.ToMM(box.GetBottom()), -pcbnew.ToMM(box.GetTop())
        bottom = footprint.IsFlipped()
        z0 = -height if bottom else thickness
        body = trimesh.creation.box(extents=[x1 - x0, y1 - y0, height])
        body.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, z0 + height / 2])
        scene.add_geometry(body, node_name=reference, geom_name=reference)

    # Nets are labelled too, so their copper reads "Net GND · copper" in the workspace.
    bom.extend({"id": f"net:{net}", "name": f"Net {net} · copper"} for net in sorted(copper))
    glb = project / "cad" / f"{args.board.stem}.glb"
    glb.write_bytes(scene.export(file_type="glb"))
    source = hashlib.sha256(args.board.read_bytes()).hexdigest()
    (project / "BOM.json").write_text(json.dumps({"source_board": args.board.as_posix(), "source_sha256": source,
                                                  "items": bom}, indent=2) + "\n")
    (project / "footprint-heights.json").write_text(json.dumps({
        "note": "Footprint boxes cover each footprint's pads and graphics in X/Y; heights are assumptions "
                "until the component's 3D model or datasheet height is attached.",
        "board_thickness_mm": thickness, "heights": heights}, indent=2) + "\n")
    (project / "geometry-basis.json").write_text(json.dumps({
        "source": f"{args.board.as_posix()} read with KiCad pcbnew {pcbnew.Version()}",
        "rules": [{"match": "board", "basis": "custom", "why": "the board outline from Edge.Cuts at its design thickness"},
                  {"match": "net:.*", "basis": "copper", "why": "the net's tracks, vias, pads and zone fills from the board file"},
                  {"match": ".+", "basis": "envelope", "why": "footprint box with an assumed height"}]}, indent=2) + "\n")
    print(json.dumps({"glb": glb.as_posix(), "footprints": len(bom), "nets": len(copper), "board_thickness_mm": thickness}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
