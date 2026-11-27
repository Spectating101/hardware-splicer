"""Measured fit of a scene revision: part-to-part interference and clearance, and overall size.

Runs as a standalone script in the native CAD interpreter (numpy, scipy, trimesh; manifold3d
for exact interference volumes), so it needs nothing from the hardware_splicer package:

    python scene_fit.py --glb MODEL.glb --parts parts.json [--near 2.0]

It reads the GLB the scene draws and the parts sidecar that names its nodes, and prints JSON:

* ``size_mm``: the assembled model's bounding size.
* ``pairs``: every pair of parts closer than ``--near`` millimetres, each classified as
  ``overlap`` (solids intersect; exact volume from a mesh boolean), ``touching`` (surfaces meet
  without measurable overlap: normal for stacked or fastened parts), ``tight`` (a gap under
  ``TIGHT_MM``) or ``near``. Gaps are the minimum distance between dense surface samples, so
  each is an upper bound with a ``precision_mm``: the true gap is at most ``gap_mm`` and at
  least ``gap_mm - precision_mm``.
* ``loose_parts``: parts that neither touch nor overlap any other part, so nothing in the model holds them.
* Each pair names both parts' ``basis`` (custom, vendor_step, envelope, unknown, ...) and is
  ``stand_in`` when either is an envelope or unknown shape: a clash there means the shape is not
  known well enough, not that real parts collide.
* ``not_computed``: what could not be measured and why (an open mesh has no volume, so its
  overlap cannot be computed; its clearance still can).

Nothing here is physical proof: it measures the CAD model, including any envelope stand-ins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from itertools import combinations
from pathlib import Path

VERSION = "scene-fit.v6"
NEAR_MM = 2.0          # pairs whose bounding boxes are farther apart than this are clear
TIGHT_MM = 1.0         # a measured gap under this is reported as tight
TOUCH_MM = 0.05        # below this, surfaces meet
OVERLAP_MM3 = 0.5      # below this intersection volume, a contact is tessellation, not interference
# Parts drawn as rough stand-ins: an envelope box or an unknown shape. A clash involving one says the
# shape is not known well enough, not that the real parts collide.
STAND_IN = {"envelope", "unknown"}
SAMPLE_SPACING_MM = 0.35
MAX_SAMPLES = 60_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _aabb_gap(a, b) -> float:
    """Distance between two axis-aligned boxes ((min xyz), (max xyz)); 0 when they overlap."""
    gaps = [max(a[0][i] - b[1][i], b[0][i] - a[1][i], 0.0) for i in range(3)]
    return math.sqrt(sum(g * g for g in gaps))


def _surface_points(mesh, spacing: float):
    import numpy as np
    import trimesh

    area = float(mesh.area)
    count = int(min(MAX_SAMPLES, max(200, area / (spacing * spacing))))
    points, _ = trimesh.sample.sample_surface(mesh, count, seed=7)
    return np.vstack([np.asarray(mesh.vertices), np.asarray(points)])


def _samples(body: dict, spacing: float):
    """Each part is sampled and indexed once, then reused for every pair it is in."""
    if "tree" not in body:
        from scipy.spatial import cKDTree

        body["points"] = _surface_points(body["mesh"], spacing)
        body["tree"] = cKDTree(body["points"])
    return body["points"], body["tree"]


def _near_points(points, bounds, margin: float):
    """Only the samples that could be closest: those inside the other part's box grown by margin."""
    import numpy as np

    low = np.asarray(bounds[0]) - margin
    high = np.asarray(bounds[1]) + margin
    return points[np.all((points >= low) & (points <= high), axis=1)]


def _to_surface(points, body: dict) -> float:
    """Exact distance from points to the nearest of a part's triangles (checked among the 24 closest
    by centroid, so the result can only be larger than the true distance, never smaller)."""
    if not len(points):
        return math.inf
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree

    triangles = body["mesh"].triangles
    if "centroid_tree" not in body:
        body["centroid_tree"] = cKDTree(triangles.mean(axis=1))
    k = min(24, len(triangles))
    _, index = body["centroid_tree"].query(points, k=k)
    index = np.asarray(index).reshape(len(points), -1)
    best = math.inf
    for start in range(0, len(points), 4096):
        chunk = points[start:start + 4096]
        rows = index[start:start + 4096]
        query = np.repeat(chunk, rows.shape[1], axis=0)
        closest = trimesh.triangles.closest_point(triangles[rows.ravel()], query)
        best = min(best, float(np.linalg.norm(closest - query, axis=1).min()))
    return best


def _min_gap(a: dict, b: dict, spacing: float, near: float) -> tuple[float, float]:
    """Minimum distance between two parts' surfaces, from dense samples, and its precision."""
    pa, ta = _samples(a, spacing)
    pb, tb = _samples(b, spacing)
    qa = _near_points(pa, b["bounds"], near + spacing)
    qb = _near_points(pb, a["bounds"], near + spacing)
    gaps = [float(tb.query(qa, k=1)[0].min()) if len(qa) else math.inf,
            float(ta.query(qb, k=1)[0].min()) if len(qb) else math.inf]
    gap = min(gaps)
    if gap < near:
        # Sample-to-sample distance cannot tell a seated contact from a gap under the sample spacing.
        # Refine with exact distances from each part's samples to the other part's real triangles:
        # a face resting on a face then measures 0. Still an upper bound, now a much tighter one.
        gap = min(gap, _to_surface(qa, b), _to_surface(qb, a))
    # Samples are about `spacing` apart on each surface, so the closest true points lie within
    # half a spacing of a sample on each side.
    return gap, spacing


def _overlap_volume(a, b) -> float | None:
    try:
        import manifold3d
    except ImportError:
        return None
    import numpy as np

    def solid(mesh):
        return manifold3d.Manifold(manifold3d.Mesh(
            vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))

    try:
        common = solid(a) ^ solid(b)
        return float(common.volume())
    except Exception:  # a mesh manifold3d refuses is reported as not computed
        return None


def analyse(glb: Path, parts_path: Path, near: float = NEAR_MM) -> dict:
    import numpy as np
    import trimesh

    sidecar = json.loads(parts_path.read_text())
    by_node = {}
    for part in sidecar.get("parts", []):
        by_node.setdefault(part.get("node_name"), part)
    scale = float(sidecar.get("glb_scale_to_mm") or 1.0)
    scene = trimesh.load(str(glb), force="scene")
    bodies = []
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        part = by_node.get(node)
        # Copper is checked by KiCad's DRC, which knows nets and clearances; the fit engine measures bodies.
        if not part or part.get("part_id") == "world" or part.get("geometry_basis") == "copper":
            continue
        mesh = scene.geometry[name].copy()
        # Exporters often store each triangle's corners separately (flat shading), which reads as
        # an open mesh; merging coincident vertices restores the solid without moving geometry.
        mesh.merge_vertices(merge_tex=True, merge_norm=True)
        mesh.apply_transform(transform)
        if scale != 1.0:
            mesh.apply_scale(scale)
        bodies.append({"part": part, "mesh": mesh, "bounds": mesh.bounds.tolist(), "solid": bool(mesh.is_watertight)})

    result = {
        "schema": "hardware_splicer.scene_fit.v1",
        "version": VERSION,
        "glb_sha256": _sha256(glb),
        "parts_sha256": _sha256(parts_path),
        "method": {
            "interference": "exact intersection volume of closed meshes (manifold3d)",
            "clearance": f"minimum distance between surface samples about {SAMPLE_SPACING_MM} mm apart",
            "near_mm": near, "tight_mm": TIGHT_MM, "touch_mm": TOUCH_MM, "overlap_mm3": OVERLAP_MM3,
        },
        "basis": "CAD model, including envelope and unknown-shape stand-ins; physical fit not tested",
        "parts_measured": len(bodies),
        "parts_unmatched": sorted(node for node in scene.graph.nodes_geometry if node not in by_node),
        "size_mm": None,
        "pairs": [],
        "not_computed": [],
    }
    if not bodies:
        return result
    low = np.min([b["bounds"][0] for b in bodies], axis=0)
    high = np.max([b["bounds"][1] for b in bodies], axis=0)
    result["size_mm"] = [round(float(v), 2) for v in (high - low)]

    open_parts = sorted({b["part"]["part_id"] for b in bodies if not b["solid"]})
    if open_parts:
        result["not_computed"].append({"what": "overlap volume", "parts": open_parts,
                                       "why": "open mesh (not a closed solid), so it has no volume"})
    manifold_available = True
    try:
        import manifold3d  # noqa: F401
    except ImportError:
        manifold_available = False
        result["not_computed"].append({"what": "overlap volume", "parts": [], "why": "manifold3d not installed"})

    for a, b in combinations(bodies, 2):
        if _aabb_gap(a["bounds"], b["bounds"]) > near:
            continue
        overlap = None
        if manifold_available and a["solid"] and b["solid"]:
            overlap = _overlap_volume(a["mesh"], b["mesh"])
        if overlap is not None and overlap > OVERLAP_MM3:
            kind, gap, precision = "overlap", 0.0, 0.0
        else:
            gap, precision = _min_gap(a, b, SAMPLE_SPACING_MM, near)
            if gap > near:
                continue
            kind = "touching" if gap < TOUCH_MM else "tight" if gap < TIGHT_MM else "near"
        basis = [a["part"].get("geometry_basis") or "unknown", b["part"].get("geometry_basis") or "unknown"]
        result["pairs"].append({
            "a": a["part"]["part_id"], "b": b["part"]["part_id"], "kind": kind,
            "basis": basis, "stand_in": any(item in STAND_IN for item in basis),
            "gap_mm": round(gap, 3), "precision_mm": round(precision, 3),
            "overlap_mm3": round(overlap, 2) if overlap is not None else None,
            "overlap_computed": overlap is not None,
        })
    order = {"overlap": 0, "tight": 1, "near": 2, "touching": 3}
    result["pairs"].sort(key=lambda row: (order[row["kind"]], -(row["overlap_mm3"] or 0), row["gap_mm"], row["a"], row["b"]))
    result["counts"] = {kind: sum(row["kind"] == kind for row in result["pairs"]) for kind in order}
    result["counts"]["overlap_real"] = sum(row["kind"] == "overlap" and not row["stand_in"] for row in result["pairs"])
    result["counts"]["overlap_stand_in"] = sum(row["kind"] == "overlap" and row["stand_in"] for row in result["pairs"])
    # A part that touches nothing is held by nothing in the model (Replicator's "floating" check): a gusset 3 mm short of
    # its plate, a board off its standoffs. A fastener left out of the model, or a part meant to be loose, shows here too.
    held = {name for row in result["pairs"] if row["kind"] in ("overlap", "touching") for name in (row["a"], row["b"])}
    result["loose_parts"] = sorted({b["part"]["part_id"] for b in bodies} - held) if len(bodies) > 1 else []
    result["counts"]["loose"] = len(result["loose_parts"])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--glb", required=True, type=Path)
    parser.add_argument("--parts", required=True, type=Path)
    parser.add_argument("--near", type=float, default=NEAR_MM)
    args = parser.parse_args(argv)
    json.dump(analyse(args.glb, args.parts, args.near), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
