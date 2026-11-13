"""Parametric HS-3G carbon frame in CadQuery.

Two flat plates, both cut from carbon sheet:

* a 3.0 mm unibody bottom plate: a 60 x 32 mm body, four arms at 45 degrees and
  round motor pads carrying both 9 mm and 12 mm M2 bolt circles (the F1404's
  published drawing could not be read, so the frame accepts either pattern);
* a 1.5 mm top plate on four M3 x 30 mm standoffs that carries the GNSS/compass
  module well away from the ESC.

The battery hangs under the bottom plate on a strap through two slots, so
nothing heavy sits in the prop plane and the centre of gravity stays low.

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
    "top_t_mm": 1.5,
    "body_l_mm": 60.0,              # along x (forward)
    "body_w_mm": 32.0,
    "body_corner_r_mm": 4.0,
    "arm_w_mm": 12.0,
    "pad_d_mm": 19.0,
    "motor_center_hole_d_mm": 5.5,
    "motor_bolt_hole_d_mm": 2.2,    # M2 clearance
    "motor_pcd_a_mm": 9.0,
    "motor_pcd_b_mm": 12.0,
    "stack_pitch_mm": 20.0,
    "stack_hole_d_mm": 3.2,         # M3 clearance for the stack's grommets
    "standoff_x_mm": 24.0,
    "standoff_y_mm": 10.0,
    "standoff_hole_d_mm": 3.2,
    "standoff_len_mm": 30.0,
    "standoff_af_mm": 5.0,          # hex across flats
    "top_l_mm": 56.0,
    "top_w_mm": 27.0,
    "top_corner_r_mm": 3.0,
    "strap_slot_x_mm": 17.0,
    "strap_slot_l_mm": 20.0,
    "strap_slot_w_mm": 3.0,
}

ARM_ANGLES_DEG = (45.0, 135.0, 225.0, 315.0)


def motor_positions(p: dict[str, float] = FRAME) -> list[tuple[float, float]]:
    r = p["wheelbase_mm"] / 2.0
    return [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a in ARM_ANGLES_DEG]


def _rounded_rect(l: float, w: float, r: float, t: float) -> cq.Workplane:
    return cq.Workplane("XY").rect(l, w).extrude(t).edges("|Z").fillet(r)


def bottom_plate(p: dict[str, float] = FRAME) -> cq.Workplane:
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

    holes: list[tuple[float, float, float]] = []
    s = p["stack_pitch_mm"] / 2.0
    holes += [(sx * s, sy * s, p["stack_hole_d_mm"]) for sx in (-1, 1) for sy in (-1, 1)]
    holes += [(sx * p["standoff_x_mm"], sy * p["standoff_y_mm"], p["standoff_hole_d_mm"])
              for sx in (-1, 1) for sy in (-1, 1)]
    for ang, (mx, my) in zip(ARM_ANGLES_DEG, motor_positions(p)):
        holes.append((mx, my, p["motor_center_hole_d_mm"]))
        for k in range(4):
            a = math.radians(ang + 45.0 + 90.0 * k)
            rr = p["motor_pcd_a_mm"] / 2.0
            holes.append((mx + rr * math.cos(a), my + rr * math.sin(a), p["motor_bolt_hole_d_mm"]))
            b = math.radians(ang + 90.0 * k)
            rr = p["motor_pcd_b_mm"] / 2.0
            holes.append((mx + rr * math.cos(b), my + rr * math.sin(b), p["motor_bolt_hole_d_mm"]))
    for (hx, hy, d) in holes:
        plate = plate.cut(cq.Workplane("XY").center(hx, hy).circle(d / 2.0).extrude(t))

    for sx in (-1, 1):
        slot = (cq.Workplane("XY").center(sx * p["strap_slot_x_mm"], 0)
                .slot2D(p["strap_slot_l_mm"], p["strap_slot_w_mm"], angle=90).extrude(t))
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


def standoff_volume_mm3(p: dict[str, float] = FRAME, thread_d_mm: float = 2.5) -> float:
    """Hex standoff volume (tapped M3 bore, 2.5 mm tap drill)."""
    af = p["standoff_af_mm"]
    hex_area = math.sqrt(3) / 2.0 * af * af
    return (hex_area - math.pi * (thread_d_mm / 2.0) ** 2) * p["standoff_len_mm"]


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
    }


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
