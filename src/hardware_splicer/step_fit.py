"""Fit check of any STEP assembly, from any CAD program: interference, clearance, loose parts, size and volumes.

SolidWorks, Fusion 360, Onshape, FreeCAD and KiCad all export STEP. HS's own fit engine (``scene_fit``) measured only the
scenes HS drew; this reads someone's edited assembly instead, keeps each part's name from the STEP product tree, meshes
every solid, and hands the result to ``scene_fit``. Runs as a standalone script in the native CAD interpreter (CadQuery,
trimesh, manifold3d), like ``scene_fit``:

    python step_fit.py ASSEMBLY.step [--near 2.0] [--density PART=g_per_cm3 ...]

It prints JSON:

* ``parts``: each solid's path in the assembly tree (``demo/arm/hub``), volume and bounding box; with ``--density`` (a part
  name or ``*`` for all), its mass;
* ``fit``: ``scene_fit``'s report on those parts: overlapping pairs with their exact intersection volume, touching, tight
  and near pairs, and loose parts that touch nothing;
* ``summary``: counts of overlaps, tight gaps and loose parts.

What it measures is the CAD model as exported, meshed to about 0.05 mm: an overlap may be a deliberate press fit or a
thread drawn as a plain cylinder, and nothing here was built or measured. A part that exports with no solid (a surface
body, a sketch) is listed under ``skipped``.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

VERSION = "step-fit.v1"
TOLERANCE_MM = 0.05
ANGULAR = 0.2


def _scene_fit():
    spec = importlib.util.spec_from_file_location("hs_scene_fit", Path(__file__).with_name("scene_fit.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _solids(step: Path):
    """(path, solid) for every solid in the assembly, with its placement applied. A single-part file with several bodies
    gives each body its own name (part#1, part#2)."""
    import cadquery as cq

    root = cq.Assembly.importStep(str(step))

    def walk(node, loc, path):
        loc = loc * node.loc
        here = path + [node.name]
        if node.obj is not None:
            shape = node.obj.val() if hasattr(node.obj, "val") else node.obj
            solids = shape.Solids() if hasattr(shape, "Solids") else []
            if not solids:
                yield "/".join(here), None
            for i, solid in enumerate(solids):
                name = "/".join(here) + (f"#{i + 1}" if len(solids) > 1 else "")
                yield name, solid.moved(loc)
        for child in node.children:
            yield from walk(child, loc, here)

    yield from walk(root, cq.Location(), [])


def analyse(step: Path | str, near: float = 2.0, density: dict[str, float] | None = None) -> dict:
    import numpy as np
    import trimesh

    step, density = Path(step), density or {}
    parts, skipped, scene = [], [], trimesh.Scene()
    seen: dict[str, int] = {}
    for name, solid in _solids(step):
        if solid is None:
            skipped.append({"part": name, "why": "no solid body in the STEP file"})
            continue
        seen[name] = seen.get(name, 0) + 1
        node = name if seen[name] == 1 else f"{name}~{seen[name]}"
        vertices, triangles = solid.tessellate(TOLERANCE_MM, ANGULAR)
        mesh = trimesh.Trimesh(np.array([v.toTuple() for v in vertices]), np.array(triangles), process=True)
        scene.add_geometry(mesh, node_name=node, geom_name=node)
        bb = solid.BoundingBox()
        row = {"part": node, "volume_mm3": round(solid.Volume(), 1),
               "bbox_mm": [round(x, 2) for x in (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)]}
        leaf = node.split("/")[-1]
        rho = density.get(node, density.get(leaf, density.get("*")))
        if rho is not None:
            row["mass_g"] = round(solid.Volume() / 1000 * rho, 2)
        parts.append(row)
    result = {"schema": "hardware_splicer.step_fit.v1", "version": VERSION, "source": step.name,
              "source_sha256": hashlib.sha256(step.read_bytes()).hexdigest(), "mesh_tolerance_mm": TOLERANCE_MM,
              "parts": parts, "skipped": skipped, "fit": None,
              "claim_boundary": "Measures the exported CAD model; overlaps may be deliberate press fits or simplified threads. "
                                "Nothing was built or measured."}
    if not parts:
        result["summary"] = {"parts": 0, "overlaps": 0, "tight": 0, "loose": 0}
        return result
    with tempfile.TemporaryDirectory() as tmp:
        glb, sidecar = Path(tmp) / "assembly.glb", Path(tmp) / "parts.json"
        scene.export(str(glb))
        sidecar.write_text(json.dumps({"glb_scale_to_mm": 1.0, "parts": [
            {"node_name": p["part"], "part_id": p["part"], "geometry_basis": "step_import"} for p in parts]}))
        fit = _scene_fit().analyse(glb, sidecar, near=near)
    for key in ("glb_sha256", "parts_sha256"):
        fit.pop(key, None)
    result["fit"] = fit
    kinds = [pair.get("kind") or pair.get("classification") for pair in fit.get("pairs", [])]
    result["summary"] = {"parts": len(parts), "overlaps": kinds.count("overlap"), "tight": kinds.count("tight"),
                         "loose": len(fit.get("loose_parts", [])), "size_mm": fit.get("size_mm")}
    if "mass_g" in parts[0] or any("mass_g" in p for p in parts):
        result["summary"]["mass_g"] = round(sum(p.get("mass_g", 0) for p in parts), 1)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", type=Path)
    ap.add_argument("--near", type=float, default=2.0)
    ap.add_argument("--density", action="append", default=[], help="PART=g_per_cm3, or *=g_per_cm3 for every part")
    args = ap.parse_args(argv)
    density = {}
    for item in args.density:
        name, _, value = item.partition("=")
        density[name] = float(value)
    print(json.dumps(analyse(args.step, args.near, density), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
