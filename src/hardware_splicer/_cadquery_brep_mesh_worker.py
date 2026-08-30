"""Isolated CadQuery/OCCT worker for bounded STEP tessellation evidence."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


WORKER_SCHEMA = "hardware_splicer.cadquery_brep_mesh_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
MAX_MESH_VERTICES = 25_000
MAX_MESH_TRIANGLES = 50_000


def _load_shape(cq, path: str):
    workplane = cq.importers.importStep(path)
    shapes = [value for value in workplane.vals() if hasattr(value, "wrapped")]
    if not shapes:
        raise RuntimeError(f"STEP import produced no CadQuery shapes: {path}")
    if len(shapes) == 1:
        return shapes[0]
    return cq.Compound.makeCompound(shapes)


def _place(shape, row: dict):
    translation = [float(value) for value in row.get("translation_mm", [0.0, 0.0, 0.0])]
    rotation = [float(value) for value in row.get("rotation_deg_xyz", [0.0, 0.0, 0.0])]
    if len(translation) != 3 or len(rotation) != 3:
        raise RuntimeError("CadQuery placement requires three translation and three rotation values")
    return shape.moved(
        x=translation[0],
        y=translation[1],
        z=translation[2],
        rx=rotation[0],
        ry=rotation[1],
        rz=rotation[2],
    )


def _finite_vertex(vertex) -> list[float]:
    row = [float(vertex.x), float(vertex.y), float(vertex.z)]
    if not all(math.isfinite(value) for value in row):
        raise RuntimeError("CadQuery tessellation produced non-finite vertex coordinates")
    return row


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("CadQuery BREP mesh worker requires one JSON input path")

    import cadquery as cq  # Optional specialist dependency; worker process only.

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    step_path = Path(request["step_path"])
    content = step_path.read_bytes()
    content_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
    if content_hash != request.get("expected_content_hash"):
        raise RuntimeError("STEP bytes no longer match the expected canonical content hash")

    tolerance_mm = float(request["tolerance_mm"])
    angular_tolerance_rad = float(request["angular_tolerance_rad"])
    placement = request.get("placement") or {
        "translation_mm": [0.0, 0.0, 0.0],
        "rotation_deg_xyz": [0.0, 0.0, 0.0],
    }
    shape = _place(_load_shape(cq, str(step_path)), placement)
    shape_valid = bool(shape.isValid())
    solid_count = len(shape.Solids())
    if not shape_valid:
        raise RuntimeError("CadQuery/OCCT reports an invalid imported STEP shape")
    if solid_count <= 0:
        raise RuntimeError("CadQuery STEP import produced no solids")

    vertices, triangles = shape.tessellate(tolerance_mm, angular_tolerance_rad)
    if len(vertices) > MAX_MESH_VERTICES:
        raise RuntimeError(
            f"CadQuery tessellation produced {len(vertices)} vertices; limit is {MAX_MESH_VERTICES}"
        )
    if len(triangles) > MAX_MESH_TRIANGLES:
        raise RuntimeError(
            f"CadQuery tessellation produced {len(triangles)} triangles; limit is {MAX_MESH_TRIANGLES}"
        )

    vertex_rows = [_finite_vertex(vertex) for vertex in vertices]
    triangle_rows: list[list[int]] = []
    for triangle in triangles:
        row = [int(value) for value in triangle]
        if len(row) != 3 or any(value < 0 or value >= len(vertex_rows) for value in row):
            raise RuntimeError("CadQuery tessellation produced an invalid triangle index")
        triangle_rows.append(row)

    print(
        json.dumps(
            {
                "ok": True,
                "worker_schema": WORKER_SCHEMA,
                "kernel": "cadquery_occt",
                "cadquery_version": getattr(cq, "__version__", None),
                "input_content_hash": content_hash,
                "shape_valid": shape_valid,
                "solid_count": solid_count,
                "vertex_count": len(vertex_rows),
                "triangle_count": len(triangle_rows),
                "vertices_mm": vertex_rows,
                "triangles": triangle_rows,
                "tolerance_mm": tolerance_mm,
                "angular_tolerance_rad": angular_tolerance_rad,
                "rotation_convention": ROTATION_CONVENTION,
                "placement_applied": True,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
