"""STEP / closed STL -> Gmsh tetrahedra -> bounded FEM screening.

This is a LOCAL, trusted-file workflow. No file-path-taking HTTP endpoint.
Gmsh is optional. Materials, support and pressure loading remain hypotheses.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .mechanical_fem import FemInput, solve_linear_tetra_fem

MAX_CAD_BYTES = 20 * 1024 * 1024
MAX_MESH_NODES = 2000
MAX_MESH_ELEMENTS = 5000
AxisPlane = Literal["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]


@dataclass(frozen=True)
class LocalRefinement:
    """Declare an optional, bounded field for STEP circular curves and/or spots."""
    target_size_mm: float
    radius_mm: float
    refine_circular_edges: bool = True
    hotspot_centers_mm: tuple[tuple[float, float, float], ...] = ()


@dataclass(frozen=True)
class CadTetraMesh:
    nodes_m: list[list[float]]
    elements: list[list[int]]
    surface_triangles: list[list[int]]
    source_sha256: str
    source_format: str
    source_name: str
    source_units: str
    mesh_target_mm: float
    volume_m3: float
    bounding_box_m: list[list[float]]
    cad_kernel_volume_m3: float | None = None
    mesh_volume_error_fraction: float | None = None
    local_refinement: dict[str, Any] | None = None


def _load_gmsh() -> Any:
    try:
        import gmsh
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Gmsh Python and its libgmsh shared library are required. "
            "Install the optional CAD-meshing dependency 'gmsh' in a supported environment."
        ) from exc
    return gmsh


def _validate_volume_boundary(tets: list[list[int]], triangles: list[list[int]]) -> None:
    """Demand one closed, connected manifold skin that exactly bounds the tets.

    Prevents accepting a triangulation with holes, disconnected shell cavities,
    overlapping tets or a surface that does not match the volume finite elements.
    """
    tetra_faces: Counter[tuple[int, int, int]] = Counter()
    for a, b, c, d in tets:
        for face in ((a, b, c), (a, b, d), (a, c, d), (b, c, d)):
            tetra_faces[tuple(sorted(face))] += 1
    if any(count > 2 for count in tetra_faces.values()):
        raise ValueError("nonmanifold tetrahedral volume: a face is shared over twice")
    boundary = {face for face, count in tetra_faces.items() if count == 1}
    surface = [tuple(sorted(tri)) for tri in triangles]
    if len(surface) != len(set(surface)) or set(surface) != boundary:
        raise ValueError("mesh surface does not exactly match tetrahedral exterior faces")

    edges_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    for idx, (a, b, c) in enumerate(surface):
        for edge in ((a, b), (b, c), (c, a)):
            edges_to_faces[tuple(sorted(edge))].append(idx)
    if any(len(adjoining) != 2 for adjoining in edges_to_faces.values()):
        raise ValueError("nonmanifold/open surface: boundary edges must have two triangles")
    adjacency: dict[int, set[int]] = defaultdict(set)
    for left, right in edges_to_faces.values():
        adjacency[left].add(right)
        adjacency[right].add(left)
    visited = {0}
    pending = [0]
    while pending:
        for adjacent in adjacency[pending.pop()] - visited:
            visited.add(adjacent)
            pending.append(adjacent)
    if len(visited) != len(surface):
        raise ValueError("multiple disconnected surface shells; cavities are not supported")


def _triangulated_volume_mesh(gmsh: Any, *, to_m: float) -> tuple[
    list[list[float]], list[list[int]], list[list[int]], float, list[list[float]]
]:
    import numpy as np

    tags, coords, _ = gmsh.model.mesh.getNodes()
    tags = [int(x) for x in tags]
    coords = np.asarray(coords, dtype=float).reshape((-1, 3))
    types, _, connectivity = gmsh.model.mesh.getElements(dim=3)
    if len(types) != 1 or int(types[0]) != 4:
        raise ValueError("CAD mesh must contain exclusively linear 4-node tetrahedra")
    tets_by_tag = np.asarray(connectivity[0], dtype=int).reshape((-1, 4))
    if not len(tets_by_tag) or len(tets_by_tag) > MAX_MESH_ELEMENTS:
        raise ValueError(f"tetrahedral element count must be 1..{MAX_MESH_ELEMENTS}")

    used = set(int(tag) for tag in tets_by_tag.ravel())
    if len(used) > MAX_MESH_NODES:
        raise ValueError(f"mesh node count exceeds {MAX_MESH_NODES}")
    node_lookup = {tag: i for i, tag in enumerate(tags)}
    if used - node_lookup.keys():
        raise ValueError("tetrahedral mesh contains undefined node tags")
    # Deterministic ordering by the native Gmsh node tag.
    selected = sorted(used)
    remap = {tag: index for index, tag in enumerate(selected)}
    nodes = (coords[[node_lookup[t] for t in selected]] * to_m).tolist()
    tets = [[remap[int(tag)] for tag in tet] for tet in tets_by_tag]

    surface_types, _, surface_connectivity = gmsh.model.mesh.getElements(dim=2)
    triangles: list[list[int]] = []
    for kind, flat in zip(surface_types, surface_connectivity):
        if int(kind) != 2:
            raise ValueError("CAD exterior mesh must contain only 3-node triangles")
        for tri in np.asarray(flat, dtype=int).reshape((-1, 3)):
            if all(int(tag) in remap for tag in tri):
                triangles.append([remap[int(tag)] for tag in tri])
    if not triangles:
        raise ValueError("no external triangles were generated for this solid")
    _validate_volume_boundary(tets, triangles)

    points = np.asarray(nodes, dtype=float)
    volumes = []
    for tet in tets:
        v = points[tet]
        det = float(np.linalg.det((v[1:] - v[0]).T))
        edge_lengths = np.linalg.norm(v[:, None, :] - v[None, :, :], axis=2)
        span = float(edge_lengths.max())
        if not math.isfinite(det) or span <= 0 or abs(det) < 1e-10 * span**3:
            raise ValueError("degenerate or near-zero-volume tetrahedron detected")
        volumes.append(abs(det) / 6)
    bounds = [points.min(axis=0).tolist(), points.max(axis=0).tolist()]
    return nodes, tets, triangles, float(sum(volumes)), bounds


def _configure_local_refinement(
    gmsh: Any,
    refinement: LocalRefinement,
    *,
    global_size_mm: float,
    cad_bounds_mm: tuple[float, float, float, float, float, float],
    source_format: str,
) -> dict[str, Any]:
    """Create a Gmsh background mesh field for explicitly scoped hotspots."""
    target = refinement.target_size_mm
    radius = refinement.radius_mm
    if not all(math.isfinite(x) for x in (target, radius)):
        raise ValueError("local mesh size and radius must be finite")
    if not (0.5 <= target < global_size_mm):
        raise ValueError("local mesh target must be >=0.5 mm and smaller than global size")
    if not (0.5 <= radius <= 500):
        raise ValueError("local radius must be in [0.5, 500] mm")
    spots = refinement.hotspot_centers_mm
    if len(spots) > 12:
        raise ValueError("at most 12 explicit hotspot centers are supported")
    if not refinement.refine_circular_edges and not spots:
        raise ValueError("local refinement needs circular CAD edges or hotspot centers")
    xmin, ymin, zmin, xmax, ymax, zmax = cad_bounds_mm
    for spot in spots:
        if len(spot) != 3 or not all(math.isfinite(x) for x in spot):
            raise ValueError("every hotspot must have three finite mm coordinates")
        for coord, lo, hi in zip(spot, (xmin, ymin, zmin), (xmax, ymax, zmax)):
            if coord < lo - 0.01 or coord > hi + 0.01:
                raise ValueError("hotspot must lie within the CAD bounding box")
    curve_tags: list[int] = []
    if refinement.refine_circular_edges:
        if source_format not in {".step", ".stp"}:
            raise ValueError("automatic circular-edge refinement requires STEP CAD")
        curve_tags = [
            tag for dim, tag in gmsh.model.getEntities(dim=1)
            if gmsh.model.getType(dim, tag) == "Circle"
        ]
        if not curve_tags:
            raise ValueError("STEP contains no circular edges; specify hotspot centers")
        if len(curve_tags) > 24:
            raise ValueError("too many circular curves for bounded local refinement")

    fields: list[int] = []
    if curve_tags:
        dist = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(dist, "CurvesList", curve_tags)
        gmsh.model.mesh.field.setNumber(dist, "Sampling", 100)
        threshold = gmsh.model.mesh.field.add("Threshold")
        for key, value in (
            ("InField", dist), ("SizeMin", target),
            ("SizeMax", global_size_mm), ("DistMin", 0), ("DistMax", radius),
        ):
            gmsh.model.mesh.field.setNumber(threshold, key, value)
        fields.append(threshold)
    for cx, cy, cz in spots:
        ball = gmsh.model.mesh.field.add("Ball")
        for key, value in (
            ("XCenter", cx), ("YCenter", cy), ("ZCenter", cz),
            ("Radius", radius), ("VIn", target), ("VOut", global_size_mm),
        ):
            gmsh.model.mesh.field.setNumber(ball, key, value)
        fields.append(ball)

    if len(fields) > 1:
        combined = gmsh.model.mesh.field.add("Min")
        gmsh.model.mesh.field.setNumbers(combined, "FieldsList", fields)
        gmsh.model.mesh.field.setAsBackgroundMesh(combined)
    else:
        gmsh.model.mesh.field.setAsBackgroundMesh(fields[0])

    gmsh.option.setNumber("Mesh.MeshSizeMin", target)
    gmsh.option.setNumber("Mesh.MeshSizeMax", global_size_mm)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    return {
        "mode": "localized_background_mesh",
        "circular_edge_tags": curve_tags,
        "circular_edge_count": len(curve_tags),
        "hotspot_centers_mm": [list(x) for x in spots],
        "local_mesh_target_mm": target,
        "global_mesh_target_mm": global_size_mm,
        "local_radius_mm": radius,
        "physical_accuracy_verified": False,
    }


def _count_nodes_near_refinement_features(
    gmsh: Any,
    nodes_m: list[list[float]],
    info: dict[str, Any],
) -> int:
    """Count actual mesh nodes within the declared field's influence region.

    Used as a *mesh density diagnostic*, not a direct proof of stress convergence.
    """
    import numpy as np
    from scipy.spatial import cKDTree

    samples: list[list[float]] = [
        list(center) for center in info["hotspot_centers_mm"]
    ]
    for tag in info["circular_edge_tags"]:
        bounds_low, bounds_high = gmsh.model.getParametrizationBounds(1, tag)
        low, high = float(bounds_low[0]), float(bounds_high[0])
        params = np.linspace(low, high, 64, endpoint=False)
        points = np.asarray(
            gmsh.model.getValue(1, tag, params.tolist()), dtype=float
        ).reshape((-1, 3))
        samples.extend(points.tolist())
    if not samples:
        raise ValueError("local refinement has no sampled geometric targets")
    distances, _ = cKDTree(np.asarray(samples)).query(
        np.asarray(nodes_m) * 1000, k=1
    )
    return int(np.count_nonzero(
        distances <= info["local_radius_mm"] + 1e-8
    ))


def mesh_cad_solid(
    path: str | Path,
    *,
    mesh_target_mm: float = 8.0,
    stl_units: Literal["mm"] | None = None,
    local_refinement: LocalRefinement | None = None,
) -> CadTetraMesh:
    """Mesh a *single* closed solid. STEP target units are mm; STL needs explicit mm.

    Large or complicated production parts will require a separate managed
    meshing service; this deliberately bounded path rejects excessive mesh sizes.
    """
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("CAD source must be a regular local file")
    suffix = source.suffix.lower()
    if suffix not in {".stp", ".step", ".stl"}:
        raise ValueError("only STEP (.stp, .step) and closed STL are supported")
    if suffix == ".stl" and stl_units != "mm":
        raise ValueError("STL has no unit metadata; explicitly declare stl_units='mm'")
    if not math.isfinite(mesh_target_mm) or not (0.5 <= mesh_target_mm <= 500.0):
        raise ValueError("mesh_target_mm must be 0.5..500 mm")
    if source.stat().st_size > MAX_CAD_BYTES or source.stat().st_size == 0:
        raise ValueError(f"CAD source must be nonempty and <= {MAX_CAD_BYTES} bytes")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    gmsh = _load_gmsh()
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("hardware-splicer-structural-screening")
        if suffix in {".step", ".stp"}:
            # OCC converts STEP's declared dimensions to millimetres.
            gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
            solids = gmsh.model.occ.importShapes(str(source))
            gmsh.model.occ.synchronize()
            if len([tag for dim, tag in solids if dim == 3]) != 1:
                raise ValueError("STEP must contain exactly one closed 3D solid")
        else:
            gmsh.merge(str(source))
            gmsh.model.mesh.classifySurfaces(math.radians(40), True, True, math.pi)
            gmsh.model.mesh.createGeometry()
            surfaces = gmsh.model.getEntities(2)
            if not surfaces or gmsh.model.getBoundary(surfaces, combined=True):
                raise ValueError("STL must form a closed orientable surface without open boundaries")
            loop = gmsh.model.geo.addSurfaceLoop([tag for _, tag in surfaces])
            gmsh.model.geo.addVolume([loop])
            gmsh.model.geo.synchronize()
        volumes = gmsh.model.getEntities(dim=3)
        if len(volumes) != 1:
            raise ValueError("meshing requires exactly one solid volume")
        kernel_volume_m3 = None
        if suffix in {".step", ".stp"}:
            kernel_volume_m3 = float(gmsh.model.occ.getMass(*volumes[0])) * 1e-9
            if not math.isfinite(kernel_volume_m3) or kernel_volume_m3 <= 0:
                raise ValueError("invalid STEP kernel volume")

        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(*volumes[0])
        spans = [xmax - xmin, ymax - ymin, zmax - zmin]
        if not all(math.isfinite(s) and s > 0 for s in spans):
            raise ValueError("invalid or degenerate CAD solid bounds")
        # A conservative pre-mesh work bound in addition to post-mesh limits.
        estimate = math.prod(max(1, math.ceil(s / mesh_target_mm)) for s in spans)
        if estimate > 2500:
            raise ValueError(
                "part too large for bounded FEM at requested mesh size; "
                "increase mesh_target_mm or use an offline engineering solver"
            )
        local_info = None
        if local_refinement is not None:
            local_info = _configure_local_refinement(
                gmsh, local_refinement,
                global_size_mm=mesh_target_mm,
                cad_bounds_mm=(xmin, ymin, zmin, xmax, ymax, zmax),
                source_format=suffix,
            )
        else:
            gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_target_mm)
            gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_target_mm)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.model.mesh.generate(3)
        nodes, tets, triangles, volume_m3, bounds = _triangulated_volume_mesh(
            gmsh, to_m=0.001
        )
        volume_error = (
            abs(volume_m3 - kernel_volume_m3) / kernel_volume_m3
            if kernel_volume_m3 is not None else None
        )
        if volume_error is not None and volume_error > 0.05:
            raise ValueError(
                "tetrahedral volume differs from STEP CAD kernel volume by more "
                "than 5%; refine the mesh before evaluating stress"
            )
        if local_info is not None:
            local_info["influence_region_node_count"] = (
                _count_nodes_near_refinement_features(
                    gmsh, nodes, local_info
                )
            )
            if local_info["influence_region_node_count"] == 0:
                raise ValueError("local refinement produced no nodes near targets")
        return CadTetraMesh(
            nodes_m=nodes,
            elements=tets,
            surface_triangles=triangles,
            source_sha256=f"sha256:{digest}",
            source_format=suffix.lstrip("."),
            source_name=source.name,
            source_units="mm",
            mesh_target_mm=mesh_target_mm,
            volume_m3=volume_m3,
            bounding_box_m=bounds,
            cad_kernel_volume_m3=kernel_volume_m3,
            mesh_volume_error_fraction=volume_error,
            local_refinement=local_info,
        )
    finally:
        gmsh.finalize()


def _selected_face(
    mesh: CadTetraMesh, plane: AxisPlane
) -> tuple[dict[int, float], float]:
    """Surface-area nodal weights on a single extreme Cartesian planar face."""
    import numpy as np

    axis = "xyz".index(plane[0])
    side = plane.split("_")[1]
    coords = np.asarray(mesh.nodes_m, dtype=float)
    edge = float(coords[:, axis].min() if side == "min" else coords[:, axis].max())
    tol_m = max(mesh.mesh_target_mm * 1e-6, 1e-5) / 1000.0
    nodal_weights: dict[int, float] = {}
    total_area = 0.0
    for tri in mesh.surface_triangles:
        v = coords[tri]
        if not np.all(abs(v[:, axis] - edge) <= tol_m):
            continue
        area = float(np.linalg.norm(np.cross(v[1] - v[0], v[2] - v[0])) / 2)
        if area <= 0:
            continue
        total_area += area
        for node in tri:
            nodal_weights[node] = nodal_weights.get(node, 0.0) + area / 3
    if total_area <= 0:
        raise ValueError(f"{plane} is not a planar meshed face with positive area")
    return nodal_weights, total_area


def build_face_loaded_case(
    mesh: CadTetraMesh,
    *,
    fixed_plane: AxisPlane,
    loaded_plane: AxisPlane,
    total_force_n: list[float],
    youngs_modulus_pa: float,
    poisson_ratio: float,
    yield_strength_pa: float | None = None,
) -> tuple[FemInput, dict[str, Any]]:
    """Uniform-traction approximation on the loaded face; fixed opposite face."""
    if fixed_plane == loaded_plane:
        raise ValueError("fixed_plane and loaded_plane must differ")
    if len(total_force_n) != 3 or not all(math.isfinite(x) for x in total_force_n):
        raise ValueError("total_force_n must contain 3 finite components")
    if not any(total_force_n):
        raise ValueError("total_force_n must be nonzero")
    fixed, fixed_area = _selected_face(mesh, fixed_plane)
    loaded, loaded_area = _selected_face(mesh, loaded_plane)
    if set(fixed).intersection(loaded):
        raise ValueError("fixed and loaded faces share nodes; choose distinct faces")
    loads = [
        {"node": node, "force_n": [component * area / loaded_area for component in total_force_n]}
        for node, area in sorted(loaded.items())
    ]
    body = FemInput.model_validate({
        "nodes_m": mesh.nodes_m,
        "elements": mesh.elements,
        "loads_n": loads,
        "constraints": [{"node": node} for node in sorted(fixed)],
        "youngs_modulus_pa": youngs_modulus_pa,
        "poisson_ratio": poisson_ratio,
        "yield_strength_pa": yield_strength_pa,
    })
    return body, {
        "fixed_plane": fixed_plane,
        "loaded_plane": loaded_plane,
        "fixed_face_area_m2": fixed_area,
        "loaded_face_area_m2": loaded_area,
        "fixed_node_count": len(fixed),
        "loaded_node_count": len(loaded),
        "total_applied_force_n": total_force_n,
        "load_distribution": "uniform_face_traction_area_weighted_by_surface_triangles",
    }


def run_cad_screening(
    path: str | Path, *, mesh_target_mm: float, stl_units: Literal["mm"] | None,
    fixed_plane: AxisPlane, loaded_plane: AxisPlane, total_force_n: list[float],
    youngs_modulus_pa: float, poisson_ratio: float,
    yield_strength_pa: float | None = None,
    local_refinement: LocalRefinement | None = None,
) -> dict[str, Any]:
    mesh = mesh_cad_solid(
        path, mesh_target_mm=mesh_target_mm, stl_units=stl_units,
        local_refinement=local_refinement,
    )
    case, boundary = build_face_loaded_case(
        mesh, fixed_plane=fixed_plane, loaded_plane=loaded_plane,
        total_force_n=total_force_n, youngs_modulus_pa=youngs_modulus_pa,
        poisson_ratio=poisson_ratio, yield_strength_pa=yield_strength_pa,
    )
    result = solve_linear_tetra_fem(case)
    return {
        "status": "cad_to_fem_screening_only",
        "cad": {
            "source_name": mesh.source_name,
            "source_sha256": mesh.source_sha256,
            "format": mesh.source_format,
            "source_units": mesh.source_units,
            "mesh_target_mm": mesh.mesh_target_mm,
            "bounding_box_m": mesh.bounding_box_m,
            "mesh_volume_m3": mesh.volume_m3,
            "cad_kernel_volume_m3": mesh.cad_kernel_volume_m3,
            "mesh_volume_error_fraction": mesh.mesh_volume_error_fraction,
            "surface_triangle_count": len(mesh.surface_triangles),
            "local_refinement": mesh.local_refinement,
        },
        "boundary_conditions": boundary,
        "analysis": result,
        "mesh_convergence_verified": False,
        "physical_validation_required": True,
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local bounded CAD-to-FEM screening")
    parser.add_argument("cad_file", type=Path)
    parser.add_argument("--mesh-size-mm", type=float, default=8.0)
    parser.add_argument(
        "--local-mesh-size-mm", type=float, default=None,
        help="Apply a single locally refined mesh at this target mm",
    )
    parser.add_argument(
        "--local-study-mm", nargs="+", type=float, default=None,
        help="Apply 3–4 decreasing localized targets; uses --mesh-size-mm as global",
    )
    parser.add_argument(
        "--local-radius-mm", type=float, default=None,
        help="Feature-distance influence radius in mm",
    )
    parser.add_argument(
        "--refine-circular-edges", action="store_true",
        help="STEP only: refine all OCC circular edges (no silent feature inference)",
    )
    parser.add_argument(
        "--hotspot-xyz-mm", nargs=3, type=float, action="append",
        metavar=("X", "Y", "Z"),
        help="Explicit CAD-coordinate hotspot center (mm); repeatable",
    )
    parser.add_argument(
        "--mesh-study-mm", type=float, nargs="+",
        help="Run 3-4 strictly decreasing coarse-to-fine sizes, e.g. 12 8 6; "
             "report sensitivity rather than only one mesh",
    )
    parser.add_argument(
        "--displacement-tolerance", type=float, default=0.02,
        help="Max adjacent-mesh relative change (study only; default 0.02)",
    )
    parser.add_argument(
        "--stress-tolerance", type=float, default=0.03,
        help="Max adjacent-mesh peak von Mises change (study only; default 0.03)",
    )
    parser.add_argument("--stl-units", choices=["mm"], default=None,
                        help="Mandatory for STL: acknowledge the model's mm units")
    parser.add_argument("--fixed-plane", choices=["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"], required=True)
    parser.add_argument("--loaded-plane", choices=["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"], required=True)
    parser.add_argument("--force-n", nargs=3, type=float, required=True, metavar=("FX", "FY", "FZ"))
    parser.add_argument("--youngs-pa", type=float, required=True)
    parser.add_argument("--poisson", type=float, required=True)
    parser.add_argument("--yield-pa", type=float, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    study_count = sum(
        value is not None for value in (
            args.mesh_study_mm, args.local_study_mm, args.local_mesh_size_mm
        )
    )
    if study_count > 1:
        parser.error("select only one of global mesh study, local mesh study, or local mesh")
    has_local_options = (
        args.local_radius_mm is not None or args.refine_circular_edges
        or args.hotspot_xyz_mm is not None
    )
    if has_local_options != (
        args.local_mesh_size_mm is not None or args.local_study_mm is not None
    ):
        parser.error("local refinement requires size/study, radius, and feature targets")
    if has_local_options and (
        args.local_radius_mm is None
        or not (args.refine_circular_edges or args.hotspot_xyz_mm)
    ):
        parser.error("local refinement needs radius and circular edges or hotspots")
    if args.mesh_study_mm is not None or args.local_study_mm is not None:
        from .mechanical_cad_convergence import run_cad_mesh_sensitivity

        result = run_cad_mesh_sensitivity(
            args.cad_file,
            mesh_sizes_mm=(
                args.local_study_mm if args.local_study_mm is not None
                else args.mesh_study_mm
            ),
            stl_units=args.stl_units,
            fixed_plane=args.fixed_plane, loaded_plane=args.loaded_plane,
            total_force_n=args.force_n, youngs_modulus_pa=args.youngs_pa,
            poisson_ratio=args.poisson, yield_strength_pa=args.yield_pa,
            displacement_tolerance=args.displacement_tolerance,
            stress_tolerance=args.stress_tolerance,
            global_mesh_size_mm=(
                args.mesh_size_mm if args.local_study_mm is not None else None
            ),
            local_radius_mm=args.local_radius_mm,
            refine_circular_edges=args.refine_circular_edges,
            hotspot_centers_mm=tuple(
                tuple(x) for x in (args.hotspot_xyz_mm or [])
            ),
        )
    else:
        result = run_cad_screening(
            args.cad_file, mesh_target_mm=args.mesh_size_mm, stl_units=args.stl_units,
            fixed_plane=args.fixed_plane, loaded_plane=args.loaded_plane,
            total_force_n=args.force_n, youngs_modulus_pa=args.youngs_pa,
            poisson_ratio=args.poisson, yield_strength_pa=args.yield_pa,
            local_refinement=(
                LocalRefinement(
                    target_size_mm=args.local_mesh_size_mm,
                    radius_mm=args.local_radius_mm,
                    refine_circular_edges=args.refine_circular_edges,
                    hotspot_centers_mm=tuple(
                        tuple(x) for x in (args.hotspot_xyz_mm or [])
                    ),
                ) if args.local_mesh_size_mm is not None else None
            ),
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"CAD-to-FEM screening saved: {args.out}")
    if args.mesh_study_mm is not None or args.local_study_mm is not None:
        print(f"mesh sensitivity: {result['status']}; "
              f"blockers={result['sensitivity_blockers']}; "
              "physical validation still required")
    else:
        print(f"elements={result['analysis']['element_count']} "
              f"max_displacement_m={result['analysis']['max_displacement_m']:.6g} "
              f"max_von_mises_pa={result['analysis']['max_von_mises_pa']:.6g} "
              "(screening only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
