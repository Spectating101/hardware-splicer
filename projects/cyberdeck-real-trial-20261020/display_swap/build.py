"""Build a source-backed Fielddeck 5 digital revision from retained Fielddeck 7 CAD."""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import zipfile

import cadquery as cq
import numpy as np
import trimesh
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from assess import assess_interfaces

ROOT = Path(__file__).resolve().parent
DEFAULT_BASE = ROOT.parent / "digital_v1"
DISPLAY = "touch_display_2_manufacturer"
NEW_DISPLAY = "touch_display_2_5inch_sc1975"
CHANGED = {"face_rear_left", "face_rear_right", "tray_rear_left", "tray_rear_right"}
CENTRE = (155, 210)
FRONT_Z = 62
APERTURE = (114, 65.5)
LINEAR_TOLERANCE = 0.005
COMMON_LIMIT = 0.05


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def vendor_display(evidence):
    archive = ROOT / "sources/vendor5.zip"
    metadata = evidence["vendor_step"]
    require(sha(archive) == metadata["archive_sha256"], "Vendor archive hash differs.")
    with zipfile.ZipFile(archive) as package, TemporaryDirectory(prefix="hs-display-") as folder:
        files = {}
        for suffix, key in ((".step", "step_sha256"), (".txt", "license_sha256")):
            entries = [entry for entry in package.infolist() if entry.filename.lower().endswith(suffix)]
            require(len(entries) == 1 and entries[0].file_size < 2_000_000, "Unexpected vendor archive inventory.")
            data = package.read(entries[0])
            require(hashlib.sha256(data).hexdigest() == metadata[key], f"Vendor {suffix} hash differs.")
            files[suffix] = data
        source = Path(folder) / "display5.step"
        source.write_bytes(files[".step"])
        display, mount = place_display(source, evidence)
    return display, mount, files[".txt"]


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    return box.Get()


def box(x, y, z, width, depth, height):
    return cq.Solid.makeBox(width, depth, height, cq.Vector(x, y, z))


def cylinder(x, y, z, radius, height):
    return cq.Solid.makeCylinder(radius, height, cq.Vector(x, y, z))


def centred_box(x, y, z, width, depth, height):
    return box(x - width / 2, y - depth / 2, z, width, depth, height)


def shape_volume(shape):
    return sum(solid.Volume() for solid in shape.Solids())


def overlap(first, second):
    a, b = bounds(first), bounds(second)
    if any(a[i] >= b[i + 3] - 1e-7 or b[i] >= a[i + 3] - 1e-7 for i in range(3)):
        return 0.0
    return shape_volume(first.intersect(second))


def matches(first, second):
    return (
        all(abs(a - b) < LINEAR_TOLERANCE for a, b in zip(bounds(first), bounds(second)))
        and abs(shape_volume(first) - shape_volume(second)) < 0.1
    )


def same_vendor_centroid(first, second):
    # A vendor screen sub-solid produces an empty Boolean intersection across
    # the STEP round trip. Its independent bounds, volume and centroid persist.
    a, b = first.Center().toTuple(), second.Center().toTuple()
    return math.dist(a, b) < LINEAR_TOLERANCE


def baseline_parts(base, evidence):
    for name, digest in evidence["baseline"]["files"].items():
        require(sha(base / name) == digest, f"Unexpected baseline revision file: {name}")
    geometry = read(base / "cad/geometry_report.json")
    verification = read(base / "analysis/verification.json")
    require(verification["status"] == "digital_geometry_checks_passed", "Baseline verification missing.")
    require(not geometry["collision_findings"], "Baseline contains unresolved CAD intersections.")
    assembly = cq.importers.importStep(str(base / "cad/FIELDDECK_7.step")).val()
    unmatched = list(assembly.Solids())
    cached_bounds = {id(body): bounds(body) for body in unmatched}
    parts = {}
    for row in geometry["parts"]:
        bb = row["bounds_mm"]
        if row["solids"] == 1:
            selected = [body for body in unmatched if all(abs(a - b) < LINEAR_TOLERANCE
                        for a, b in zip(cached_bounds[id(body)], bb))]
        else:
            selected = [solid for solid in unmatched if all(
                cached_bounds[id(solid)][i] >= bb[i] - LINEAR_TOLERANCE
                and cached_bounds[id(solid)][i + 3] <= bb[i + 3] + LINEAR_TOLERANCE
                for i in range(3))]
        require(len(selected) == row["solids"], f"Wrong baseline solid inventory for {row['name']}")
        part = selected[0] if len(selected) == 1 else cq.Compound.makeCompound(selected)
        if row["name"] != DISPLAY:
            require(abs(shape_volume(part) - row["volume_mm3"]) < 0.1,
                    f"Wrong baseline solid volume for {row['name']}")
        parts[row["name"]] = part
        for solid in selected:
            unmatched.remove(solid)
    require(not unmatched, "Baseline STEP contains unaccounted solids.")
    return parts, geometry


def place_display(source, evidence):
    native = cq.importers.importStep(str(source)).val()
    require(native.isValid(), "Vendor display STEP is invalid.")
    glass = max(native.Solids(), key=lambda solid: (bounds(solid)[3] - bounds(solid)[0]) *
                                                   (bounds(solid)[4] - bounds(solid)[1]))
    x0, y0, _, x1, y1, z1 = bounds(glass)
    brief = evidence["product_brief"]
    require(all(abs(a - b) < 0.02 for a, b in zip((y1 - y0, x1 - x0), brief["landscape_glass_mm"])),
            "Vendor glass outline differs from the product drawing.")
    tx, ty, tz = CENTRE[0] + (y0 + y1) / 2, CENTRE[1] - (x0 + x1) / 2, FRONT_Z - z1
    axes, starts = set(), []
    # The archive includes open reference surface features for a second
    # (Pi board) attachment pattern. The case mounts use closed solid lugs.
    for face in (face for solid in native.Solids() for face in solid.Faces()):
        if face.geomType() != "CYLINDER":
            continue
        bore = face._geomAdaptor().Cylinder()
        direction, location = bore.Axis().Direction(), bore.Location()
        if abs(bore.Radius() - 1.25) < .001 and abs(abs(direction.Z()) - 1) < 1e-7:
            axes.add((round(tx - location.Y(), 3), round(ty + location.X(), 3)))
            starts.append(bounds(face)[2] + tz)
    require(len(axes) == 4, "Expected four distinct manufacturer M2.5 mounting axes.")
    xs, ys = (sorted({row[i] for row in axes}) for i in (0, 1))
    pitch = [xs[-1] - xs[0], ys[-1] - ys[0]]
    require(all(abs(x - y) < .01 for x, y in zip(pitch, brief["landscape_mount_pitch_mm"])),
            "STEP bore pitch differs from the product drawing.")
    model_seat = round(min(starts), 3)
    drawing_seat = FRONT_Z - brief["nominal_lug_depth_mm"]
    require(.1 < model_seat - drawing_seat < 10, "Unsupported drawing/STEP mount depth difference.")
    return native.rotate((0, 0, 0), (0, 0, 1), 90).translate((tx, ty, tz)), {
        "glass_mm": [round(y1 - y0, 3), round(x1 - x0, 3)],
        "pose_mm": [round(v, 4) for v in (tx, ty, tz)],
        "mount_xy_mm": sorted(axes), "mount_pitch_mm": [round(v, 3) for v in pitch],
        "step_bore_entrance_z_mm": model_seat, "drawing_support_seat_z_mm": round(drawing_seat, 3),
        "spacer_height_mm": round(model_seat - drawing_seat, 3),
        "step_full_reference_envelope_depth_mm": round(z1 - bounds(native)[2], 3),
        "aperture_mm": APERTURE,
    }


def revise_panels(parts, geometry, mount):
    changed = {}
    for side in ("left", "right"):
        name = "face_rear_" + side
        panel = parts[name]
        x0, _, _, x1, _, _ = bounds(panel)
        # Fill only the old display cutout region. Existing face, fan and
        # fastener geometry outside the screen region stays intact.
        refill = centred_box(*CENTRE, 61, 191, 122, 3).intersect(
            box(x0, 148, 61, x1 - x0, 124, 3))
        new_pocket = centred_box(*CENTRE, 60.98, *[v + 1.2 for v in mount["glass_mm"]], 1.37)
        opening = centred_box(*CENTRE, 62.35, *APERTURE, 2)
        changed[name] = panel.fuse(refill).cut(new_pocket).cut(opening).clean()

        name = "tray_rear_" + side
        tray = parts[name]
        inside = lambda x: (x < CENTRE[0]) == (side == "left")
        for x, y in geometry["display_case_mount_centres_mm"]:
            if inside(x):
                tray = tray.cut(cylinder(x, y, 3, 5.001, 60))
                tray = tray.fuse(cylinder(x, y, 0, 3.05, 3))
        seat = mount["drawing_support_seat_z_mm"]
        for x, y in mount["mount_xy_mm"]:
            if inside(x):
                tray = tray.fuse(cylinder(x, y, 2.95, 5, seat - 2.95))
                tray = tray.cut(cylinder(x, y, -1, 3, seat - 2))
                tray = tray.cut(cylinder(x, y, seat - 3.05, 1.4, 4))
        changed[name] = tray.clean()

    z = mount["drawing_support_seat_z_mm"]
    height = mount["spacer_height_mm"]
    for index, (x, y) in enumerate(mount["mount_xy_mm"], 1):
        spacer = cylinder(x, y, z, 3.5, height).cut(cylinder(x, y, z - .1, 1.4, height + .2))
        changed[f"display_spacer_{index}"] = spacer
    for name, shape in changed.items():
        require(shape.isValid() and len(shape.Solids()) == 1, f"{name} is not one valid solid.")
    return changed


def verify_geometry(parts, mount):
    new_parts = CHANGED | {name for name in parts if name.startswith("display_spacer_")} | {NEW_DISPLAY}
    for a, b in itertools.combinations(parts, 2):
        if a in new_parts or b in new_parts:
            interference = overlap(parts[a], parts[b])
            require(interference <= COMMON_LIMIT, f"{a} collides with {b} by {interference:.3f} mm³.")
    tray = cq.Compound.makeCompound([shape for name, shape in parts.items() if name.startswith("tray_")])
    bezel = cq.Compound.makeCompound([parts["face_rear_left"], parts["face_rear_right"]])
    aperture = centred_box(*CENTRE, 62.3, *APERTURE, 2)
    require(overlap(bezel, aperture) < COMMON_LIMIT, "Bezel obstructs the requested viewing aperture.")
    z = mount["drawing_support_seat_z_mm"]
    for index, (x, y) in enumerate(mount["mount_xy_mm"], 1):
        head_and_tool = cylinder(x, y, -.5, 2.8, z - 2.55)
        shank = cylinder(x, y, z - 3.04, 1.26, mount["step_bore_entrance_z_mm"] - z + 3.04)
        require(overlap(tray, head_and_tool) < .01, "An underside driver path is blocked.")
        seat = cylinder(x, y, z - .1, 3.45, .09).cut(cylinder(x, y, z - .11, 1.45, .11))
        require(overlap(tray, seat) >= .99 * shape_volume(seat), "An upper support seat is missing.")
        require(overlap(tray, shank) < .01 and overlap(parts[f"display_spacer_{index}"], shank) < .01,
                "A screw clearance bore misses the mount axis.")
    # Only the middle run of a possible FFC path has sufficient source/model
    # coverage. The two plug exits and bend radii remain separate fit items.
    corridor = box(50, 191.8, 31, 62, 16.5, 4)
    offenders = [name for name, shape in parts.items() if overlap(corridor, shape) > .01]
    require(not offenders, f"Proposed ribbon middle run obstructed by {offenders}.")
    return {"nominal_changed_pair_checks": sum(a in new_parts or b in new_parts for a,b in itertools.combinations(parts, 2)),
            "intersection_limit_mm3": COMMON_LIMIT, "display_mount_paths_checked": 4,
            "bezel_aperture_mm": APERTURE,
            "ffc_middle_corridor": {"bounds_mm": [50, 191.8, 31, 112, 208.3, 35],
                                    "obstruction_free": True, "plug_exits_and_bends_verified": False}}


def export_and_reimport(parts, revised, out):
    cad = out / "cad"
    changed_dir = cad / "changed_parts"
    changed_dir.mkdir(parents=True)
    assembly = cq.Assembly(name="Fielddeck_5_display_swap")
    scene = trimesh.Scene()
    for name, shape in parts.items():
        color = ((.92, .51, .22, 1) if name.startswith("face_") else
                 (.10, .13, .15, 1) if name == NEW_DISPLAY else (.34, .42, .48, 1))
        assembly.add(shape, name=name, color=cq.Color(*color))
        vertices, faces = shape.copy().tessellate(.25, .2)
        mesh = trimesh.Trimesh([[v.x, v.y, v.z] for v in vertices], faces, process=True)
        mesh.visual.face_colors = np.array(color) * 255
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    assembly_path = cad / "FIELDDECK_5.step"
    assembly.save(str(assembly_path))
    scene.export(str(cad / "FIELDDECK_5.glb"))
    reread = cq.importers.importStep(str(assembly_path)).val()
    require(reread.isValid(), "Exported assembly STEP is invalid.")
    remaining = list(reread.Solids())
    for name, shape in parts.items():
        for solid in shape.Solids():
            match = next((item for item in remaining if matches(solid, item)
                          and (same_vendor_centroid(solid, item) if name == NEW_DISPLAY
                               else overlap(solid, item) >= .99999 * shape_volume(solid))), None)
            require(match is not None, f"Exported assembly solid lost geometry or placement: {name}")
            remaining.remove(match)
    require(not remaining, "Exported assembly contains extra solids.")
    glb = trimesh.load(cad / "FIELDDECK_5.glb", force="scene")
    require(set(glb.graph.nodes_geometry) == set(parts), "GLB shape inventory differs.")
    for name, shape in parts.items():
        transform, geometry = glb.graph[name]
        mesh = glb.geometry[geometry].copy()
        mesh.apply_transform(transform)
        require(np.allclose(mesh.bounds.flatten(), bounds(shape), atol=.3, rtol=0),
                f"GLB shape bounds differ: {name}")
    export_rows = []
    # One spacer file defines the four identical pieces.
    for name in sorted(CHANGED | {"display_spacer_1"}):
        body = revised[name]
        lower = bounds(body)[:3]
        local = body.translate(tuple(-v for v in lower))
        step = changed_dir / (name + ".step")
        stl = step.with_suffix(".stl")
        cq.exporters.export(local, str(step))
        cq.exporters.export(local, str(stl), tolerance=.08, angularTolerance=.12)
        copy = cq.importers.importStep(str(step)).val()
        mesh = trimesh.load(stl, force="mesh", process=True)
        dimensions = [bounds(copy)[i + 3] - bounds(copy)[i] for i in range(3)]
        require(copy.isValid() and len(copy.Solids()) == 1 and matches(copy, local), f"Exported {name} STEP differs.")
        require(mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
                and abs(mesh.volume / shape_volume(copy) - 1) < .015, f"Exported {name} STL differs or is open.")
        require(max(dimensions[:2]) <= 220, f"{name} exceeds the nominal print bed.")
        export_rows.append({"part": name, "quantity": 4 if name.startswith("display_spacer") else 1,
                            "dimensions_mm": [round(v, 3) for v in dimensions],
                            "step_sha256": sha(step), "stl_sha256": sha(stl)})
    return {"reimported_assembly_solids": len(reread.Solids()), "exported_parts": export_rows,
            "vendor_solid_reimport_check": "bounds, volume and placed centroid",
            "assembly_step_sha256": sha(assembly_path), "assembly_glb_sha256": sha(cad / "FIELDDECK_5.glb")}


def power_comparison(design, published):
    a = design["engineering_assumptions"]
    voltage = a["supply_voltage_v"]
    bank = design["power_bank"]
    energy = bank["capacity_mah"] / 1000 * a["power_bank_cell_voltage_v"]
    usable = [energy * e * u for e, u in zip(a["conversion_efficiency_range"], a["usable_capacity_fraction_range"])]
    keyboard = a["keyboard_current_a"]["normal_allocation"]
    rows = []
    for scenario, pi, display1, display2, keys in (
        ("work_published_panel_power", a["pi_current_a"]["work"], a["display_w"]["published"], published, keyboard),
        ("stress_design_allocation", a["pi_current_a"]["stress"], a["display_w"]["allocated"], a["display_w"]["allocated"], keyboard),
        ("high_keyboard_demand", a["pi_current_a"]["stress"], a["display_w"]["allocated"], a["display_w"]["allocated"],
         a["keyboard_current_a"]["usb2_high_power_sensitivity"]),
    ):
        def result(display):
            watts = voltage * (pi + keys + a["fan_current_a"]) + display
            return {"display_w": display, "system_w": round(watts, 3), "runtime_h": [round(e / watts, 3) for e in usable],
                    "source_margin_a": round(bank["rated_5v_current_a"] - watts / voltage, 3)}
        rows.append({"scenario": scenario, "original_7inch": result(display1), "variant_5inch": result(display2)})
    return {"usable_energy_wh": usable, "scenarios": rows, "physical_validation_performed": False,
            "limits": ["Published panel consumption is a scenario input with no maximum implied.",
                       "Original 3 W panel allocation is retained for stress.",
                       "Bank regulation, cable contact resistance and duty cycle remain assumptions."]}


def write_bom(base, out):
    items = deepcopy(read(base / "bom.json")["items"])
    for item in items:
        if item["id"] == "display":
            item.update(description="Raspberry Pi Touch Display 2, 5-inch portrait kit", manufacturer="Raspberry Pi",
                        mpn="SC1975", url="https://www.raspberrypi.com/products/touch-display-2/",
                        open_issue="Vendor STEP and drawing have different lug depths. Verify actual hardware before fabrication.")
        elif item["id"] == "m25_6":
            item.update(description="Display mounting fastener selection", mpn=None, specification="M2.5; length pending actual seat and thread measurement",
                        acquisition="resolve", open_issue="Nominal STEP assembly uses 4.52 mm spacing on four supports; verify screw engagement.")
        for field in ("price_usd", "price_basis", "availability"):
            item.pop(field, None)
    for name in sorted(CHANGED | {"display_spacer_1"}):
        items.append({"id": name, "description": "Revised enclosure part", "quantity": 4 if name.startswith("display_spacer") else 1,
                      "unit": "ea", "acquisition": "make", "specification": "Nominal CAD export for digital review"})
    write(out / "BOM.json", {"items": items})
    columns = ["id", "description", "manufacturer", "mpn", "specification", "quantity", "unit", "acquisition", "url", "open_issue"]
    with (out / "BOM.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(items)


def build(base, output):
    base, output = Path(base).resolve(), Path(output).resolve()
    evidence = read(ROOT / "sources/evidence.json")
    parts, geometry = baseline_parts(base, evidence)
    display, mount, vendor_license = vendor_display(evidence)
    assessment = assess_interfaces(mount, evidence, geometry)
    revised = revise_panels(parts, geometry, mount)
    del parts[DISPLAY]
    parts.update(revised)
    parts[NEW_DISPLAY] = display
    checks = verify_geometry(parts, mount)
    output.mkdir(parents=True, exist_ok=False)
    exports = export_and_reimport(parts, revised, output)
    power = power_comparison(read(base / "design.json"), evidence["product_brief"]["documented_power_w"])
    write(output / "power.json", power)
    write(output / "substitution.json", assessment)
    write(output / "connections.json", {"display": assessment["connections"],
                                         "rigid_cad_check": checks["ffc_middle_corridor"]})
    write_bom(base, output)
    write(output / "geometry.json", {"status": "nominal_geometry_checks_passed", "display_mount": mount,
                                    "checks": checks, "exports": exports, "physical_fit_verified": False})
    (output / "display5-LICENSE.txt").write_bytes(vendor_license)
    shutil.copy2(ROOT / "sources/evidence.json", output / "source-evidence.json")
    return mount, power


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mount, power = build(args.baseline, args.output)
    print(json.dumps({"mount": mount, "power": power}, indent=2))


if __name__ == "__main__":
    main()
