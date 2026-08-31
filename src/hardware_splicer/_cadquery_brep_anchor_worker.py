"""Isolated CadQuery/OCCT worker for placed STEP surface-anchor evidence."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


WORKER_SCHEMA = "hardware_splicer.cadquery_brep_anchor_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"


def _content_hash(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


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
        raise RuntimeError("CadQuery anchor placement requires three translation and three rotation values")
    if not all(math.isfinite(value) for value in [*translation, *rotation]):
        raise RuntimeError("CadQuery anchor placement requires finite translation and rotation values")
    return shape.moved(
        x=translation[0],
        y=translation[1],
        z=translation[2],
        rx=rotation[0],
        ry=rotation[1],
        rz=rotation[2],
    )


def _vector_row(vector) -> list[float]:
    row = [float(vector.x), float(vector.y), float(vector.z)]
    if not all(math.isfinite(value) for value in row):
        raise RuntimeError("CadQuery anchor worker produced non-finite geometry")
    return row


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("CadQuery BREP anchor worker requires one JSON input path")

    import cadquery as cq  # Optional specialist dependency; worker process only.
    from cadquery.occ_impl.shapes import closest

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    step_path = Path(request["step_path"])
    content_hash = _content_hash(step_path)
    if content_hash != request.get("expected_content_hash"):
        raise RuntimeError("STEP bytes no longer match the expected canonical content hash")

    probe = [float(value) for value in request["probe_point_mm"]]
    if len(probe) != 3 or not all(math.isfinite(value) for value in probe):
        raise RuntimeError("BREP anchor probe_point_mm must contain three finite values")
    max_snap_distance_mm = float(request["max_snap_distance_mm"])
    if not math.isfinite(max_snap_distance_mm) or max_snap_distance_mm < 0:
        raise RuntimeError("BREP anchor max_snap_distance_mm must be finite and non-negative")

    shape = _place(_load_shape(cq, str(step_path)), request["placement"])
    if not shape.isValid():
        raise RuntimeError("CadQuery/OCCT reports an invalid imported STEP shape")
    solid_count = len(shape.Solids())
    if solid_count <= 0:
        raise RuntimeError("CadQuery STEP import produced no solids")

    probe_vertex = cq.Vertex.makeVertex(*probe)
    faces = list(shape.Faces())
    if not faces:
        raise RuntimeError("CadQuery STEP import produced no faces")

    best = None
    for face_index, face in enumerate(faces):
        point_on_face, _point_on_probe = closest(face, probe_vertex)
        point_row = _vector_row(point_on_face)
        distance = math.dist(point_row, probe)
        if best is None or distance < best[0]:
            best = (distance, face_index, face, point_on_face, point_row)

    assert best is not None
    snap_distance_mm, face_index, face, point_on_face, anchor_point_mm = best
    if snap_distance_mm > max_snap_distance_mm:
        raise RuntimeError(
            f"nearest BREP surface is {snap_distance_mm:.6f} mm from probe; "
            f"maximum allowed is {max_snap_distance_mm:.6f} mm"
        )

    normal = face.normalAt(point_on_face)
    outward_normal = _vector_row(normal)
    normal_length = math.sqrt(sum(value * value for value in outward_normal))
    if not math.isfinite(normal_length) or abs(normal_length - 1.0) > 1e-5:
        raise RuntimeError("CadQuery face normal is not a finite unit vector")

    center = _vector_row(face.Center())
    area_mm2 = float(face.Area())
    if not math.isfinite(area_mm2) or area_mm2 <= 0:
        raise RuntimeError("CadQuery face area is not finite and positive")

    print(
        json.dumps(
            {
                "ok": True,
                "worker_schema": WORKER_SCHEMA,
                "kernel": "cadquery_occt",
                "cadquery_version": getattr(cq, "__version__", None),
                "input_content_hash": content_hash,
                "rotation_convention": ROTATION_CONVENTION,
                "placement_applied": True,
                "shape_valid": True,
                "solid_count": solid_count,
                "face_count": len(faces),
                "face_index": face_index,
                "face_geom_type": str(face.geomType()),
                "face_area_mm2": area_mm2,
                "face_center_mm": center,
                "probe_point_mm": probe,
                "anchor_point_mm": anchor_point_mm,
                "outward_normal": outward_normal,
                "snap_distance_mm": snap_distance_mm,
                "max_snap_distance_mm": max_snap_distance_mm,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
