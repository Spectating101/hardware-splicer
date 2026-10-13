"""Printable case files (STL and OpenSCAD) derived from a device plan's case proposal.

The plan already sizes a two-part box from its modules, a USB cut-out and a display window. This turns those numbers into
files a slicer opens. It is a geometry export: the case has not been printed or test-fitted, nothing here knows how a
particular printer or filament behaves, and nothing changes any authority flag.

Every solid is built from axis-aligned boxes on an integer grid (hundredths of a millimetre), and only the faces between
solid and empty grid cells are written. That makes the surface closed by construction, and ``mesh_report`` checks it again
from the finished triangles rather than trusting the construction.
"""
from __future__ import annotations

import bisect
import hashlib
import io
import json
import struct
import zipfile
from typing import Any

from .device_plan import DevicePlanError, build_device_plan

SCHEMA = "hardware_splicer.device_case_proposal.v1"
BOUNDARY = (
    "Geometry proposal only. The case has not been printed or test-fitted, no printer, material or tolerance was "
    "measured, and nothing here approves building, powering or release."
)
UNITS = 100  # grid units per millimetre

# Choices this export makes beyond the plan. They are typical FDM values, stated so they can be changed, not measured.
LIP_FIT_MM = 0.3      # gap between the lid's lip and the inside of the walls
LIP_HEIGHT_MM = 2.0   # how far the lip reaches down into the base
LIP_WALL_MM = 1.0     # thickness of the lip

Box = tuple[int, int, int, int, int, int]  # x0, x1, y0, y1, z0, z1 in grid units


class DeviceCaseError(DevicePlanError):
    pass


def _u(value: float) -> int:
    return round(float(value) * UNITS)


def _box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Box:
    return (_u(x0), _u(x1), _u(y0), _u(y1), _u(z0), _u(z1))


def _check(box: Box, label: str) -> Box:
    x0, x1, y0, y1, z0, z1 = box
    if not (x0 < x1 and y0 < y1 and z0 < z1):
        raise DeviceCaseError(f"the {label} has no size in this plan")
    return box


def _inside(inner: Box, outer: Box) -> bool:
    return (outer[0] <= inner[0] and inner[1] <= outer[1] and outer[2] <= inner[2] and inner[3] <= outer[3]
            and outer[4] <= inner[4] and inner[5] <= outer[5])


def _geometry(plan: dict[str, Any]) -> dict[str, Any]:
    """The case as boxes in the plan's frame: x along the case, y up, z across, x and z centred and y from the floor."""

    case = plan.get("case")
    if not isinstance(case, dict) or case.get("style") != "two_part_box":
        raise DeviceCaseError("this plan has no two-part case to export")
    wall, outer, inner = case["wall_mm"], case["outer_mm"], case["inner_mm"]
    ox, oy, oz = outer["x"], outer["y"], outer["z"]
    top = case["lid_underside_y"]  # where the base walls end and the lid plate begins
    hx, hz = ox / 2, oz / 2

    def at(x0, x1, y0, y1, z0, z1):  # centred x and z to the grid's own origin at the corner
        return _box(x0 + hx, x1 + hx, y0, y1, z0 + hz, z1 + hz)

    base_add = [
        at(-hx, hx, 0, wall, -hz, hz),                                  # floor
        at(-hx, -hx + wall, wall, top, -hz, hz),                        # -x wall
        at(hx - wall, hx, wall, top, -hz, hz),                          # +x wall
        at(-hx + wall, hx - wall, wall, top, -hz, -hz + wall),          # -z wall
        at(-hx + wall, hx - wall, wall, top, hz - wall, hz),            # +z wall
    ]
    stops = (case.get("board_stops") or {}).get("boxes", [])
    base_add += [at(b["x0"], b["x1"], b["y0"], b["y1"], b["z0"], b["z1"]) for b in stops]
    base_cut: list[Box] = []
    usb = case.get("usb_cutout")
    if usb:
        if usb.get("wall") != "-x":
            raise DeviceCaseError("only a cut-out in the -x wall is supported")
        cut = at(-hx - 1, -hx + wall + 1, usb["y"] - usb["height_mm"] / 2, usb["y"] + usb["height_mm"] / 2,
                 usb["z"] - usb["width_mm"] / 2, usb["z"] + usb["width_mm"] / 2)
        if cut[2] < _u(wall) or cut[3] > _u(top) or cut[4] < _u(wall) or cut[5] > _u(oz - wall):
            raise DeviceCaseError("the USB cut-out would fall outside its wall")
        base_cut.append(cut)

    lip_out = at(-hx + wall + LIP_FIT_MM, hx - wall - LIP_FIT_MM, top - LIP_HEIGHT_MM, top, -hz + wall + LIP_FIT_MM, hz - wall - LIP_FIT_MM)
    lip_in = at(-hx + wall + LIP_FIT_MM + LIP_WALL_MM, hx - wall - LIP_FIT_MM - LIP_WALL_MM, top - LIP_HEIGHT_MM - 1, top,
                -hz + wall + LIP_FIT_MM + LIP_WALL_MM, hz - wall - LIP_FIT_MM - LIP_WALL_MM)
    _check(lip_out, "lid lip")
    _check(lip_in, "lid lip opening")
    lid_add = [at(-hx, hx, top, oy, -hz, hz), lip_out]
    lid_cut = [lip_in]
    window = case.get("window")
    if window:
        win = at(window["x"] - window["width_mm"] / 2, window["x"] + window["width_mm"] / 2, top - 1, oy + 1,
                 window["z"] - window["depth_mm"] / 2, window["z"] + window["depth_mm"] / 2)
        if not _inside((win[0], win[1], lip_in[2], lip_in[3], win[4], win[5]), lip_in):
            raise DeviceCaseError("the display window would overlap the lid's lip: the display is too close to a wall for this export")
        lid_cut.append(win)
    for label, boxes in (("base", base_add), ("lid", lid_add)):
        for box in boxes:
            _check(box, f"{label} part")
    return {"outer": (_u(ox), _u(oy), _u(oz)), "top": _u(top), "base": (base_add, base_cut), "lid": (lid_add, lid_cut)}


def _map(box: Box, fn) -> Box:
    """Apply a proper rotation (given on corners) to a box and re-order its bounds."""

    a = fn(box[0], box[2], box[4])
    b = fn(box[1], box[3], box[5])
    return (min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]), min(a[2], b[2]), max(a[2], b[2]))


def _print_frames(geometry: dict[str, Any]):
    """Z-up print orientation. Both are proper rotations, so neither part is mirrored.

    The base stands on its floor. The lid is turned over so its plate is on the bed and the lip points up.
    """

    ox, oy, oz = geometry["outer"]
    return (
        lambda x, y, z: (x, oz - z, y),   # base
        lambda x, y, z: (x, z, oy - y),   # lid
    )


def _solid(adds: list[Box], cuts: list[Box]) -> list[tuple[tuple[int, int, int], ...]]:
    xs = sorted({v for b in adds + cuts for v in b[0:2]})
    ys = sorted({v for b in adds + cuts for v in b[2:4]})
    zs = sorted({v for b in adds + cuts for v in b[4:6]})

    def cells(box: Box):
        i0, i1 = bisect.bisect_left(xs, box[0]), bisect.bisect_left(xs, box[1])
        j0, j1 = bisect.bisect_left(ys, box[2]), bisect.bisect_left(ys, box[3])
        k0, k1 = bisect.bisect_left(zs, box[4]), bisect.bisect_left(zs, box[5])
        return ((i, j, k) for i in range(i0, i1) for j in range(j0, j1) for k in range(k0, k1))

    solid = {c for b in adds for c in cells(b)} - {c for b in cuts for c in cells(b)}
    triangles: list[tuple[tuple[int, int, int], ...]] = []

    def quad(corners, outward):
        a, b, c, d = corners
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if sum(n * o for n, o in zip(normal, outward)) < 0:
            b, d = d, b
        triangles.append((a, b, c))
        triangles.append((a, c, d))

    for (i, j, k) in solid:
        x0, x1, y0, y1, z0, z1 = xs[i], xs[i + 1], ys[j], ys[j + 1], zs[k], zs[k + 1]
        for axis, step in ((0, -1), (0, 1), (1, -1), (1, 1), (2, -1), (2, 1)):
            neighbour = [i, j, k]
            neighbour[axis] += step
            if tuple(neighbour) in solid:
                continue
            fixed = (x0, x1, y0, y1, z0, z1)[2 * axis + (0 if step < 0 else 1)]
            lo = [(x0, y0, z0), (x1, y1, z1)]
            others = [a for a in range(3) if a != axis]
            p, q = others
            ranges = {a: (lo[0][a], lo[1][a]) for a in range(3)}

            def corner(vp, vq):
                point = [0, 0, 0]
                point[axis], point[p], point[q] = fixed, vp, vq
                return tuple(point)

            outward = [0, 0, 0]
            outward[axis] = step
            quad([corner(ranges[p][0], ranges[q][0]), corner(ranges[p][1], ranges[q][0]),
                  corner(ranges[p][1], ranges[q][1]), corner(ranges[p][0], ranges[q][1])], tuple(outward))
    triangles.sort()
    return triangles


def mesh_report(triangles) -> dict[str, Any]:
    """Measure a finished mesh rather than trusting how it was built."""

    edges: dict[tuple, int] = {}
    volume6 = 0
    low = [None, None, None]
    high = [None, None, None]
    for tri in triangles:
        for index in range(3):
            a, b = tri[index], tri[(index + 1) % 3]
            edges[(a, b)] = edges.get((a, b), 0) + 1
        a, b, c = tri
        volume6 += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]))
        for vertex in tri:
            for axis in range(3):
                low[axis] = vertex[axis] if low[axis] is None else min(low[axis], vertex[axis])
                high[axis] = vertex[axis] if high[axis] is None else max(high[axis], vertex[axis])
    closed = bool(edges) and all(count == 1 and edges.get((b, a)) == 1 for (a, b), count in edges.items())
    return {
        "triangles": len(triangles),
        "closed_manifold": closed,
        "volume_mm3": round(volume6 / 6 / UNITS ** 3, 2),
        "size_mm": [round((high[a] - low[a]) / UNITS, 2) for a in range(3)] if triangles else [0, 0, 0],
    }


def _stl(triangles, name: str) -> bytes:
    out = io.BytesIO()
    header = f"hardware-splicer case proposal: {name}".encode()[:79]
    out.write(header.ljust(80, b" "))
    out.write(struct.pack("<I", len(triangles)))
    for a, b, c in triangles:
        u = [(b[i] - a[i]) / UNITS for i in range(3)]
        v = [(c[i] - a[i]) / UNITS for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        length = sum(x * x for x in n) ** 0.5 or 1.0
        out.write(struct.pack("<3f", *(x / length for x in n)))
        for vertex in (a, b, c):
            out.write(struct.pack("<3f", *(x / UNITS for x in vertex)))
        out.write(b"\x00\x00")
    return out.getvalue()


def _scad(name: str, adds: list[Box], cuts: list[Box]) -> str:
    def cube(box: Box) -> str:
        x0, x1, y0, y1, z0, z1 = (v / UNITS for v in box)
        return f"translate([{x0:g}, {y0:g}, {z0:g}]) cube([{x1 - x0:g}, {y1 - y0:g}, {z1 - z0:g}]);"

    body = "\n".join("    " + cube(b) for b in adds)
    holes = "\n".join("    " + cube(b) for b in cuts)
    return (f"// {name}: a hardware-splicer case proposal in print orientation (z up), millimetres.\n"
            "// Not printed or test-fitted. Edit the numbers; every box is one wall, lip or opening.\n"
            f"module {name}() {{\n  difference() {{\n    union() {{\n{body}\n    }}\n    union() {{\n{holes}\n    }}\n  }}\n}}\n{name}();\n")


def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode()


def build_device_case(spec: Any) -> tuple[dict[str, Any], bytes]:
    """Recompute the plan from the spec and export its case; never trust a caller's plan or findings."""

    plan = build_device_plan(spec)
    blockers = [f for f in plan["findings"] if f["severity"] == "error"]
    if blockers:
        raise DevicePlanError("Resolve the plan's errors before exporting a case: " + ", ".join(sorted({f["rule"] for f in blockers})))
    geometry = _geometry(plan)
    frame_base, frame_lid = _print_frames(geometry)
    parts: dict[str, tuple[list[Box], list[Box]]] = {}
    for name, frame in (("case_base", frame_base), ("case_lid", frame_lid)):
        adds, cuts = geometry["base" if name == "case_base" else "lid"]
        parts[name] = ([_map(b, frame) for b in adds], [_map(b, frame) for b in cuts])
    files: dict[str, bytes] = {}
    reports: dict[str, Any] = {}
    for name, (adds, cuts) in parts.items():
        triangles = _solid(adds, cuts)
        report = mesh_report(triangles)
        if not report["closed_manifold"] or report["volume_mm3"] <= 0:
            raise DeviceCaseError(f"the {name} mesh is not a closed solid; nothing was exported")
        reports[name] = report
        files[f"{name}.stl"] = _stl(triangles, name)
        files[f"{name}.scad"] = _scad(name, adds, cuts).encode()
    case = plan["case"]
    readme = (
        "# Case proposal\n\n" + BOUNDARY + "\n\n"
        f"Outer size {case['outer_mm']['x']} x {case['outer_mm']['z']} x {case['outer_mm']['y']} mm (length x width x height), wall {case['wall_mm']} mm, "
        f"clearance {case['clearance_mm']} mm. Both parts are in print orientation: the base on its floor, the lid turned over with its plate on the bed.\n\n"
        "What this export chose beyond the plan:\n"
        f"- The lid has a lip, {LIP_HEIGHT_MM} mm tall and {LIP_WALL_MM} mm thick, {LIP_FIT_MM} mm inside the walls. It holds the lid in place by friction.\n"
        "- There are no screw bosses, snap hooks, board standoffs, vents or cable strain relief. The plan assumes the board rests on its own header pins.\n"
        "- The USB cut-out and display window come from the plan; its notes say to measure your module before printing.\n"
        "- Thermal behaviour has not been assessed. Do not enclose a part that gets hot without checking.\n\n"
        "`.scad` files hold the same boxes as editable OpenSCAD. Check every fit on a test print before trusting a dimension.\n"
    ).encode()
    files["README.md"] = readme
    plan_bytes = _json(plan)
    files["DEVICE_PLAN.json"] = plan_bytes
    metadata = {
        "schema_version": SCHEMA,
        "claim_boundary": BOUNDARY,
        "status": "GEOMETRY_PROPOSAL",
        "printed": False,
        "test_fitted": False,
        "physical_correctness": "UNPROVEN",
        "firmware_authorized": False,
        "power_on_authorized": False,
        "units": "mm",
        "assumptions": {"lip_fit_mm": LIP_FIT_MM, "lip_height_mm": LIP_HEIGHT_MM, "lip_wall_mm": LIP_WALL_MM},
        "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "meshes": reports,
        "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)} for name, data in sorted(files.items())},
    }
    files["CASE_PROPOSAL.json"] = _json(metadata)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return metadata, output.getvalue()
