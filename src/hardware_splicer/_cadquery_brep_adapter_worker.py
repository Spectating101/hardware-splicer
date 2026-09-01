"""Isolated CadQuery/OCCT worker for bounded bridge-block adapter synthesis.

The worker accepts two hash-pinned, placed STEP parents plus two already-resolved
exact BREP surface anchors. It generates only a rectangular bridge block spanning
approximately opposed planar anchor surfaces, exports that generated solid to STEP,
tessellates it for preview, and evaluates exact parent contact/intersection.

A successful worker result is geometric evidence only. It does not establish a
mounting method, material, strength, tolerance stack, manufacturability, retention,
connector compatibility, physical measurement, or fabrication authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


WORKER_SCHEMA = "hardware_splicer.cadquery_brep_adapter_worker.v1"
ROTATION_CONVENTION = "Rz*Ry*Rx; canonical STEP XYZ"
MAX_MESH_VERTICES = 5_000
MAX_MESH_TRIANGLES = 10_000
MAX_GENERATED_STEP_BYTES = 1_000_000


def _hash_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


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


def _vector(value, field: str) -> list[float]:
    row = [float(item) for item in value]
    if len(row) != 3 or not all(math.isfinite(item) for item in row):
        raise RuntimeError(f"{field} must contain exactly three finite values")
    return row


def _sub(left: list[float], right: list[float]) -> list[float]:
    return [left[index] - right[index] for index in range(3)]


def _add(left: list[float], right: list[float]) -> list[float]:
    return [left[index] + right[index] for index in range(3)]


def _scale(vector: list[float], scalar: float) -> list[float]:
    return [value * scalar for value in vector]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _cross(left: list[float], right: list[float]) -> list[float]:
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _norm(vector: list[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: list[float], field: str) -> list[float]:
    length = _norm(vector)
    if not math.isfinite(length) or length <= 1e-12:
        raise RuntimeError(f"{field} must have non-zero finite length")
    return [value / length for value in vector]


def _angle_deg(left: list[float], right: list[float]) -> float:
    cosine = max(-1.0, min(1.0, _dot(_normalize(left, "angle left"), _normalize(right, "angle right"))))
    return math.degrees(math.acos(cosine))


def _finite_vertex(vertex) -> list[float]:
    row = [float(vertex.x), float(vertex.y), float(vertex.z)]
    if not all(math.isfinite(value) for value in row):
        raise RuntimeError("CadQuery adapter tessellation produced non-finite coordinates")
    return row


def _shape_metrics(adapter, parent) -> tuple[float, float]:
    distance = float(adapter.distance(parent))
    volume = max(0.0, float(adapter.intersect(parent).Volume()))
    if not math.isfinite(distance) or distance < 0:
        raise RuntimeError("OCCT returned an invalid adapter-parent minimum distance")
    if not math.isfinite(volume) or volume < 0:
        raise RuntimeError("OCCT returned an invalid adapter-parent intersection volume")
    return distance, volume


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("CadQuery BREP adapter worker requires one JSON input path")

    import cadquery as cq  # Optional specialist dependency; worker process only.

    request_path = Path(sys.argv[1])
    request = json.loads(request_path.read_text(encoding="utf-8"))

    first_path = Path(request["first_step_path"])
    second_path = Path(request["second_step_path"])
    first_hash = _hash_bytes(first_path.read_bytes())
    second_hash = _hash_bytes(second_path.read_bytes())
    if first_hash != request.get("first_expected_content_hash"):
        raise RuntimeError("first STEP bytes no longer match the expected canonical content hash")
    if second_hash != request.get("second_expected_content_hash"):
        raise RuntimeError("second STEP bytes no longer match the expected canonical content hash")

    first = _place(_load_shape(cq, str(first_path)), dict(request["first_placement"]))
    second = _place(_load_shape(cq, str(second_path)), dict(request["second_placement"]))
    if not first.isValid() or not second.isValid():
        raise RuntimeError("CadQuery/OCCT reports an invalid placed parent STEP shape")
    if len(first.Solids()) <= 0 or len(second.Solids()) <= 0:
        raise RuntimeError("placed parent STEP source produced no solids")

    first_anchor = dict(request["first_anchor"])
    second_anchor = dict(request["second_anchor"])
    first_point = _vector(first_anchor["anchor_point_mm"], "first anchor point")
    second_point = _vector(second_anchor["anchor_point_mm"], "second anchor point")
    first_normal = _normalize(_vector(first_anchor["outward_normal"], "first outward normal"), "first outward normal")
    second_normal = _normalize(_vector(second_anchor["outward_normal"], "second outward normal"), "second outward normal")

    delta = _sub(second_point, first_point)
    length = _norm(delta)
    if length <= 1e-6:
        raise RuntimeError("adapter anchors must have non-zero separation")
    axis = _normalize(delta, "adapter bridge axis")
    first_axis_error_deg = _angle_deg(first_normal, axis)
    second_axis_error_deg = _angle_deg(second_normal, _scale(axis, -1.0))
    normal_opposition_error_deg = _angle_deg(first_normal, _scale(second_normal, -1.0))

    max_axis_error = float(request["max_axis_alignment_error_deg"])
    if first_axis_error_deg > max_axis_error + 1e-9 or second_axis_error_deg > max_axis_error + 1e-9:
        raise RuntimeError(
            "exact anchor normals are not sufficiently aligned with the bridge axis for bridge_block_v0"
        )

    width_mm = float(request["width_mm"])
    thickness_mm = float(request["thickness_mm"])
    if width_mm <= 0 or thickness_mm <= 0:
        raise RuntimeError("adapter width and thickness must be positive")

    midpoint = _scale(_add(first_point, second_point), 0.5)
    reference = [0.0, 0.0, 1.0]
    if abs(_dot(axis, reference)) > 0.90:
        reference = [0.0, 1.0, 0.0]
    plane_normal = _normalize(_cross(axis, reference), "adapter plane normal")
    plane = cq.Plane(origin=tuple(midpoint), xDir=tuple(axis), normal=tuple(plane_normal))
    adapter = cq.Workplane(plane).box(
        length,
        width_mm,
        thickness_mm,
        centered=(True, True, True),
    ).val()
    if not adapter.isValid() or len(adapter.Solids()) != 1:
        raise RuntimeError("generated bridge adapter is not one valid solid")

    first_distance_mm, first_intersection_volume_mm3 = _shape_metrics(adapter, first)
    second_distance_mm, second_intersection_volume_mm3 = _shape_metrics(adapter, second)
    contact_tolerance_mm = float(request["contact_distance_tolerance_mm"])
    penetration_tolerance_mm3 = float(request["penetration_volume_tolerance_mm3"])
    first_contact_passed = first_distance_mm <= contact_tolerance_mm + 1e-9
    second_contact_passed = second_distance_mm <= contact_tolerance_mm + 1e-9
    first_penetration_passed = first_intersection_volume_mm3 <= penetration_tolerance_mm3 + 1e-12
    second_penetration_passed = second_intersection_volume_mm3 <= penetration_tolerance_mm3 + 1e-12

    first_endpoint = _sub(midpoint, _scale(axis, length / 2.0))
    second_endpoint = _add(midpoint, _scale(axis, length / 2.0))
    first_endpoint_error_mm = _norm(_sub(first_endpoint, first_point))
    second_endpoint_error_mm = _norm(_sub(second_endpoint, second_point))

    adapter_step_path = request_path.parent / "generated-adapter.step"
    cq.exporters.export(adapter, str(adapter_step_path))
    adapter_step_bytes = adapter_step_path.read_bytes()
    if len(adapter_step_bytes) > MAX_GENERATED_STEP_BYTES:
        raise RuntimeError(
            f"generated adapter STEP is {len(adapter_step_bytes)} bytes; limit is {MAX_GENERATED_STEP_BYTES}"
        )
    try:
        adapter_step_content = adapter_step_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("generated adapter STEP is not UTF-8/ASCII text") from exc
    adapter_hash = _hash_bytes(adapter_step_bytes)

    tolerance_mm = float(request["tessellation_tolerance_mm"])
    angular_tolerance_rad = float(request["tessellation_angular_tolerance_rad"])
    vertices, triangles = adapter.tessellate(tolerance_mm, angular_tolerance_rad)
    if len(vertices) > MAX_MESH_VERTICES:
        raise RuntimeError(
            f"adapter tessellation produced {len(vertices)} vertices; limit is {MAX_MESH_VERTICES}"
        )
    if len(triangles) > MAX_MESH_TRIANGLES:
        raise RuntimeError(
            f"adapter tessellation produced {len(triangles)} triangles; limit is {MAX_MESH_TRIANGLES}"
        )
    vertex_rows = [_finite_vertex(vertex) for vertex in vertices]
    triangle_rows: list[list[int]] = []
    for triangle in triangles:
        row = [int(value) for value in triangle]
        if len(row) != 3 or any(value < 0 or value >= len(vertex_rows) for value in row):
            raise RuntimeError("adapter tessellation produced an invalid triangle index")
        triangle_rows.append(row)

    bbox = adapter.BoundingBox()
    volume_mm3 = float(adapter.Volume())
    if not math.isfinite(volume_mm3) or volume_mm3 <= 0:
        raise RuntimeError("generated adapter has invalid volume")

    geometric_candidate_passed = bool(
        first_contact_passed
        and second_contact_passed
        and first_penetration_passed
        and second_penetration_passed
        and first_endpoint_error_mm <= 1e-6
        and second_endpoint_error_mm <= 1e-6
    )

    print(
        json.dumps(
            {
                "ok": True,
                "worker_schema": WORKER_SCHEMA,
                "kernel": "cadquery_occt",
                "cadquery_version": getattr(cq, "__version__", None),
                "rotation_convention": ROTATION_CONVENTION,
                "first_input_content_hash": first_hash,
                "second_input_content_hash": second_hash,
                "parent_placements_applied": True,
                "parent_shapes_valid": True,
                "adapter_family": "bridge_block_v0",
                "adapter_shape_valid": True,
                "adapter_solid_count": 1,
                "adapter_axis": axis,
                "adapter_midpoint_mm": midpoint,
                "adapter_length_mm": length,
                "adapter_width_mm": width_mm,
                "adapter_thickness_mm": thickness_mm,
                "adapter_volume_mm3": volume_mm3,
                "first_axis_alignment_error_deg": first_axis_error_deg,
                "second_axis_alignment_error_deg": second_axis_error_deg,
                "normal_opposition_error_deg": normal_opposition_error_deg,
                "first_endpoint_error_mm": first_endpoint_error_mm,
                "second_endpoint_error_mm": second_endpoint_error_mm,
                "first_parent_minimum_distance_mm": first_distance_mm,
                "second_parent_minimum_distance_mm": second_distance_mm,
                "first_parent_intersection_volume_mm3": first_intersection_volume_mm3,
                "second_parent_intersection_volume_mm3": second_intersection_volume_mm3,
                "first_parent_contact_passed": first_contact_passed,
                "second_parent_contact_passed": second_contact_passed,
                "first_parent_penetration_passed": first_penetration_passed,
                "second_parent_penetration_passed": second_penetration_passed,
                "geometric_candidate_passed": geometric_candidate_passed,
                "generated_step_content": adapter_step_content,
                "generated_content_hash": adapter_hash,
                "generated_step_bytes": len(adapter_step_bytes),
                "bbox_minimum_mm": [float(bbox.xmin), float(bbox.ymin), float(bbox.zmin)],
                "bbox_maximum_mm": [float(bbox.xmax), float(bbox.ymax), float(bbox.zmax)],
                "vertex_count": len(vertex_rows),
                "triangle_count": len(triangle_rows),
                "vertices_mm": vertex_rows,
                "triangles": triangle_rows,
                "tessellation_tolerance_mm": tolerance_mm,
                "tessellation_angular_tolerance_rad": angular_tolerance_rad,
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
