"""Parametric HS-3G carbon frame in CadQuery.

Two flat plates, both cut from carbon sheet:

* a 3.0 mm unibody bottom plate: a 70 x 40 mm body, four arms at 45 degrees and
  round motor pads with ONE M2 bolt circle (``motor_pcd_mm``). No public page
  states the F1404's bolt circle, so the default is a best guess and the README
  gates cutting on a caliper measurement. Concave corners (arm roots and
  arm-to-pad junctions) are filleted with ``junction_fillet_r_mm``;
* a 1.6 mm top plate on four M3 x 30 mm standoffs that carries the GNSS/compass
  module well away from the ESC.

The battery hangs crosswise under the bottom plate (long side along y) on a
strap through two slots that straddle the pack's 30 mm width. The strap's top
run passes under the stack, which sits on nylon spacers so the strap clears
both the stack screws and the ESC board.

Every dimension lives in ``FRAME``; ``build()`` returns the solids, and
``measure()`` reads interface positions back off the generated solid rather
than trusting the parameters.
"""
from __future__ import annotations

import math
from typing import Any

import cadquery as cq

FRAME: dict[str, float] = {
    "wheelbase_mm": 135.0,          # motor-to-motor diagonal
    "bottom_t_mm": 3.0,
    "top_t_mm": 1.6,             # the cutter's 1.60 mm stock
    "body_l_mm": 70.0,              # along x (forward)
    "body_w_mm": 40.0,
    "body_corner_r_mm": 4.0,
    "arm_w_mm": 12.0,
    "pad_d_mm": 19.0,
    "junction_fillet_r_mm": 3.0,    # arm roots and arm-to-pad junctions
    "motor_center_hole_d_mm": 4.0,  # shaft-end / circlip clearance; measure
    "motor_bolt_hole_d_mm": 2.2,    # M2 clearance
    "motor_pcd_mm": 9.0,            # single bolt circle; MEASURE BEFORE CUTTING
    "stack_pitch_mm": 20.0,
    "stack_hole_d_mm": 3.2,         # M3 clearance
    "stack_spacer_len_mm": 5.0,     # nylon M3 spacer under the ESC
    "stack_spacer_af_mm": 5.0,
    "standoff_x_mm": 27.0,
    "standoff_y_mm": 7.0,
    "standoff_hole_d_mm": 3.2,
    "standoff_len_mm": 30.0,
    "standoff_af_mm": 5.0,          # hex across flats
    "top_l_mm": 64.0,
    "top_w_mm": 26.0,
    "top_corner_r_mm": 3.0,
    "strap_w_mm": 10.0,             # battery strap width
    "strap_t_mm": 1.5,              # strap thickness (assumed)
    "strap_slot_x_mm": 18.2,
    "strap_slot_w_mm": 3.2,     # = the cutter's minimum hole
}


def strap_slot_l_mm(p: dict[str, float] = FRAME) -> float:
    """Slot length along y, end to end: strap width plus 1 mm."""
    return p["strap_w_mm"] + 1.0

ARM_ANGLES_DEG = (45.0, 135.0, 225.0, 315.0)


def motor_positions(p: dict[str, float] = FRAME) -> list[tuple[float, float]]:
    r = p["wheelbase_mm"] / 2.0
    return [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a in ARM_ANGLES_DEG]


def _rounded_rect(l: float, w: float, r: float, t: float) -> cq.Workplane:
    return cq.Workplane("XY").rect(l, w).extrude(t).edges("|Z").fillet(r)


def bottom_outline(p: dict[str, float] = FRAME) -> cq.Workplane:
    """Body + arms + pads as one extruded outline with filleted concave corners.

    The fillet is a morphological closing of the plan outline: offset out by r,
    then back in by r. Convex corners come back unchanged; every concave corner
    (arm root, arm-to-pad junction) gets radius r.
    """
    t = p["bottom_t_mm"]
    r_motor = p["wheelbase_mm"] / 2.0
    plate = _rounded_rect(p["body_l_mm"], p["body_w_mm"], p["body_corner_r_mm"], t)
    for ang in ARM_ANGLES_DEG:
        arm = (cq.Workplane("XY").center(r_motor / 2.0, 0)
               .rect(r_motor, p["arm_w_mm"]).extrude(t)
               .rotate((0, 0, 0), (0, 0, 1), ang))
        plate = plate.union(arm)
    for (mx, my) in motor_positions(p):
        pad = cq.Workplane("XY").center(mx, my).circle(p["pad_d_mm"] / 2.0).extrude(t)
        plate = plate.union(pad)
    r = p["junction_fillet_r_mm"]
    if r <= 0:
        return plate
    wire = plate.faces("<Z").val().outerWire()
    closed = wire.offset2D(r, "arc")[0].offset2D(-r, "arc")[0]
    return cq.Workplane("XY").add(cq.Solid.extrudeLinear(cq.Face.makeFromWires(closed), cq.Vector(0, 0, t)))


def motor_bolt_holes(p: dict[str, float] = FRAME) -> list[tuple[float, float, float]]:
    """One M2 pattern per pad: four holes at 45 degrees to the arm axis."""
    out = []
    for ang, (mx, my) in zip(ARM_ANGLES_DEG, motor_positions(p)):
        rr = p["motor_pcd_mm"] / 2.0
        for k in range(4):
            a = math.radians(ang + 45.0 + 90.0 * k)
            out.append((mx + rr * math.cos(a), my + rr * math.sin(a), p["motor_bolt_hole_d_mm"]))
    return out


def bottom_plate(p: dict[str, float] = FRAME) -> cq.Workplane:
    t = p["bottom_t_mm"]
    plate = bottom_outline(p)
    holes: list[tuple[float, float, float]] = []
    s = p["stack_pitch_mm"] / 2.0
    holes += [(sx * s, sy * s, p["stack_hole_d_mm"]) for sx in (-1, 1) for sy in (-1, 1)]
    holes += [(sx * p["standoff_x_mm"], sy * p["standoff_y_mm"], p["standoff_hole_d_mm"])
              for sx in (-1, 1) for sy in (-1, 1)]
    holes += [(mx, my, p["motor_center_hole_d_mm"]) for (mx, my) in motor_positions(p)]
    holes += motor_bolt_holes(p)
    for (hx, hy, d) in holes:
        plate = plate.cut(cq.Workplane("XY").center(hx, hy).circle(d / 2.0).extrude(t))

    for sx in (-1, 1):
        slot = (cq.Workplane("XY").center(sx * p["strap_slot_x_mm"], 0)
                .slot2D(strap_slot_l_mm(p), p["strap_slot_w_mm"], angle=90).extrude(t))
        plate = plate.cut(slot)
    return plate


def top_plate(p: dict[str, float] = FRAME) -> cq.Workplane:
    t = p["top_t_mm"]
    plate = _rounded_rect(p["top_l_mm"], p["top_w_mm"], p["top_corner_r_mm"], t)
    for sx in (-1, 1):
        for sy in (-1, 1):
            plate = plate.cut(cq.Workplane("XY").center(sx * p["standoff_x_mm"], sy * p["standoff_y_mm"])
                              .circle(p["standoff_hole_d_mm"] / 2.0).extrude(t))
    return plate


def hex_tube_volume_mm3(af: float, length: float, bore_d: float) -> float:
    hex_area = math.sqrt(3) / 2.0 * af * af
    return (hex_area - math.pi * (bore_d / 2.0) ** 2) * length


def standoff_volume_mm3(p: dict[str, float] = FRAME, thread_d_mm: float = 2.5) -> float:
    """Hex standoff volume (tapped M3 bore, 2.5 mm tap drill)."""
    return hex_tube_volume_mm3(p["standoff_af_mm"], p["standoff_len_mm"], thread_d_mm)


def build(p: dict[str, float] = FRAME) -> dict[str, cq.Workplane]:
    return {"bottom_plate": bottom_plate(p), "top_plate": top_plate(p)}


def _circle_centres(solid: cq.Shape, radius: float, tol: float = 1e-3) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for e in solid.Edges():
        if e.geomType() != "CIRCLE" or abs(e.radius() - radius) > tol:
            continue
        c = e.Center()
        if not any(math.hypot(c.x - x, c.y - y) < 1e-3 for x, y in out):
            out.append((c.x, c.y))
    return out


def measure(parts: dict[str, cq.Workplane], p: dict[str, float] = FRAME) -> dict[str, Any]:
    """Read interface geometry back off the generated solids."""
    bottom = parts["bottom_plate"].val()
    top = parts["top_plate"].val()
    motors = sorted(_circle_centres(bottom, p["motor_center_hole_d_mm"] / 2.0),
                    key=lambda c: math.atan2(c[1], c[0]))
    bolts = _circle_centres(bottom, p["motor_bolt_hole_d_mm"] / 2.0)
    pcd_found: dict[str, int] = {}
    for (bx, by) in bolts:
        mx, my = min(motors, key=lambda m: math.hypot(bx - m[0], by - m[1]))
        d = round(2.0 * math.hypot(bx - mx, by - my), 3)
        pcd_found[f"{d:g}"] = pcd_found.get(f"{d:g}", 0) + 1
    diag = [math.hypot(motors[i][0] - motors[i + 2][0], motors[i][1] - motors[i + 2][1]) for i in (0, 1)]
    adj = [math.hypot(motors[i][0] - motors[(i + 1) % 4][0], motors[i][1] - motors[(i + 1) % 4][1])
           for i in range(4)]
    stack = _circle_centres(bottom, p["stack_hole_d_mm"] / 2.0)
    bb, tb = bottom.BoundingBox(), top.BoundingBox()
    return {
        "motor_centres_mm": [[round(x, 3), round(y, 3)] for x, y in motors],
        "motor_count": len(motors),
        "diagonal_motor_spacing_mm": [round(d, 3) for d in diag],
        "adjacent_motor_spacing_mm": [round(a, 3) for a in adj],
        "motor_bolt_pcd_counts": dict(sorted(pcd_found.items())),
        "m3_hole_count_bottom": len(stack),
        "bottom_volume_mm3": round(bottom.Volume(), 3),
        "top_volume_mm3": round(top.Volume(), 3),
        "bottom_bbox_mm": [round(bb.xlen, 3), round(bb.ylen, 3), round(bb.zlen, 3)],
        "top_bbox_mm": [round(tb.xlen, 3), round(tb.ylen, 3), round(tb.zlen, 3)],
        "bottom_centroid_mm": [round(v, 3) for v in bottom.Center().toTuple()],
        "top_centroid_mm": [round(v, 3) for v in top.Center().toTuple()],
        "bottom_is_valid": bool(bottom.isValid()),
        "top_is_valid": bool(top.isValid()),
        "bottom_solids": len(bottom.Solids()),
        "top_solids": len(top.Solids()),
        "bottom_sharp_concave_corners": _sharp_concave_corners(bottom),
    }


def _ordered_edges(wire: cq.Wire) -> list[tuple[cq.Vector, cq.Vector, cq.Vector]]:
    """(start tangent, end tangent, end point) of each edge in wire order."""
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.TopAbs import TopAbs_REVERSED
    out = []
    ex = BRepTools_WireExplorer(wire.wrapped)
    while ex.More():
        e = cq.Edge(ex.Current())
        t0, t1, end = e.tangentAt(0.0), e.tangentAt(1.0), e.endPoint()
        if ex.Current().Orientation() == TopAbs_REVERSED:
            t0, t1, end = -t1, -t0, e.startPoint()
        out.append((t0, t1, end))
        ex.Next()
    return out


def _sharp_concave_corners(solid: cq.Shape, tol_deg: float = 1.0, eps: float = 0.05) -> int:
    """Count non-tangent concave corners on the plate's outer boundary.

    At each corner, a point a little way along (outgoing - incoming) tangent
    lies inside the material for a convex corner and outside for a concave one.
    """
    face = max(solid.Faces(), key=lambda f: f.Center().z)
    zmid = solid.Center().z
    edges = _ordered_edges(face.outerWire())
    n = 0
    for (_, a, p), (b, _, _) in zip(edges, edges[1:] + edges[:1]):
        dot = max(-1.0, min(1.0, a.x * b.x + a.y * b.y))
        if math.degrees(math.acos(dot)) <= tol_deg:
            continue
        d = cq.Vector(b.x - a.x, b.y - a.y, 0).normalized()
        probe = cq.Vector(p.x + eps * d.x, p.y + eps * d.y, zmid)
        if not solid.isInside(probe):
            n += 1
    return n


def _feature_of(wire: cq.Wire, p: dict[str, float]) -> str:
    """Name an inner wire of the plate face by its position and size."""
    c = wire.Center()
    bb = wire.BoundingBox()
    d = max(bb.xlen, bb.ylen)
    if abs(bb.xlen - bb.ylen) > 0.5:
        return "strap_slot"
    for (mx, my) in motor_positions(p):
        if math.hypot(c.x - mx, c.y - my) < 0.01:
            return "motor_centre_hole"
        if math.hypot(c.x - mx, c.y - my) < p["pad_d_mm"] / 2.0:
            return "motor_bolt_hole"
    if abs(abs(c.x) - p["stack_pitch_mm"] / 2.0) < 0.01:
        return "stack_hole"
    if abs(abs(c.x) - p["standoff_x_mm"]) < 0.01:
        return "standoff_hole"
    return f"hole_{d:.1f}"


def manufacturability(parts: dict[str, cq.Workplane], p: dict[str, float], rules: dict[str, float]) -> dict[str, Any]:
    """Smallest hole and smallest web, read off each plate's cut face.

    ``rules``: ``min_hole_d_mm`` and ``min_web_over_t`` (web >= k x thickness).
    Webs are the shortest distances hole-to-hole and hole-to-outline. Results
    are grouped by feature pair so the README can say exactly which rule fails
    where.
    """
    out: dict[str, Any] = {}
    for name, wp, t in (("bottom_plate", parts["bottom_plate"], p["bottom_t_mm"]),
                        ("top_plate", parts["top_plate"], p["top_t_mm"])):
        face = min(wp.val().Faces(), key=lambda f: f.Center().z)
        inner = face.innerWires()
        outer = face.outerWire()
        names = [_feature_of(w, p) for w in inner]
        min_web = rules["min_web_over_t"] * t
        webs: dict[str, float] = {}
        for i, wi in enumerate(inner):
            k = f"{names[i]}-outline"
            webs[k] = min(webs.get(k, math.inf), wi.distance(outer))
            for j in range(i + 1, len(inner)):
                k = "-".join(sorted((names[i], names[j])))
                webs[k] = min(webs.get(k, math.inf), wi.distance(inner[j]))
        holes: dict[str, float] = {}
        for w, n in zip(inner, names):
            bb = w.BoundingBox()
            holes[n] = min(holes.get(n, math.inf), min(bb.xlen, bb.ylen))
        out[name] = {
            "thickness_mm": t,
            "min_web_rule_mm": round(min_web, 3),
            "min_hole_rule_mm": rules["min_hole_d_mm"],
            "smallest_hole_by_feature_mm": {k: round(v, 3) for k, v in sorted(holes.items())},
            "smallest_web_by_pair_mm": {k: round(v, 3) for k, v in sorted(webs.items())},
            "holes_below_rule": sorted(k for k, v in holes.items() if v < rules["min_hole_d_mm"] - 1e-6),
            "webs_below_rule": sorted(k for k, v in webs.items() if v < min_web - 1e-6),
            "smallest_web_mm": round(min(webs.values()), 3) if webs else None,
        }
    return out


def export(parts: dict[str, cq.Workplane], out_dir) -> dict[str, str]:
    """Write STEP, binary STL and a 2D DXF cut profile for each plate."""
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}
    for name, wp in parts.items():
        shape = wp.val()
        step = out / f"hs3g_{name}.step"
        stl = out / f"hs3g_{name}.stl"
        dxf = out / f"hs3g_{name}.dxf"
        cq.exporters.export(wp, str(step))
        shape.exportStl(str(stl), tolerance=0.02, angularTolerance=0.1, ascii=False, parallel=False)
        cq.exporters.export(cq.Workplane("XY").add(wp.faces("<Z").val()), str(dxf))
        files[f"{name}_step"] = step.name
        files[f"{name}_stl"] = stl.name
        files[f"{name}_dxf"] = dxf.name
    return files
