"""Bounded native exports of declared substitution envelopes and mount proposals.

These solids are nominal declarations, never vendor models or proof of physical
fit.  The worker is this fixed source file; supplied data never becomes code.
CadQuery and trimesh are imported only inside the isolated native worker.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

SCHEMA = "hardware_splicer.part_substitution_geometry.v1"
REPORT_SCHEMA = "hardware_splicer.part_substitution.v1"
MAX_BYTES = 2 * 1024 * 1024
MAX_EXPORT_BYTES = 64 * 1024 * 1024
MIN_LIGAMENT_MM = 1.0  # A declared geometry policy, not a strength calculation.
OUTPUT_NAMES = frozenset({"nominal_assembly.step", "nominal_assembly.stl",
                          "replacement_envelope.step", "replacement_envelope.stl",
                          "adapter_plate.step", "adapter_plate.stl"})


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _number(value, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or abs(value) > 10000 or (positive and value <= 0)):
        raise ValueError("Geometry requires finite millimetre values bounded to 10000 mm.")
    return float(value)


def _vector(value, length, *, positive=False):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError("Invalid geometry coordinate vector.")
    return [_number(v, positive=positive) for v in value]


def _overlap(first, second):
    return all(min(a + da, b + db) - max(a, b) > 1e-7
               for a, da, b, db in zip(first["position_mm"], first["dimensions_mm"],
                                       second["position_mm"], second["dimensions_mm"]))


def _rectangle(points):
    if not isinstance(points, list) or len(points) != 4:
        raise ValueError("Only four-hole axis-aligned rectangular patterns are supported.")
    points = [tuple(_vector(point, 2)) for point in points]
    xs, ys = sorted({p[0] for p in points}), sorted({p[1] for p in points})
    if len(xs) != 2 or len(ys) != 2 or set(points) != {(x, y) for x in xs for y in ys}:
        raise ValueError("Only four-hole axis-aligned rectangular patterns are supported.")
    return points


def _adapter(task, envelopes):
    """Resolve one explicit plate proposal or give a concrete fail-closed reason."""
    try:
        if (task.get("status") != "nominal_geometry_requested"
                or task.get("basis") != "declared_mount_patterns"
                or task.get("structural_fit_verified") is not False):
            raise ValueError("Unsupported adapter declaration.")
        target = next((e for e in envelopes if e["part_id"] == task.get("target_part_id")), None)
        if target is None or target["role"] != "replacement":
            raise ValueError("Adapter target must be the declared replacement envelope.")
        position = _vector(task.get("position_mm"), 3)
        if position != target["position_mm"]:
            raise ValueError("Adapter placement differs from the replacement placement.")
        plane = _number(task.get("plane_z_mm"))
        # A bottom-face plane supplies a coherent nominal contact. Other planes
        # require a spacer/offset design and cannot silently bury the plate.
        if plane != 0:
            raise ValueError("Only a bottom-face XY mount plane (local z=0) is supported.")
        thickness = _number(task.get("thickness_mm"), positive=True)
        edge = _number(task.get("edge_margin_mm"), positive=True)
        base = _rectangle(task.get("base_holes_mm"))
        replacement = _rectangle(task.get("replacement_holes_mm"))
        diameters = [_number(task.get(key), positive=True)
                     for key in ("base_hole_diameter_mm", "replacement_hole_diameter_mm")]
        holes = []
        for label, points, diameter in zip(("base", "replacement"), (base, replacement), diameters):
            for x, y in points:
                existing = next((h for h in holes if h["local_xy_mm"] == [x, y]), None)
                if existing:
                    if abs(existing["diameter_mm"] - diameter) > 1e-7:
                        raise ValueError("Coincident source/replacement holes have different bore diameters.")
                    existing["patterns"].append(label)
                else:
                    holes.append({"local_xy_mm": [x, y], "diameter_mm": diameter, "patterns": [label]})
        for i, first in enumerate(holes):
            for second in holes[i + 1:]:
                distance = math.dist(first["local_xy_mm"], second["local_xy_mm"])
                if distance - (first["diameter_mm"] + second["diameter_mm"]) / 2 < MIN_LIGAMENT_MM:
                    raise ValueError("Drill bores overlap or leave less than the declared 1 mm minimum web.")
        if edge - max(diameters) / 2 < MIN_LIGAMENT_MM:
            raise ValueError("Plate edge leaves less than the declared 1 mm minimum ligament.")
        xs = [h["local_xy_mm"][0] for h in holes]
        ys = [h["local_xy_mm"][1] for h in holes]
        minimum = [position[0] + min(xs) - edge, position[1] + min(ys) - edge,
                   position[2] - thickness]
        dimensions = [max(xs) - min(xs) + 2 * edge, max(ys) - min(ys) + 2 * edge, thickness]
        plate = {"position_mm": minimum, "dimensions_mm": dimensions}
        if any(_overlap(plate, envelope) for envelope in envelopes):
            raise ValueError("Nominal plate envelope collides with a revised part envelope.")
        return {"adaptation_id": task.get("adaptation_id"), "target_part_id": target["part_id"],
                "status": "nominal_geometry_generated", **plate, "holes": holes,
                "hole_origin_mm": position, "plane_z_mm": plane,
                "thickness_mm": thickness, "edge_margin_mm": edge,
                "minimum_ligament_mm": MIN_LIGAMENT_MM,
                "parameter_basis": "explicit_declared_mount_adapter",
                "shared_hole_hardware_unverified": any(len(h["patterns"]) > 1 for h in holes),
                "enclosure_fit_verified": False,
                "structural_fit_verified": False}
    except (ValueError, TypeError, KeyError) as exc:
        return {"adaptation_id": task.get("adaptation_id"), "target_part_id": task.get("target_part_id"),
                "status": "blocked", "reason": str(exc), "structural_fit_verified": False}


def _prepare(report):
    if not isinstance(report, dict) or report.get("schema_version") != REPORT_SCHEMA:
        raise ValueError("Unsupported substitution report schema.")
    raw = _canonical(report)
    if len(raw) > MAX_BYTES:
        raise ValueError("Substitution report exceeds geometry input limit.")
    geometry = report.get("geometry", {})
    if geometry.get("basis") != "declared_axis_aligned_envelopes":
        raise ValueError("Unsupported substitution geometry basis.")
    supplied = geometry.get("envelopes")
    tasks = geometry.get("adapter_requirements")
    if (not isinstance(supplied, list) or len(supplied) > 32
            or not isinstance(tasks, list) or len(tasks) > 1):
        raise ValueError("Geometry supports at most 32 envelopes and one adapter task.")
    envelopes = []
    revised = {p["part_id"]: p for p in report.get("revised", {}).get("parts", [])}
    target_id = report.get("replacement", {}).get("target_part_id")
    for supplied_row in supplied:
        row = dict(supplied_row)
        if (not isinstance(row.get("part_id"), str) or not row["part_id"]
                or any(e["part_id"] == row["part_id"] for e in envelopes)
                or row.get("role") not in {"replacement", "unchanged"}):
            raise ValueError("Invalid or duplicate nominal envelope identity.")
        row["dimensions_mm"] = _vector(row.get("dimensions_mm"), 3, positive=True)
        row["position_mm"] = _vector(row.get("position_mm"), 3)
        if any(d < 0.01 for d in row["dimensions_mm"]):
            raise ValueError("Envelope dimensions below 0.01 mm are unsupported.")
        declared = revised.get(row["part_id"])
        if (declared is None or declared.get("dimensions_mm") != row["dimensions_mm"]
                or declared.get("position_mm") != row["position_mm"]):
            raise ValueError("Envelope geometry differs from the revised part declarations.")
        if (row["role"] == "replacement") != (row["part_id"] == target_id):
            raise ValueError("Replacement envelope identity differs from the substitution target.")
        envelopes.append(row)
    if not all(isinstance(task, dict) for task in tasks):
        raise ValueError("Invalid adapter task.")
    adapters = [_adapter(task, envelopes) for task in tasks]
    for task, adapter in zip(tasks, adapters):
        if adapter["status"] == "blocked":
            continue
        original = report.get("replacement", {}).get("original_profile", {})
        selected = revised.get(target_id, {})
        for prefix, profile in (("base", original), ("replacement", selected)):
            mount = profile.get("mount") or {}
            if (task.get(prefix + "_holes_mm") != mount.get("holes_mm")
                    or task.get(prefix + "_hole_diameter_mm") != mount.get("hole_diameter_mm")
                    or task.get("plane_z_mm") != mount.get("plane_z_mm")):
                adapter.update(status="blocked", reason="Adapter drill declaration differs from the source/replacement mount contract.")
                break
            dimensions = profile.get("dimensions_mm")
            radius = task[prefix + "_hole_diameter_mm"] / 2
            if (not isinstance(dimensions, list) or len(dimensions) != 3
                    or any(x - radius < 0 or y - radius < 0 or x + radius > dimensions[0] or y + radius > dimensions[1]
                           for x, y in task[prefix + "_holes_mm"])):
                adapter.update(status="blocked", reason="A declared bore lies outside its source/replacement nominal body.")
                break
    requested_ids = {task.get("adaptation_id") for task in tasks}
    for required in report.get("required_adaptations", []):
        if required.get("kind") == "mount_adapter" and required.get("adaptation_id") not in requested_ids:
            adapters.append({"adaptation_id": required.get("adaptation_id"), "status": "not_generated",
                             "reason": "Complete coplanar mount patterns, placement and explicit plate thickness/edge margin are required.",
                             "structural_fit_verified": False})
    replacements = [e for e in envelopes if e["role"] == "replacement"]
    complete = len(envelopes) == len(revised) and bool(revised)
    return {"envelopes": envelopes, "adapters": adapters, "complete": complete,
            "has_replacement": len(replacements) == 1}


def _safe_output(path):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise ValueError("Geometry output paths cannot contain parent traversal.")
    for component in [path, *path.parents]:
        if component.is_symlink():
            raise ValueError("Geometry output paths cannot contain symlinks.")
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError("Geometry requires a fresh, empty output directory.")
    else:
        path.mkdir(parents=True, exist_ok=False)
    return path


def generate_substitution_geometry(report, output_dir, *, interpreter=None):
    """Return immutable-file inventory for nominal CAD; never alter core verdict.

    ``interpreter`` is a server configuration/testing hook, not a request field.
    Missing native dependencies produce an unavailable receipt, not fake exports.
    """
    prepared = _prepare(report)
    output = _safe_output(output_dir)
    manifest = {"schema_version": SCHEMA, "report_sha256": _sha(_canonical(report)),
                "specification_sha256": report.get("specification_sha256"),
                "generator_sha256": _sha(Path(__file__).read_bytes()),
                "basis": "declared_axis_aligned_envelopes", "nominal_geometry": True,
                "physical_fit_unverified": True, "physical_validation_performed": False,
                "construction_ready": False, "core_status": report.get("status"),
                "source_bindings": [e.get("source") for e in prepared["envelopes"] if e.get("source")],
                "assembly_complete": prepared["complete"],
                "envelopes": prepared["envelopes"],
                "adapter_results": [dict(a, status="nominal_geometry_supported" if a["status"] == "nominal_geometry_generated" else a["status"])
                                    for a in prepared["adapters"]],
                "files": {}, "status": "unknown",
                "limitations": ["Envelopes omit ports, cables, detailed body geometry and manufacturing tolerances.",
                                "Adapter is an unvalidated mount proposal; fastener heads, nuts, tool access, engagement and strength are not modelled.",
                                "Adapter clearance against an enclosure is unassessed; the report supplies no enclosure geometry.",
                                "Assembly STL represents separate nominal bodies, not a printable one-piece assembly.",
                                "Generated CAD does not close required adaptations or grant physical authority."]}
    if not prepared["has_replacement"]:
        manifest["reason"] = "Replacement dimensions and assembly position are required for native geometry."
        return manifest
    from .bounded_process import BoundedProcessError, run_bounded
    configured = os.environ.get("SPLICER3D_PYTHON")
    repository_python = Path(__file__).resolve().parents[2] / ".cache/hardware-splicer/digital-native-venv/bin/python"
    python = str(interpreter or configured or (repository_python if repository_python.is_file() else sys.executable))
    env = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT", "LD_LIBRARY_PATH") if key in os.environ}
    env.update({"PYTHONOPTIMIZE": "0", "PYTHONDONTWRITEBYTECODE": "1", "QT_QPA_PLATFORM": "offscreen",
                "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1"})
    published = []
    with tempfile.TemporaryDirectory(prefix="hs-substitution-") as temporary:
        temporary = Path(temporary)
        request = temporary / "request.json"
        request.write_bytes(_canonical(prepared))
        try:
            result = run_bounded([python, str(Path(__file__).resolve()), "--worker", str(request), str(temporary)],
                                 timeout_s=120, cwd=temporary, env=env)
            if result.returncode:
                raise ValueError(result.stderr_tail.decode("utf-8", errors="replace")[-2000:] or "Native geometry worker failed.")
            receipt_path = temporary / "result.json"
            if receipt_path.stat().st_size > MAX_BYTES:
                raise ValueError("Native receipt exceeds limit.")
            receipt = json.loads(receipt_path.read_bytes())
            files = receipt["files"]
            expected = {"nominal_assembly.step", "nominal_assembly.stl", "replacement_envelope.step", "replacement_envelope.stl"}
            if any(a["status"] == "nominal_geometry_generated" for a in prepared["adapters"]):
                expected |= {"adapter_plate.step", "adapter_plate.stl"}
            if set(files) != expected or not set(files) <= OUTPUT_NAMES:
                raise ValueError("Unexpected native export inventory.")
            total = 0
            for name, entry in files.items():
                path = temporary / name
                if path.is_symlink() or not path.is_file():
                    raise ValueError("Invalid native export.")
                total += path.stat().st_size
                if total > MAX_EXPORT_BYTES:
                    raise ValueError("Native geometry exports exceed 64 MiB.")
                raw = path.read_bytes()
                if entry != {"sha256": _sha(raw), "size_bytes": len(raw)}:
                    raise ValueError("Native geometry export hash mismatch.")
            # All validation precedes create-only publication.
            for name in files:
                # Temporary files may be on a different filesystem.
                destination = output / name
                with destination.open("xb") as stream:
                    published.append(destination)
                    stream.write((temporary / name).read_bytes())
            all_requested = all(a["status"] == "nominal_geometry_generated" for a in prepared["adapters"])
            manifest.update(status="generated" if prepared["complete"] and all_requested else "partial",
                            files=files, native_verification=receipt["verification"],
                            adapter_results=prepared["adapters"],
                            native_runtime=receipt["runtime"])
        except (BoundedProcessError, ValueError, OSError, KeyError, TypeError) as exc:
            # A failed invocation cannot leave a plausible partial native set.
            for path in published:
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            manifest.update(status="unavailable", reason=str(exc))
    return manifest


def _worker(request_path, output):
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_EXPORT_BYTES, MAX_EXPORT_BYTES))
    if hasattr(os, "sched_getaffinity"):
        allowed = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, allowed[:2])
    import cadquery as cq
    import trimesh
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    request_path, output = Path(request_path), Path(output)
    if request_path.stat().st_size > MAX_BYTES:
        raise ValueError("Native request exceeds limit.")
    request = json.loads(request_path.read_bytes())
    envelopes = request["envelopes"]
    solids = [cq.Workplane("XY").box(*e["dimensions_mm"], centered=(False, False, False)).val()
              .translate(tuple(e["position_mm"])) for e in envelopes]
    replacement_index = next(i for i, e in enumerate(envelopes) if e["role"] == "replacement")
    adapter = next((a for a in request["adapters"] if a["status"] == "nominal_geometry_generated"), None)
    plate = None
    if adapter:
        plate = cq.Workplane("XY").box(*adapter["dimensions_mm"], centered=(False, False, False)).val().translate(tuple(adapter["position_mm"]))
        origin = adapter["hole_origin_mm"]
        for hole in adapter["holes"]:
            x, y = hole["local_xy_mm"]
            bore = cq.Solid.makeCylinder(hole["diameter_mm"] / 2, adapter["thickness_mm"] + 2,
                                         cq.Vector(origin[0] + x, origin[1] + y, adapter["position_mm"][2] - 1))
            plate = plate.cut(bore)
        if not plate.isValid() or len(plate.Solids()) != 1:
            raise ValueError("Adapter is not one valid solid.")
    entries = [("nominal_assembly", cq.Compound.makeCompound(solids + ([plate] if plate else [])), False),
               ("replacement_envelope", solids[replacement_index], True)]
    if plate:
        entries.append(("adapter_plate", plate, True))
    verification = {}
    files = {}
    for name, shape, single in entries:
        # Assemblies share topology with their constituent parts. Give each
        # export its own topology so STL triangulation cannot contaminate a
        # later STEP/bbox check of a constituent.
        shape = shape.copy(mesh=False)
        if not shape.isValid():
            raise ValueError("Invalid nominal BRep.")
        step, stl = output / (name + ".step"), output / (name + ".stl")
        cq.exporters.export(shape, str(step), exportType="STEP")
        reopened = cq.importers.importStep(str(step)).val()
        if not reopened.isValid() or len(reopened.Solids()) != len(shape.Solids()):
            raise ValueError("STEP solid inventory differs after export.")
        bounds = lambda s: [s.BoundingBox().xmin, s.BoundingBox().ymin, s.BoundingBox().zmin,
                            s.BoundingBox().xmax, s.BoundingBox().ymax, s.BoundingBox().zmax]
        if any(abs(a - b) > 1e-5 for a, b in zip(bounds(shape), bounds(reopened))):
            raise ValueError(f"STEP bounds differ after export: {name}: {bounds(shape)} != {bounds(reopened)}")
        expected_solid_bounds = sorted(bounds(solid) for solid in shape.Solids())
        actual_solid_bounds = sorted(bounds(solid) for solid in reopened.Solids())
        if any(abs(a - b) > 1e-5 for expected, actual in zip(expected_solid_bounds, actual_solid_bounds)
               for a, b in zip(expected, actual)):
            raise ValueError("STEP per-body placement differs after export.")
        volume = sum(s.Volume() for s in shape.Solids())
        if abs(sum(s.Volume() for s in reopened.Solids()) - volume) > max(1e-5, volume * 1e-7):
            raise ValueError("STEP volume differs after export.")
        # Meshing attaches triangulation to the original shape and can change
        # OpenCascade's bbox approximation. Bind STEP before triangulating.
        cq.exporters.export(shape, str(stl), exportType="STL", tolerance=0.02, angularTolerance=0.1)
        mesh = trimesh.load(str(stl), force="mesh", process=True)
        if any(abs(a - b) > 0.03 for a, b in zip(bounds(reopened), mesh.bounds.flatten())):
            raise ValueError("STL bounds differ after export.")
        if single and (not mesh.is_watertight or abs(abs(mesh.volume) - volume) > max(0.1, volume * 0.005)):
            raise ValueError("Single-part STL is open or has inconsistent volume.")
        row = {"step_valid": True, "solid_count": len(reopened.Solids()),
               "bounds_mm": bounds(reopened), "volume_mm3": volume,
               "per_solid_bounds_mm": actual_solid_bounds,
               "stl_bounds_verified": True, "stl_watertight": bool(mesh.is_watertight),
               "single_printable_part_claimed": False}
        if name == "adapter_plate":
            actual = set()
            for face in reopened.Faces():
                surface = BRepAdaptor_Surface(face.wrapped)
                if surface.GetType() == GeomAbs_Cylinder:
                    cylinder = surface.Cylinder()
                    axis = cylinder.Axis()
                    if abs(abs(axis.Direction().Z()) - 1) > 1e-7:
                        raise ValueError("Nonvertical adapter bore.")
                    point = axis.Location()
                    actual.add((round(point.X(), 5), round(point.Y(), 5), round(cylinder.Radius() * 2, 5)))
            origin = adapter["hole_origin_mm"]
            expected = {(round(origin[0] + h["local_xy_mm"][0], 5),
                         round(origin[1] + h["local_xy_mm"][1], 5), round(h["diameter_mm"], 5)) for h in adapter["holes"]}
            if actual != expected:
                raise ValueError("Reimported adapter bore axes/diameters differ from both declared patterns.")
            row["reimported_bores_mm"] = [list(hole) for hole in sorted(actual)]
            expected_volume = math.prod(adapter["dimensions_mm"]) - sum(math.pi * (h["diameter_mm"] / 2) ** 2 * adapter["thickness_mm"] for h in adapter["holes"])
            if abs(volume - expected_volume) > 1e-4:
                raise ValueError("Adapter drill volume differs from declared through holes.")
            row["through_drill_volume_verified"] = True
        verification[name] = row
        for path in (step, stl):
            raw = path.read_bytes()
            files[path.name] = {"sha256": _sha(raw), "size_bytes": len(raw)}
    receipt = {"files": files, "verification": verification,
               "runtime": {"python_version": sys.version.split()[0], "cadquery_version": cq.__version__,
                           "trimesh_version": trimesh.__version__}}
    (output / "result.json").write_bytes(_canonical(receipt))


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--worker":
        raise SystemExit("This module is an internal fixed native worker.")
    _worker(sys.argv[2], sys.argv[3])
