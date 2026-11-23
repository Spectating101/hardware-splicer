"""Fielddeck 5c: a proposed compact layout of the 5-inch revision, authored in CadQuery.

The 5-inch case is 64 mm tall because the 26 mm power bank sits under the 22 mm keyboard, while
the rear bay above the Pi is mostly empty (docs/status/generated/device-design-review-20261123.md).
This revision moves the bank into the rear-right bay and takes an 11.6 mm band out of the case:

* the trays lose an 11.6 mm band, so the walls, keyboard support columns (top 38 -> 26.4; band z 26.3-37.9),
  display posts and face-fastener bosses all shorten together; exhaust slots and the rear I/O
  window are re-cut at their original sizes;
* the old bank nest under the keyboard is removed and its strap slots filled; an open, removable
  nest with the same 1 mm allowance and strap slots is authored around the new bank position;
* the keyboard, display, display spacers, fan, fan guard and faces drop 11.6 mm; the fan duct's
  sleeve loses the band z 30-41.6 so its flange still meets the fan.

Everything else (Pi, its connectors and standoffs, the display aperture, seams, seam plates and
feet) is the 5-inch geometry unchanged. A proposal: nothing has been printed or assembled.

Run with the native CAD Python:  python compact/build.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT / "display_swap"))  # for its `assess` import
_spec = importlib.util.spec_from_file_location("fielddeck_display_swap_build", PROJECT / "display_swap" / "build.py")
swap = importlib.util.module_from_spec(_spec)  # the 5-inch revision's own build
_spec.loader.exec_module(swap)

DROP = 11.6
TRAY_BAND = (26.3, 37.9)  # clear of the keyboard columns' top face at z 38
DUCT_BAND = (30.0, 41.6)
# Bank (Anker A1259, 52.3 x 104 x 26) in the rear-right bay, 1 mm above the floor as before.
BANK_MIN = (217.0, 171.0, 4.0)
BANK_SIZE = (52.3, 104.0, 26.0)
LOWERED = ("keyboard_nominal_envelope", "fan_envelope", "fan_guard", swap.NEW_DISPLAY)
PRINTABLE_PREFIXES = ("tray_", "face_", "seam_plate_", "foot_", "fan_duct", "fan_guard", "display_spacer_")


def box(x, y, z, w, d, h):
    return cq.Solid.makeBox(w, d, h, cq.Vector(x, y, z))


def remove_band(shape, lo, hi):
    """Take the horizontal band lo..hi out of a solid and close the gap from above."""
    big, eps = 2000, 0.01
    below = shape.intersect(box(-big, -big, -big, 2 * big, 2 * big, big + lo))
    # The upper piece keeps a 0.01 mm sliver of the band, so the two pieces overlap rather than
    # meet face to face (a face-to-face fuse leaves an invalid compound). Every feature crossing
    # the band is prismatic there, so the sliver duplicates material already in the lower piece.
    above = shape.intersect(box(-big, -big, hi - eps, 2 * big, 2 * big, big))
    if not above.Solids():
        return below.clean()
    if not below.Solids():
        return above.translate((0, 0, -(hi - lo))).clean()
    fused = below.fuse(above.translate((0, 0, -(hi - lo))))
    cleaned = fused.clean()  # clean() can break the merged faces; keep it only when it stays valid
    return cleaned if cleaned.isValid() else fused


def round_rect(cx, cy, z, w, d, h, r):
    return cq.Workplane("XY").box(w, d, h).edges("|Z").fillet(r).translate((cx, cy, z + h / 2)).val()


def bank_nest():
    """Open nest, 1 mm radial allowance, 8 mm walls: the 5-inch nest moved with the bank."""
    x0, y0, _ = BANK_MIN
    w, d, _ = BANK_SIZE
    left, right = x0 - 3, x0 + w + 1
    front, rear = y0 - 3, y0 + d + 1
    walls = [box(left, front, 3, 2, rear + 2 - front, 8), box(right, front, 3, 2, rear + 2 - front, 8),
             box(left, front, 3, right + 2 - left, 2, 8), box(left, rear, 3, right + 2 - left, 2, 8)]
    shape = walls[0]
    for wall in walls[1:]:
        shape = shape.fuse(wall)
    # Two 20 mm straps through floor slots, outside the walls, clear of the display posts.
    slots = [box(x - 1.5, y - 11, -1, 3, 22, 6) for x, y in itertools.product((left - 1.5, right + 3.5), (y0 + 40, y0 + 87))]
    return shape.clean(), slots


def compact(parts):
    out = dict(parts)
    # Old nest (under the keyboard): remove its walls, keep the keyboard columns, fill strap slots.
    old_walls = box(13, 22, 3, 2, 110, 8).fuse(box(69.3, 22, 3, 2, 110, 8)).fuse(
        box(13, 22, 3, 58.3, 2, 8)).fuse(box(13, 130, 3, 58.3, 2, 8))
    for x, y in itertools.product((28, 110), (20, 135)):
        old_walls = old_walls.cut(box(x - 5, y - 5, 3, 10, 10, 35))
    tray = out["tray_front_left"].cut(old_walls)
    for x, y in itertools.product((10, 74), (51, 105)):
        tray = tray.fuse(box(x - 1.5, y - 11, 0, 3, 22, 3))
    out["tray_front_left"] = tray.clean()

    nest, slots = bank_nest()
    tray = out["tray_rear_right"].fuse(nest)
    for slot in slots:
        tray = tray.cut(slot)
    out["tray_rear_right"] = tray.clean()

    for name in [n for n in out if n.startswith("tray_")]:
        out[name] = remove_band(out[name], *TRAY_BAND)
    # Re-cut the openings the band crossed, at their 5-inch sizes.
    for y in range(181, 262, 10):
        out["tray_rear_right"] = out["tray_rear_right"].cut(box(306, y, 14, 6, 7.5, 24))
    out["tray_rear_left"] = out["tray_rear_left"].cut(box(3, 281, 5, 73, 6, 25))
    out["fan_duct"] = remove_band(out["fan_duct"], *DUCT_BAND)

    for name in list(out):
        if name in LOWERED or name.startswith("face_") or name.startswith("display_spacer_"):
            out[name] = out[name].translate((0, 0, -DROP))
    x0, y0, z0 = BANK_MIN
    w, d, h = BANK_SIZE
    out["power_bank_nominal_envelope"] = round_rect(x0 + w / 2, y0 + d / 2, z0, w, d, h, 6)
    for name, shape in out.items():
        swap.require(shape.isValid() and shape.Solids(), f"{name} is not a valid solid")
    return out


def measure(parts):
    """Real solid overlaps between every pair (bounding boxes first), size, printable volume."""
    names = sorted(parts)
    bounds = {name: swap.bounds(parts[name]) for name in names}
    overlaps = []
    for a, b in itertools.combinations(names, 2):
        ba, bb = bounds[a], bounds[b]
        if any(ba[i] > bb[i + 3] or bb[i] > ba[i + 3] for i in range(3)):
            continue
        if a.startswith("pi4_") and b.startswith("pi4_"):
            continue  # seated sub-parts of one purchased module
        volume = swap.overlap(parts[a], parts[b])
        if volume > swap.COMMON_LIMIT:
            overlaps.append({"a": a, "b": b, "overlap_mm3": round(volume, 3)})
    lo = np.min([bounds[n][:3] for n in names], 0)
    hi = np.max([bounds[n][3:] for n in names], 0)
    case = [bounds[n] for n in names if n.startswith("tray_") or n.startswith("face_")]
    printable = {n: round(swap.shape_volume(parts[n]), 1) for n in names if n.startswith(PRINTABLE_PREFIXES)}
    return {"size_mm": [round(float(v), 2) for v in hi - lo],
            "case_height_mm": round(max(b[5] for b in case) - min(b[2] for b in case), 2),
            "overlaps": overlaps, "printable_volume_mm3": printable,
            "printable_volume_total_mm3": round(sum(printable.values()), 1)}


def export(parts, cad):
    cad.mkdir(parents=True, exist_ok=True)
    assembly = cq.Assembly(name="Fielddeck_5c_compact")
    scene = trimesh.Scene()
    for name, shape in parts.items():
        color = ((.92, .51, .22, 1) if name.startswith("face_") else
                 (.10, .13, .15, 1) if name == swap.NEW_DISPLAY else (.34, .42, .48, 1))
        assembly.add(shape, name=name, color=cq.Color(*color))
        vertices, faces = shape.copy().tessellate(.25, .2)
        mesh = trimesh.Trimesh([[v.x, v.y, v.z] for v in vertices], faces, process=True)
        mesh.visual.face_colors = np.array(color) * 255
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    assembly.save(str(cad / "FIELDDECK_5C.step"))
    scene.export(str(cad / "FIELDDECK_5C.glb"))
    printed = cad / "print"
    printed.mkdir(exist_ok=True)
    for name in sorted(n for n in parts if n.startswith(("tray_", "fan_duct"))):
        local = parts[name].translate(tuple(-v for v in swap.bounds(parts[name])[:3]))
        cq.exporters.export(local, str(printed / f"{name}.step"))
        cq.exporters.export(local, str(printed / f"{name}.stl"), tolerance=.08, angularTolerance=.12)


def main():
    five, *_ = swap.prepare_assembly(swap.DEFAULT_BASE)
    parts = compact(five)
    before, after = measure(five), measure(parts)
    swap.require(not after["overlaps"], f"Compact layout has solid overlaps: {after['overlaps']}")
    export(parts, ROOT / "cad")
    geometry = {
        "status": "proposed_layout_nominal_geometry_checks_passed",
        "revision": "5c", "based_on": "5", "drop_mm": DROP, "tray_band_z_mm": TRAY_BAND, "duct_band_z_mm": DUCT_BAND,
        "power_bank_min_mm": BANK_MIN, "power_bank_size_mm": BANK_SIZE,
        "measured": {"5": before, "5c": after},
        "physical_fit_verified": False,
        "blockers": [
            {"reason": "power bank port, button and cable access from the rear-right bay not checked", "part_id": "power-bank-nominal-envelope"},
            {"reason": "heat from the bank beside the Pi and fan intake not checked", "part_id": "power-bank-nominal-envelope"},
            {"reason": "centre of mass moved rearward with the bank; stability on the feet not checked", "part_id": "power-bank-nominal-envelope"},
            {"reason": "printed bank nest and strap retention in the new position untested", "part_id": "tray-rear-right"},
            {"reason": "keyboard and fan cable lengths for the lowered layout not checked", "part_id": "keyboard-nominal-envelope"},
        ],
        "sources": {"build_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "glb_sha256": hashlib.sha256((ROOT / "cad/FIELDDECK_5C.glb").read_bytes()).hexdigest()},
    }
    (ROOT / "geometry.json").write_text(json.dumps(geometry, indent=2) + "\n")
    print(json.dumps({"5": {k: before[k] for k in ("size_mm", "case_height_mm", "printable_volume_total_mm3")},
                      "5c": {k: after[k] for k in ("size_mm", "case_height_mm", "printable_volume_total_mm3")},
                      "overlaps_5c": after["overlaps"], "overlaps_5": before["overlaps"]}, indent=1))


if __name__ == "__main__":
    main()
